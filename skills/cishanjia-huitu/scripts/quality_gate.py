#!/usr/bin/env python3
"""Bind comparison metrics and an explicit visual review to a master SVG."""
from __future__ import annotations
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from svg_contract import validate
from object_groups import audit,SCHEMA

CHECKS = ("text", "connections", "critical_objects", "background", "single_figure", "object_editability", "vector_construction", "connector_isolation", "shape_editability")


def build(svg: Path, comparison: Path, review: Path, require_object_groups: bool=True, drawing_plan: Path|None=None,cache=None) -> dict:
    digest = hashlib.sha256(svg.read_bytes()).hexdigest()
    root=ET.parse(svg).getroot();validate(root)
    grouping=audit(root) if root.get('data-huitu-grouping')==SCHEMA else None
    metrics = json.loads(comparison.read_text(encoding="utf-8-sig"))
    visual = json.loads(review.read_text(encoding="utf-8-sig"))
    if not isinstance(metrics, dict) or not isinstance(visual, dict):
        raise ValueError("comparison and visual review must be JSON objects")
    errors = []
    construction=None
    plan_value=drawing_plan or visual.get('drawing_plan')
    if not plan_value:errors.append('Authored vector drawing plan required; no screenshot/mesh final fallback')
    else:
        plan_path=Path(plan_value)
        if not plan_path.is_absolute():plan_path=review.parent/plan_path
        try:
            from redraw_audit import audit as redraw_audit
            construction=redraw_audit(svg,plan_path,cache=cache)
            if construction['status']!='PASS':errors.extend(construction['errors'])
        except (ValueError,OSError) as error:errors.append('Redraw audit failed: '+str(error))
    if require_object_groups and grouping is None:errors.append('Complete movable semantic object groups required')
    if grouping and grouping['status']!='PASS':errors.extend(grouping['errors'])
    if metrics.get("svg_sha256") != digest or visual.get("svg_sha256") != digest:
        errors.append("comparison/review belongs to a different SVG")
    if metrics.get("threshold_failures") or metrics.get("quality_gate") == "FAIL":
        errors.append("comparison threshold failure remains")
    if not isinstance(visual.get("checks"), dict):
        errors.append("visual review checks required")
    else:
        for check in CHECKS:
            item = visual["checks"].get(check)
            if not isinstance(item, dict) or item.get("status") != "pass" or not isinstance(item.get("evidence"), str) or not item["evidence"].strip():
                errors.append(f"visual check missing or unresolved: {check}")
    if visual.get("unresolved_issues") != []:
        errors.append("unresolved_issues must be explicitly empty")
    reviewed = visual.get("regions", {})
    if not isinstance(reviewed, dict):
        errors.append("reviewed regions must be an object")
        reviewed = {}
    for region in metrics.get("regions", []):
        if region.get("critical") and reviewed.get(region.get("id")) != "pass":
            errors.append(f"critical region not reviewed: {region.get('id')}")
    return {
        "schema_version": 1, "status": "FAIL" if errors else "PASS", "svg_sha256": digest,
        "created_at": datetime.now(timezone.utc).isoformat(), "errors": errors,
        "comparison": str(comparison.resolve()), "visual_review": str(review.resolve()),
        "construction":construction['schema'] if construction and construction['status']=='PASS' else 'unverified',
        "drawing_plan_sha256":construction.get('drawing_plan_sha256') if construction else None,
        "connector_geometry_passed":bool(construction and construction['status']=='PASS' and construction['connector_geometry_passed']),
        "object_grouping":SCHEMA if grouping else 'flat-legacy',"object_count":len(grouping['objects']) if grouping else 0,
        "meaning": "Internal reviewed-result gate, not automatic proof of Cell-LCT equivalence",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg", required=True, type=Path)
    parser.add_argument("--comparison", required=True, type=Path)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument('--drawing-plan',type=Path)
    parser.add_argument('--cache-dir',type=Path)
    parser.add_argument("--allow-flat-legacy",action="store_true",help="Only for explicit acceptance of legacy fragmented editing")
    args = parser.parse_args()
    from render_cache import from_directory
    cache=from_directory(args.cache_dir)
    report = build(args.svg, args.comparison, args.review,not args.allow_flat_legacy,args.drawing_plan,cache)
    if cache:report['render_cache']=dict(cache.stats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if report["status"] == "PASS" else 1)
