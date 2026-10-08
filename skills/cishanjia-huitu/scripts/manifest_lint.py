#!/usr/bin/env python3
"""Validate text manifest geometry/styles; spelling needs reference review."""
from __future__ import annotations
import argparse
import json
import math
import re
from pathlib import Path


def lint(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("manifest root must be an object")
    source = payload.get("source") or payload.get("canvas") or {}
    errors, warnings, seen = [], [], set()

    def number(raw, label):
        try:
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError("not finite")
            return value
        except (TypeError, ValueError):
            errors.append(f"{label}: expected a finite number")
            return None

    def box(raw, label):
        if not isinstance(raw, (list, tuple)) or len(raw) != 4:
            errors.append(f"{label}: expected [x,y,width,height]")
            return
        values = [number(value, label) for value in raw]
        if None in values:
            return
        x, y, w, h = values
        if w <= 0 or h <= 0:
            errors.append(f"{label}: non-positive size")
        if width and height and (x < 0 or y < 0 or x+w > width or y+h > height):
            errors.append(f"{label}: outside source canvas")

    def color(raw, label):
        if not isinstance(raw, str) or not re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", raw):
            errors.append(f"{label}: expected #RGB or #RRGGBB")

    width = number(source.get("width_px", source.get("width")), "source width")
    height = number(source.get("height_px", source.get("height")), "source height")
    if (width is not None and width <= 0) or (height is not None and height <= 0):
        errors.append("source dimensions must be positive")
    entries = payload.get("text_elements", payload.get("objects", []))
    if not isinstance(entries, list):
        errors.append("text_elements must be a list")
        entries = []
    if not entries:
        warnings.append("no live text entries; valid only for a text-free reference")
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            errors.append(f"entry {index}: expected object")
            continue
        name = entry.get("id")
        label = name or f"entry {index}"
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{label}: id required")
        elif name in seen:
            errors.append(f"duplicate id: {name}")
        else:
            seen.add(name)
        content = entry.get("content")
        if 'style_group' in entry and (not isinstance(entry['style_group'],str) or not entry['style_group'].strip()):
            errors.append(f"{label}: style_group must be a nonempty string")
        if not isinstance(content, str) or not content.strip():
            errors.append(f"{label}: non-empty content string required")
            content = ""
        raw_box = entry.get("bbox_px", entry.get("bbox"))
        if raw_box is None:
            warnings.append(f"{label}: no bbox for text cleanup")
        else:
            box(raw_box, f"{label} bbox")
        if "x" in entry or "y" in entry:
            x, y = number(entry.get("x"), f"{label} x"), number(entry.get("y"), f"{label} y")
            if x is not None and y is not None:
                if entry.get("coordinate_space") == "normalized":
                    x, y = x * (width or 1), y * (height or 1)
                if width and height and (not 0 <= x <= width or not 0 <= y <= height):
                    errors.append(f"{label}: baseline outside canvas")
        else:
            warnings.append(f"{label}: bbox-derived baseline requires visual review")
        size_raw = entry.get("source_font_size_px", entry.get("source_font_size_pt", entry.get("font_size", 16)))
        size = number(size_raw, f"{label} font size")
        if size is not None:
            if "source_font_size_px" not in entry and "source_font_size_pt" not in entry and entry.get("font_size_space") == "normalized":
                size *= height or 1
            if size <= 0 or (height and size > height):
                errors.append(f"{label}: implausible font size")
        if "source_font_size_pt" in entry:
            warnings.append(f"{label}: legacy source_font_size_pt treated as source pixels; prefer source_font_size_px")
        color(entry.get("fill", entry.get("color", "#111111")), f"{label} fill")
        if entry.get("text_anchor", entry.get("alignment", "middle")) not in {"start", "middle", "end"}:
            errors.append(f"{label}: text_anchor must be start/middle/end")
        if entry.get("font_style", "normal") not in {"normal", "italic", "oblique"}:
            errors.append(f"{label}: invalid font_style")
        for attr, low, high in (("opacity", 0, 1), ("line_height", 0.1, 10), ("horizontal_scale", 0.1, 10), ("mask_threshold", 0, 442), ("mask_dilation", 0, 4)):
            if attr in entry:
                value = number(entry[attr], f"{label} {attr}")
                if value is not None and not low <= value <= high:
                    errors.append(f"{label}: {attr} outside {low}..{high}")
        for attr in ("rotation", "paint_order", "z_index"):
            if attr in entry:
                number(entry[attr], f"{label} {attr}")
        mode = str(entry.get("mask_mode", "glyphs")).lower()
        if mode not in {"glyphs", "manual", "none", "off", "false"}:
            errors.append(f"{label}: unsupported mask_mode")
        if mode == "manual":
            raw_path = entry.get("mask_path")
            if not isinstance(raw_path, str) or not raw_path:
                errors.append(f"{label}: manual mask_path required")
            elif not (path.parent / raw_path).is_file():
                errors.append(f"{label}: local mask file missing")
        for raw in entry.get("protect_regions", []):
            box(raw, f"{label} protect_region")
        colors = entry.get("mask_colors", [])
        if not isinstance(colors, list):
            errors.append(f"{label}: mask_colors must be a list")
        else:
            for value in colors:
                color(value, f"{label} mask color")
        if "mask_color" in entry:
            color(entry["mask_color"], f"{label} mask_color")
        styles = entry.get("line_styles", [])
        if not isinstance(styles, list) or any(not isinstance(item, dict) for item in styles):
            errors.append(f"{label}: line_styles must be a list of objects")
        else:
            if len(styles) > len(content.splitlines()):
                errors.append(f"{label}: more line_styles than lines")
            for item in styles:
                if "fill" in item:
                    color(item["fill"], f"{label} line fill")
    return {"schema_version": "2.0", "file": str(path.resolve()), "status": "PASS" if not errors else "FAIL",
            "entry_count": len(entries), "unique_id_count": len(seen), "errors": errors, "warnings": warnings,
            "spelling_verified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = lint(args.manifest.resolve(strict=True))
    except Exception as exc:
        report = {"status": "FAIL", "errors": [str(exc)]}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
