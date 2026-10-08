#!/usr/bin/env python3
"""Offline, fidelity-first raster-to-SVG reconstruction.

The default backend is VTracer (a local curve tracer). It preserves the
reference's paths and paint order instead of inventing semantic shapes. Text
is removed with glyph-sized masks and added back as live SVG text, so labels
remain editable in Illustrator. No image bytes leave this process.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
import json
from pathlib import Path
from typing import Any
from runtime_env import bootstrap
bootstrap()

try:
    import cv2
    import numpy as np
except Exception as exc:
    raise SystemExit(f"LOCAL_PYTHON_MISSING|OpenCV/numpy unavailable: {exc}") from exc


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def read_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower() or ".png"
    ok, encoded = cv2.imencode(suffix, image)
    if not ok:
        raise RuntimeError(f"Could not encode image: {path}")
    encoded.tofile(str(path))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    entries = payload.get("text_elements") or payload.get("objects") or []
    if not isinstance(entries, list):
        raise ValueError("text manifest must contain a list in text_elements or objects")
    result = [item for item in entries if isinstance(item, dict) and str(item.get("content", "")).strip()]
    # Preserve caller order for ties; alphabetical IDs are not paint order.
    result.sort(key=lambda item: float(item.get("paint_order", item.get("z_index", 0)) or 0))
    for entry in result:
        if entry.get("mask_path"):
            mask_path = Path(entry["mask_path"])
            entry["mask_path"] = str((path.parent / mask_path).resolve() if not mask_path.is_absolute() else mask_path)
    return result


def bbox_px(entry: dict[str, Any], width: int, height: int) -> tuple[int, int, int, int] | None:
    raw = entry.get("bbox_px") or entry.get("bbox")
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        x, y, w, h = [float(value) for value in raw[:4]]
    else:
        x = float(entry.get("x", 0.0) or 0.0)
        y = float(entry.get("y", 0.0) or 0.0)
        w = float(entry.get("width", entry.get("w", 0.0)) or 0.0)
        h = float(entry.get("height", entry.get("h", 0.0)) or 0.0)
        if entry.get("coordinate_space") == "normalized" or max(abs(x), abs(y), abs(w), abs(h)) <= 1.5:
            x, y, w, h = x * width, y * height, w * width, h * height
    if w <= 0 or h <= 0:
        return None
    x0 = max(0, min(width - 1, int(round(x))))
    y0 = max(0, min(height - 1, int(round(y))))
    x1 = max(x0 + 1, min(width, int(round(x + w))))
    y1 = max(y0 + 1, min(height, int(round(y + h))))
    return x0, y0, x1 - x0, y1 - y0


def parse_rgb(value: str) -> tuple[int, int, int] | None:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        return None
    try:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return None


def font_size_px(entry: dict[str, Any], height: int) -> float:
    # Legacy source_font_size_pt was stored as image-coordinate pixels.
    # New manifests should use source_font_size_px to avoid the ambiguity.
    size = float(entry.get("source_font_size_px", entry.get("source_font_size_pt", entry.get("font_size", 16))))
    if "source_font_size_px" not in entry and "source_font_size_pt" not in entry:
        if entry.get("font_size_space") == "normalized":
            size *= height
    if not np.isfinite(size) or size <= 0:
        raise ValueError(f"Invalid font size on {entry.get('id', '?')}")
    return size


def protect_mask(mask: np.ndarray, entry: dict[str, Any]) -> np.ndarray:
    height, width = mask.shape
    for raw in entry.get("protect_regions", []):
        if not isinstance(raw, (list, tuple)) or len(raw) != 4:
            raise ValueError("protect_regions requires [x,y,width,height] boxes")
        x, y, w, h = map(float, raw)
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(width, int(np.ceil(x+w))), min(height, int(np.ceil(y+h)))
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = 0
    return mask


def glyph_mask_for_entry(image: np.ndarray, entry: dict[str, Any], radius: int) -> np.ndarray:
    """Mask text-like components only; never erase an entire declared box."""
    height, width = image.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    mode = str(entry.get("mask_mode", "glyphs")).lower()
    if mode in {"none", "off", "false"}:
        return mask
    if mode == "manual":
        if not entry.get("mask_path"):
            raise ValueError(f"manual mask requires mask_path: {entry.get('id')}")
        raw = np.fromfile(str(entry["mask_path"]), dtype=np.uint8)
        manual = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
        if manual is None or manual.shape != (height, width):
            raise ValueError("Manual mask must match the complete source canvas")
        return protect_mask(np.uint8(manual > 127) * 255, entry)
    if mode != "glyphs":
        raise ValueError(f"Unknown mask_mode: {mode}")
    box = bbox_px(entry, width, height)
    if box is None:
        return mask
    x, y, w, h = box
    # OCR boxes are often a few pixels too tight at the last glyph.  Expand
    # only the cleanup ROI; live-text placement still uses the original box.
    pad_x = int(round(w * float(entry.get("mask_pad_x", 0))))
    pad_y = int(round(h * float(entry.get("mask_pad_y", 0))))
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(width, x + w + pad_x)
    y1 = min(height, y + h + pad_y)
    x, y, w, h = x0, y0, x1 - x0, y1 - y0
    roi = image[y:y + h, x:x + w]
    colors = entry.get("mask_colors") or [entry.get("mask_color") or entry.get("fill") or "#141414"]
    if not entry.get("mask_colors"):
        colors += [style["fill"] for style in entry.get("line_styles", []) if isinstance(style, dict) and style.get("fill")]
    # A wide threshold used to remove salmon outlines and faint connectors.
    # Match glyph cores tightly; a controlled 1px dilation handles AA fringes.
    threshold = float(entry.get("mask_threshold", 70))
    candidate = np.zeros((h, w), dtype=np.uint8)
    for color in colors:
        rgb = parse_rgb(str(color))
        if rgb is None:
            raise ValueError(f"mask color must be hexadecimal: {color}")
        target = np.array(rgb[::-1], dtype=np.float32)
        distance = np.linalg.norm(roi.astype(np.float32) - target[None, None, :], axis=2)
        candidate[distance <= threshold] = 255
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(candidate, 8)
    size = font_size_px(entry, height)
    max_component_area = float(entry.get("max_component_area", size * size * 2))
    for index in range(1, count):
        bx, by, bw, bh, area = [int(value) for value in stats[index]]
        if area < 2 or area > max_component_area:
            continue
        if bh > size * 1.6 or bw > size * 3.5:
            continue
        if bw >= w - 1 or bh >= h - 1:
            continue  # a crossing border/connector, or a box needing review
        component = np.uint8(labels == index) * 255
        mask[y:y + h, x:x + w] = np.maximum(mask[y:y + h, x:x + w], component)
    dilation = int(entry.get("mask_dilation", 1))
    if dilation > 0 and np.any(mask):
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=dilation)
        bounds = np.zeros_like(mask)
        bounds[y:y+h, x:x+w] = 255
        mask = cv2.bitwise_and(mask, bounds)
    return protect_mask(mask, entry)


def clean_text_glyphs(image: np.ndarray, manifest: list[dict[str, Any]], radius: int) -> tuple[np.ndarray, int]:
    combined = np.zeros(image.shape[:2], dtype=np.uint8)
    for entry in manifest:
        combined = np.maximum(combined, glyph_mask_for_entry(image, entry, radius))
    for entry in manifest:
        combined = protect_mask(combined, entry)
    pixels = int(np.count_nonzero(combined))
    if not pixels:
        return image.copy(), 0
    return cv2.inpaint(image, combined, float(max(1, radius)), cv2.INPAINT_TELEA), pixels


def xml_local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def add_ids_and_text(root: ET.Element, manifest: list[dict[str, Any]], width: int, height: int, prefix: str) -> int:
    drawable = 0
    for element in root.iter():
        if xml_local(element.tag) in {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text"}:
            drawable += 1
            if not element.get("id"):
                element.set("id", f"{prefix}-path-{drawable:06d}")
    for entry_index, entry in enumerate(manifest, start=1):
        content = str(entry.get("content", "")).strip()
        if not content:
            continue
        size = font_size_px(entry, height)
        attrs = {
            "fill": str(entry.get("fill", entry.get("color", "#111111"))),
            "fill-opacity": str(entry.get("opacity", 1)),
            "font-family": str(entry.get("font_family", "Arial")),
            "font-size": f"{size:.3f}",
            "font-weight": str(entry.get("font_weight", "normal")),
            "font-style": str(entry.get("font_style", "normal")),
            "text-anchor": str(entry.get("text_anchor", entry.get("alignment", "middle"))),
            "dominant-baseline": str(entry.get("alignment_baseline", "alphabetic")),
        }
        if entry.get('object_id'):
            attrs['data-huitu-owner'] = str(entry['object_id'])
        box = bbox_px(entry, width, height)
        anchor = attrs["text-anchor"].lower()
        # An explicit baseline beats a bbox heuristic. Bbox-only manifests
        # remain supported but are flagged for position review by the linter.
        if box is not None and entry.get("position_from_bbox", not ("x" in entry and "y" in entry)):
            bx, by, bw, _bh = box
            x = bx + (bw / 2.0 if anchor in {"middle", "center"} else bw if anchor == "end" else 0.0)
            y = by + size * 0.92
        else:
            x = float(entry.get("x", 0.0) or 0.0)
            y = float(entry.get("y", 0.0) or 0.0)
            if entry.get("coordinate_space") == "normalized":
                x *= width
                y *= height
        line_height = float(entry.get("line_height", 1.15) or 1.15)
        rotation = float(entry.get("rotation", 0) or 0)
        lines = content.splitlines() or [content]
        line_styles = entry.get("line_styles") if isinstance(entry.get("line_styles"), list) else []
        for line_index, line in enumerate(lines):
            baseline = y + line_index * size * line_height
            line_attrs = dict(attrs)
            if line_index < len(line_styles) and isinstance(line_styles[line_index], dict):
                for key in ("fill", "font-weight", "font-style", "font-family"):
                    if key in line_styles[line_index]:
                        line_attrs[key] = str(line_styles[line_index][key])
            element = ET.SubElement(root, f"{{{SVG_NS}}}text", {
                "id": f"{prefix}-text-{entry_index:04d}-{line_index:02d}",
                "x": f"{x:.3f}",
                "y": f"{baseline:.3f}",
                **line_attrs,
            })
            horizontal_scale = float(entry.get("horizontal_scale", 1))
            transforms = []
            if rotation:
                transforms.append(f"rotate({rotation:.3f} {x:.3f} {y:.3f})")
            if abs(horizontal_scale-1) > 1e-6:
                transforms.append(f"translate({x:.3f} {y:.3f}) scale({horizontal_scale:.6f} 1) translate({-x:.3f} {-y:.3f})")
            if transforms:
                element.set("transform", " ".join(transforms))
            element.text = line
    return drawable + sum(len(str(entry.get("content", "")).splitlines()) for entry in manifest)


def vtracer_trace(cleaned_path: Path, output_path: Path, width: int, height: int, args: argparse.Namespace) -> int:
    try:
        import vtracer
    except Exception as exc:
        raise RuntimeError(
            "LOCAL_VTRACER_MISSING|Install vtracer in the skill .deps directory "
            "or set HUITU_DEPENDENCIES; refusing a low-fidelity contour fallback."
        ) from exc
    vtracer.convert_image_to_svg_py(
        str(cleaned_path), str(output_path),
        colormode="color", hierarchical="stacked", mode="spline",
        filter_speckle=int(args.filter_speckle),
        color_precision=int(args.color_precision),
        layer_difference=int(args.layer_difference),
        corner_threshold=int(args.corner_threshold),
        length_threshold=float(args.length_threshold),
        max_iterations=int(args.max_iterations),
        splice_threshold=int(args.splice_threshold),
        path_precision=int(args.path_precision),
    )
    tree = ET.parse(output_path)
    root = tree.getroot()
    root.set("width", str(width))
    root.set("height", str(height))
    root.set("viewBox", f"0 0 {width} {height}")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return len([element for element in root.iter() if xml_local(element.tag) == "path"])


def reconstruct(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input).resolve(strict=True)
    output = Path(args.output).resolve()
    image = read_image(source)
    height, width = image.shape[:2]
    manifest_path = Path(args.text_manifest).resolve() if args.text_manifest else None
    if manifest_path:
        from manifest_lint import lint
        check = lint(manifest_path)
        if check["status"] != "PASS":
            raise ValueError("TEXT_MANIFEST_INVALID|" + "; ".join(check["errors"]))
    manifest = read_manifest(manifest_path)
    if args.mask_output:
        combined = np.zeros(image.shape[:2], dtype=np.uint8)
        for entry in manifest:
            combined = np.maximum(combined, glyph_mask_for_entry(image, entry, args.inpaint_radius))
        for entry in manifest:
            combined = protect_mask(combined, entry)
        write_image(Path(args.mask_output).resolve(), combined)
    cleaned, masked_pixels = clean_text_glyphs(image, manifest, args.inpaint_radius)
    output.parent.mkdir(parents=True, exist_ok=True)
    cleaned_path = Path(args.cleaned_output).resolve() if args.cleaned_output else output.with_name(f"{output.stem}.cleaned.png")
    write_image(cleaned_path, cleaned)
    with tempfile.TemporaryDirectory(prefix="huitu-trace-") as temporary:
        traced_path = Path(temporary) / "traced.svg"
        path_count = vtracer_trace(cleaned_path, traced_path, width, height, args)
        tree = ET.parse(traced_path)
        root = tree.getroot()
        root.set('data-huitu-build','auto-trace-draft')
        add_ids_and_text(root, manifest, width, height, args.id_prefix)
        tree.write(output, encoding="utf-8", xml_declaration=True)
    analysis = {
        "schema_version": "2.0",
        "source": str(source),
        "source_sha256": sha256_file(source),
        "output": str(output),
        "width": width,
        "height": height,
        "backend": "vtracer-spline-local",
        "traced_paths": path_count,
        "live_text_entries": len(manifest),
        "masked_glyph_pixels": masked_pixels,
        "raster_nodes": 0,
        "local_only": True,
        "quality_gate": "render-and-inspect-required",
        "trace_settings": {"filter_speckle": args.filter_speckle, "color_precision": args.color_precision,
                           "layer_difference": args.layer_difference, "length_threshold": args.length_threshold},
    }
    if args.analysis_output:
        report = Path(args.analysis_output).resolve()
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    return analysis


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--text-manifest")
    parser.add_argument("--cleaned-output")
    parser.add_argument("--mask-output", help="Inspect actual glyph mask before committing cleanup")
    parser.add_argument("--analysis-output")
    parser.add_argument("--inpaint-radius", type=int, default=2)
    parser.add_argument("--preset", choices=["detail", "balanced"], default="detail")
    parser.add_argument("--filter-speckle", type=int)
    parser.add_argument("--color-precision", type=int)
    parser.add_argument("--layer-difference", type=int)
    parser.add_argument("--corner-threshold", type=int, default=60)
    parser.add_argument("--length-threshold", type=float)
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--splice-threshold", type=int, default=45)
    parser.add_argument("--path-precision", type=int, default=2)
    parser.add_argument("--id-prefix", default="cishanjia-diagnostic")
    args = parser.parse_args()
    settings = {"detail": (1, 7, 4, 2.0), "balanced": (8, 6, 16, 4.0)}
    for key, value in zip(("filter_speckle", "color_precision", "layer_difference", "length_threshold"), settings[args.preset]):
        if getattr(args, key) is None:
            setattr(args, key, value)
    try:
        analysis = reconstruct(args)
    except Exception as exc:
        print(f"ERROR|{exc}", file=sys.stderr)
        raise
    print(json.dumps(analysis, ensure_ascii=False))


if __name__ == "__main__":
    main()
