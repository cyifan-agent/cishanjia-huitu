#!/usr/bin/env python3
"""Render a local SVG and report a visual comparison against its source image."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


from runtime_env import bootstrap
bootstrap()
import cv2
import numpy as np
import resvg_py
from svg_contract import view_box
import xml.etree.ElementTree as ET
from render_cache import render_png,from_directory


def load_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return image


def save_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        raise RuntimeError(f"cannot encode {path}")
    encoded.tofile(str(path))


def render(svg: Path, width: int, height: int,cache=None) -> np.ndarray:
    import tempfile
    from preview_fonts import font_files_for_svg
    with tempfile.TemporaryDirectory(prefix="huitu-preview-fonts-") as temporary:
        files=font_files_for_svg(svg,Path(temporary))
        payload=render_png(svg.read_text(encoding='utf-8-sig'),width=width,height=height,font_files=files,cache=cache)
    data = np.frombuffer(payload, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("resvg returned no raster")
    return image


def edge_f1(source: np.ndarray, output: np.ndarray, low: int = 80, high: int = 180) -> float:
    a = cv2.Canny(source, low, high)
    b = cv2.Canny(output, low, high)
    kernel = np.ones((5, 5), np.uint8)
    a_near_b = cv2.dilate(b, kernel)
    b_near_a = cv2.dilate(a, kernel)
    recall = float(np.count_nonzero((a > 0) & (a_near_b > 0))) / max(1, int(np.count_nonzero(a)))
    precision = float(np.count_nonzero((b > 0) & (b_near_a > 0))) / max(1, int(np.count_nonzero(b)))
    if not np.any(a) and not np.any(b):
        return 1.0
    return 2 * recall * precision / max(1e-9, recall + precision)


def region_metrics(source: np.ndarray, output: np.ndarray, regions_path: Path | None) -> list[dict]:
    if regions_path is None:
        return []
    payload = json.loads(regions_path.read_text(encoding="utf-8-sig"))
    entries = payload if isinstance(payload, list) else payload.get("regions", payload.get("text_elements", payload.get("objects", [])))
    if not isinstance(entries, list):
        raise ValueError("--regions must contain a list or text_elements")
    height, width = source.shape[:2]
    result = []
    seen = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Invalid region {index}")
        box = entry.get("bbox_px") or entry.get("bbox")
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError(f"Region {index} needs bbox_px")
        if not all(np.isfinite(float(value)) for value in box):
            raise ValueError(f"Non-finite region {index}")
        x, y, w, h = [int(round(float(value))) for value in box[:4]]
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x+w > width or y+h > height:
            raise ValueError(f"Invalid/outside-canvas region {index}")
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(width, x + max(1, w)), min(height, y + max(1, h))
        if x1 <= x0 or y1 <= y0:
            raise ValueError(f"Empty/outside-canvas region {index}")
        source_crop = source[y0:y1, x0:x1]
        output_crop = output[y0:y1, x0:x1]
        item = {
            "id": str(entry.get("id", f"region-{index:03d}")),
            "bbox_px": [x0, y0, x1 - x0, y1 - y0],
            "pixel_mae_bgr": round(float(np.mean(cv2.absdiff(source_crop, output_crop))), 3),
            "edge_f1_tolerance_2px": round(edge_f1(source_crop, output_crop), 4),
            "low_contrast_edge_f1_tolerance_2px": round(edge_f1(source_crop, output_crop, 20, 60), 4),
            "critical": bool(entry.get("critical", False)),
        }
        if item["id"] in seen:
            raise ValueError(f"Duplicate region id: {item['id']}")
        seen.add(item["id"])
        for key in ("max_mae", "min_edge_f1", "min_low_contrast_edge_f1"):
            if key in entry:
                item[key] = float(entry[key])
                limit = 255 if key == "max_mae" else 1
                if not np.isfinite(item[key]) or not 0 <= item[key] <= limit:
                    raise ValueError(f"Invalid regional threshold: {key}")
        result.append(item)
    return result


def compare(args: argparse.Namespace) -> dict:
    source = load_image(Path(args.source).resolve())
    canvas = view_box(ET.parse(args.svg).getroot())
    if any(abs(a-b) > 1e-6 for a, b in zip(canvas, (0, 0, source.shape[1], source.shape[0]))):
        raise ValueError("SVG viewBox must match source pixel canvas; fix coordinates instead of stretching")
    cache=from_directory(getattr(args,'cache_dir',None))
    output = render(Path(args.svg).resolve(), source.shape[1], source.shape[0],cache)
    if output.shape[:2] != source.shape[:2]:
        raise ValueError("SVG render aspect ratio differs from the source; do not rescale a mismatch away")
    diff = cv2.absdiff(source, output)
    mae = float(np.mean(diff))
    f1 = edge_f1(source, output)
    regions = region_metrics(source, output, Path(args.regions).resolve() if args.regions else None)
    region_previews = getattr(args, "region_previews", None)
    if region_previews:
        crop_dir = Path(region_previews).resolve()
        for index, region in enumerate(regions, 1):
            x, y, w, h = region["bbox_px"]
            a, b = source[y:y+h, x:x+w], output[y:y+h, x:x+w]
            safe_id = __import__("re").sub(r"[^A-Za-z0-9_-]", "_", region["id"])[:48]
            crop_path = crop_dir / f"{index:03d}-{safe_id}.png"
            save_image(crop_path, np.concatenate([a, np.full((h, 12, 3), 245, np.uint8), b], axis=1))
            region["qa_crop"] = str(crop_path)
    # Make a contact sheet and a low-frequency difference map for visual QA.
    left = cv2.cvtColor(source, cv2.COLOR_BGR2RGB)
    right = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
    gap = np.full((source.shape[0], 18, 3), 245, dtype=np.uint8)
    sheet = np.concatenate([left, gap, right], axis=1)
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    diff_heat = cv2.applyColorMap(np.clip(diff_gray.astype(np.float32) * 3, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    if args.preview:
        save_image(Path(args.preview).resolve(), output)
    if args.contact_sheet:
        save_image(Path(args.contact_sheet).resolve(), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    if args.diff:
        save_image(Path(args.diff).resolve(), diff_heat)
    report = {
        "source": str(Path(args.source).resolve()),
        "svg": str(Path(args.svg).resolve()),
        "render_width": int(source.shape[1]),
        "render_height": int(source.shape[0]),
        "pixel_mae_bgr": round(mae, 3),
        "edge_f1_tolerance_2px": round(f1, 4),
        "low_contrast_edge_f1_tolerance_2px": round(edge_f1(source, output, 20, 60), 4),
        "regions": regions,
        "quality_gate": "human-visual-review-required",
        "notes": "Metrics detect regressions; they do not prove semantic correctness or pixel identity.",
    }
    failures = []
    if args.max_mae is not None and mae > args.max_mae:
        failures.append(f"pixel_mae_bgr>{args.max_mae}")
    if args.min_edge_f1 is not None and f1 < args.min_edge_f1:
        failures.append(f"edge_f1<{args.min_edge_f1}")
    for region in regions:
        if "max_mae" in region and region["pixel_mae_bgr"] > region["max_mae"]:
            failures.append(f"region:{region['id']}:pixel_mae>{region['max_mae']}")
        if "min_edge_f1" in region and region["edge_f1_tolerance_2px"] < region["min_edge_f1"]:
            failures.append(f"region:{region['id']}:edge_f1<{region['min_edge_f1']}")
        if "min_low_contrast_edge_f1" in region and region["low_contrast_edge_f1_tolerance_2px"] < region["min_low_contrast_edge_f1"]:
            failures.append(f"region:{region['id']}:low_contrast_edge_f1<{region['min_low_contrast_edge_f1']}")
    report["threshold_failures"] = failures
    if cache:report['render_cache']=dict(cache.stats)
    report["svg_sha256"] = __import__("hashlib").sha256(Path(args.svg).read_bytes()).hexdigest()
    if failures:
        report["quality_gate"] = "FAIL"
    if args.report:
        path = Path(args.report).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--svg", required=True)
    parser.add_argument("--report")
    parser.add_argument("--contact-sheet")
    parser.add_argument("--diff")
    parser.add_argument("--preview", help="Single figure preview; contact-sheet is QA only")
    parser.add_argument("--regions")
    parser.add_argument("--region-previews", help="Directory for source/output regional QA crops")
    parser.add_argument("--max-mae", type=float)
    parser.add_argument("--min-edge-f1", type=float)
    parser.add_argument('--cache-dir',type=Path)
    report = compare(parser.parse_args())
    return 1 if report.get("threshold_failures") else 0


if __name__ == "__main__":
    raise SystemExit(main())
