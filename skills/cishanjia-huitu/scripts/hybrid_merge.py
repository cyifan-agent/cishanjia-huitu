#!/usr/bin/env python3
"""Merge editable correction layers, preserving canvas and root presentation."""
from __future__ import annotations
import argparse
import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from svg_contract import SVG_NS, DRAWABLE, INFO, validate, view_box, local_name

ET.register_namespace("", SVG_NS)


def merge(args: argparse.Namespace) -> dict:
    base_path = Path(args.base).resolve(strict=True)
    output = Path(args.output).resolve()
    if output == base_path or output in [Path(raw).resolve() for raw in args.overlay]:
        raise ValueError("write a new master SVG; never overwrite an input")
    tree = ET.parse(base_path)
    root = tree.getroot()
    validate(root)
    canvas = view_box(root)
    removed = []
    for ident in getattr(args, "remove_id", []) or []:
        found = False
        for parent in list(root.iter()):
            for node in list(parent):
                if node.get("id") == ident:
                    parent.remove(node)
                    found = True
                    break
        if not found:
            raise ValueError(f"replacement target absent: {ident}")
        removed.append(ident)
    ids = {node.get("id") for node in root.iter() if node.get("id")}
    count, paths = 0, []
    for index, raw in enumerate(args.overlay, 1):
        path = Path(raw).resolve(strict=True)
        overlay = ET.parse(path).getroot()
        validate(overlay)
        if any(abs(a-b) > 1e-6 for a, b in zip(canvas, view_box(overlay))):
            raise ValueError("overlay viewBox must match base canvas; do not guess coordinates")
        prefix = f"{args.overlay_prefix or 'overlay'}-{index:02d}"
        group_id = prefix
        while group_id in ids:
            group_id += "-x"
        ids.add(group_id)
        attrs = {key: value for key, value in overlay.attrib.items()
                 if local_name(key) not in {"id", "version", "width", "height", "viewBox", "preserveAspectRatio"}}
        attrs["id"] = group_id
        group = ET.Element(f"{{{SVG_NS}}}g", attrs)
        for child in overlay:
            if local_name(child.tag) in INFO or local_name(child.tag) == "defs":
                continue
            node = copy.deepcopy(child)
            for descendant in node.iter():
                ident = descendant.get("id")
                if ident or local_name(descendant.tag) in DRAWABLE:
                    new_id = f"{prefix}-{ident or 'element-' + str(count)}"
                    while new_id in ids:
                        new_id += "-x"
                    descendant.set("id", new_id)
                    ids.add(new_id)
                if local_name(descendant.tag) in DRAWABLE:
                    count += 1
            group.append(node)
        root.append(group)
        paths.append(str(path))
    validate(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output, encoding="utf-8", xml_declaration=True)
    report = {"base": str(base_path), "overlays": paths, "output": str(output),
              "overlay_drawables_appended": count, "replaced_base_ids": removed, "local_only": True}
    if args.report:
        Path(args.report).resolve().parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--overlay", required=True, nargs="+")
    parser.add_argument("--output", required=True)
    parser.add_argument("--overlay-prefix")
    parser.add_argument("--remove-id", action="append", default=[], help="Replace explicit base IDs, preserving original input")
    parser.add_argument("--report")
    print(json.dumps(merge(parser.parse_args()), ensure_ascii=False))
