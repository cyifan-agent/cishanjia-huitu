#!/usr/bin/env python3
"""Compose a semantic scientific-figure manifest into editable SVG.

The manifest is intentionally small and explicit. It lets local reconstruction
use named scientific primitives for complex figures instead of trusting a
single color-contour pass to infer all semantics.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def style(obj: dict[str, Any]) -> str:
    attrs = []
    for key, default in (("fill", "none"), ("stroke", "none"), ("stroke_width", 1), ("opacity", 1)):
        value = obj.get(key, default)
        attr = {"stroke_width": "stroke-width"}.get(key, key)
        attrs.append(f'{attr}="{esc(value)}"')
    attrs.append(f'stroke-linecap="{esc(obj.get("linecap", "round"))}"')
    attrs.append(f'stroke-linejoin="{esc(obj.get("linejoin", "round"))}"')
    return " ".join(attrs)


def point_list(points: list[list[float]]) -> str:
    return " ".join(f"{float(x):.2f},{float(y):.2f}" for x, y in points)


def polyline_path(points: list[list[float]]) -> str:
    if not points:
        return ""
    return "M " + " L ".join(f"{float(x):.2f} {float(y):.2f}" for x, y in points)


def arrow_head(x1: float, y1: float, x2: float, y2: float, size: float) -> list[list[float]]:
    angle = math.atan2(y2 - y1, x2 - x1)
    left = angle + math.pi * 0.82
    right = angle - math.pi * 0.82
    return [[x2, y2], [x2 + math.cos(left) * size, y2 + math.sin(left) * size], [x2 + math.cos(right) * size, y2 + math.sin(right) * size]]


def dna_parts(obj: dict[str, Any], ident: str) -> list[str]:
    x, y, w, h = [float(obj.get(key, 0)) for key in ("x", "y", "width", "height")]
    stroke = esc(obj.get("stroke", "#1473C9"))
    width = esc(obj.get("stroke_width", 2))
    parts = []
    steps = max(8, int(obj.get("steps", 18)))
    left, right = [], []
    for i in range(steps + 1):
        t = i / steps
        xx = x + w * t
        phase = math.sin(t * math.pi * 2 * float(obj.get("turns", 1.5)))
        left.append([xx, y + h * (0.5 + 0.36 * phase)])
        right.append([xx, y + h * (0.5 - 0.36 * phase)])
    parts.append(f'<path id="{ident}-left" d="{polyline_path(left)}" fill="none" stroke="{stroke}" stroke-width="{width}"/>')
    parts.append(f'<path id="{ident}-right" d="{polyline_path(right)}" fill="none" stroke="{stroke}" stroke-width="{width}"/>')
    for i in range(1, steps):
        t = i / steps
        xx = x + w * t
        phase = math.sin(t * math.pi * 2 * float(obj.get("turns", 1.5)))
        y1, y2 = y + h * (0.5 + 0.36 * phase), y + h * (0.5 - 0.36 * phase)
        parts.append(f'<line id="{ident}-rung-{i:02d}" x1="{xx:.2f}" y1="{y1:.2f}" x2="{xx:.2f}" y2="{y2:.2f}" stroke="{stroke}" stroke-width="{max(1, float(obj.get("stroke_width", 2)) * 0.7):.2f}"/>')
    return parts


def mitochondrion_parts(obj: dict[str, Any], ident: str) -> list[str]:
    x, y, w, h = [float(obj.get(key, 0)) for key in ("x", "y", "width", "height")]
    fill, stroke = esc(obj.get("fill", "#F79B87")), esc(obj.get("stroke", "#D64336"))
    parts = [f'<ellipse id="{ident}-outer" cx="{x + w / 2:.2f}" cy="{y + h / 2:.2f}" rx="{w / 2:.2f}" ry="{h / 2:.2f}" fill="{fill}" stroke="{stroke}" stroke-width="{esc(obj.get("stroke_width", 2))}"/>']
    waves = max(2, int(obj.get("waves", 4)))
    for wave in range(waves):
        yy = y + h * (0.2 + wave * 0.2)
        points = []
        for i in range(17):
            xx = x + w * (0.17 + i * 0.041)
            points.append([xx, yy + math.sin(i * math.pi * 0.9 + wave) * h * 0.075])
        parts.append(f'<path id="{ident}-crista-{wave:02d}" d="{polyline_path(points)}" fill="none" stroke="{stroke}" stroke-width="{max(1, float(obj.get("stroke_width", 2)) * 0.8):.2f}"/>')
    return parts


def bead_chain_parts(obj: dict[str, Any], ident: str) -> list[str]:
    points = obj.get("points", [])
    if not points:
        return []
    parts = [f'<path id="{ident}-backbone" d="{polyline_path(points)}" fill="none" stroke="{esc(obj.get("stroke", "#E10000"))}" stroke-width="{esc(obj.get("stroke_width", 2))}"/>']
    radius = float(obj.get("radius", 6))
    for index, point in enumerate(points):
        parts.append(f'<circle id="{ident}-bead-{index:03d}" cx="{float(point[0]):.2f}" cy="{float(point[1]):.2f}" r="{radius:.2f}" fill="{esc(obj.get("fill", "#FF5B5B"))}" stroke="{esc(obj.get("stroke", "#C40000"))}" stroke-width="{esc(obj.get("stroke_width", 1))}"/>')
    return parts


def soft_glow_parts(obj: dict[str, Any], ident: str) -> list[str]:
    """Editable nested ellipses approximate a smooth glow without SVG filters."""
    cx, cy, rx, ry = [float(obj.get(key, 0)) for key in ("cx", "cy", "rx", "ry")]
    if rx <= 0 or ry <= 0:
        raise ValueError("soft_glow needs positive rx/ry")
    layers = max(8, min(128, int(obj.get("layers", 48))))
    peak = float(obj.get("opacity", 0.3))
    if not 0 <= peak < 1:
        raise ValueError("soft_glow opacity must be >=0 and <1")
    color = esc(obj.get("fill", "#8AD667"))
    parts, cumulative = [], 0.0
    for index in range(layers):
        fraction = 1.0 - index / layers
        target = peak * math.exp(-4.0 * fraction * fraction)
        alpha = (target - cumulative) / max(1e-9, 1.0 - cumulative)
        cumulative = target
        parts.append(f'<ellipse id="{esc(ident)}-layer-{index:03d}" cx="{cx:.3f}" cy="{cy:.3f}" rx="{rx*fraction:.3f}" ry="{ry*fraction:.3f}" fill="{color}" stroke="none" opacity="{alpha:.6f}"/>')
    return parts


def curved_arrow_parts(obj: dict[str, Any], ident: str) -> list[str]:
    """Cubic connector and expanded dashes; no unsupported dash-array."""
    if 'branches' in obj:
        branches=obj['branches']
        if not isinstance(branches,list) or not branches:raise ValueError('Explicit connector branch routes required')
        parts=[];endpoints=[]
        for index,branch in enumerate(branches):
            if not isinstance(branch,dict) or 'branches' in branch or branch.get('termination') not in {'arrow','inhibition','none'}:raise ValueError('Declare each branch end marker')
            route={k:v for k,v in obj.items() if k not in {'branches','points','segments'}};route.update(branch)
            parts.extend(curved_arrow_parts(route,ident+'-b'+str(index)))
            points=route.get('segments')
            endpoints.append([points[0][0],points[-1][-1]] if points else [route['points'][0],route['points'][-1]])
        connected={0}
        for _ in branches:
            connected.update(i for i,a in enumerate(endpoints) if any(any(math.dist(p,q)<1e-6 for p in a for q in endpoints[j]) for j in tuple(connected)))
        if len(connected)!=len(branches):raise ValueError('Branch routes must share endpoint junctions')
        return parts
    if 'segments' in obj:
        segments=obj['segments']
        if not isinstance(segments,list) or not segments:raise ValueError('Explicit connected cubic segments required')
        parts=[];previous=None
        for index,points in enumerate(segments):
            if not isinstance(points,list) or len(points)!=4 or any(not isinstance(p,list) or len(p)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in p) for p in points):raise ValueError('Four finite controls per segment required')
            if previous is not None and math.dist(previous,points[0])>1e-6:raise ValueError('Connector segments must join')
            previous=points[-1]
            segment={k:v for k,v in obj.items() if k!='segments'};segment['points']=points
            if index<len(segments)-1:segment['termination']='none'
            parts.extend(curved_arrow_parts(segment,ident+'-s'+str(index)))
        return parts
    points = obj.get("points", [])
    if len(points) != 4:
        raise ValueError("curved_arrow points require [start,control1,control2,end]")
    p0, p1, p2, p3 = [[float(x), float(y)] for x, y in points]
    color = esc(obj.get("stroke", "#777777"))
    sw = float(obj.get("stroke_width", 3))
    opacity = float(obj.get("opacity", 1))
    parts = []
    if obj.get("dashed"):
        # Sample cubic by arc length. Dashes keep almost constant physical
        # length along the curve, unlike equal parametric intervals.
        sampled = []
        for index in range(401):
            t, u = index/400, 1-index/400
            sampled.append([u**3*p0[k]+3*u*u*t*p1[k]+3*u*t*t*p2[k]+t**3*p3[k] for k in (0, 1)])
        dash, gap = float(obj.get("dash", 10)), float(obj.get("gap", 7))
        if dash <= 0 or gap <= 0:
            raise ValueError("positive dash/gap required")
        active, collected, length, previous = True, [sampled[0]], 0.0, sampled[0]
        segment_index = 0
        for point in sampled[1:]:
            step = math.hypot(point[0]-previous[0], point[1]-previous[1])
            length += step
            if active:
                collected.append(point)
            if length >= (dash if active else gap):
                if active and len(collected) > 1:
                    parts.append(f'<path id="{esc(ident)}-dash-{segment_index:03d}" d="{polyline_path(collected)}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" opacity="{opacity}"/>')
                    segment_index += 1
                active = not active
                length = 0.0
                collected = [point] if active else []
            previous = point
        if active and len(collected) > 1:
            parts.append(f'<path id="{esc(ident)}-dash-{segment_index:03d}" d="{polyline_path(collected)}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" opacity="{opacity}"/>')
    else:
        d = f"M {p0[0]} {p0[1]} C {p1[0]} {p1[1]} {p2[0]} {p2[1]} {p3[0]} {p3[1]}"
        parts.append(f'<path id="{esc(ident)}-shaft" d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" opacity="{opacity}"/>')
    termination=obj.get('termination','arrow')
    if termination=='arrow':
        size=float(obj.get('head',14))
        if obj.get('head_style','triangle')=='stealth':
            length=float(obj.get('head_length',size));width=float(obj.get('head_width',size*.8));inset=float(obj.get('head_inset',size*.27))
            if any(not math.isfinite(v) for v in (length,width,inset)) or length<=0 or width<=0 or not 0<=inset<length:raise ValueError('Finite stealth marker dimensions and valid inset required')
            dx,dy=p3[0]-p2[0],p3[1]-p2[1];norm=math.hypot(dx,dy)
            if norm<1e-9:dx,dy=p3[0]-p0[0],p3[1]-p0[1];norm=math.hypot(dx,dy)
            if norm<1e-9:raise ValueError('Arrowhead needs nonzero terminal tangent')
            ux,uy=dx/norm,dy/norm;nx,ny=-uy,ux
            head=[p3,[p3[0]-ux*length+nx*width/2,p3[1]-uy*length+ny*width/2],[p3[0]-ux*(length-inset),p3[1]-uy*(length-inset)],[p3[0]-ux*length-nx*width/2,p3[1]-uy*length-ny*width/2]]
        elif obj.get('head_style','triangle')=='triangle':head=arrow_head(p2[0],p2[1],p3[0],p3[1],size)
        else:raise ValueError('Unsupported arrowhead style')
        parts.append(f'<polygon id="{esc(ident)}-head" points="{point_list(head)}" fill="{color}" opacity="{opacity}" stroke="none"/>')
    elif termination=='inhibition':
        dx,dy=p3[0]-p2[0],p3[1]-p2[1];length=math.hypot(dx,dy)
        if length<1e-9:dx,dy=p3[0]-p0[0],p3[1]-p0[1];length=math.hypot(dx,dy)
        if length<1e-9:raise ValueError('Inhibition cap needs a nonzero terminal tangent')
        half=float(obj.get('cap_width',18))/2
        if half<=0:raise ValueError('Positive inhibition cap_width required')
        ux,uy=-dy/length*half,dx/length*half
        parts.append(f'<line id="{esc(ident)}-cap" x1="{p3[0]-ux:.4f}" y1="{p3[1]-uy:.4f}" x2="{p3[0]+ux:.4f}" y2="{p3[1]+uy:.4f}" stroke="{color}" stroke-width="{sw}" opacity="{opacity}" stroke-linecap="butt"/>')
    elif termination!='none':raise ValueError('Unsupported connector termination')
    return parts


def text_part(obj: dict[str, Any], ident: str) -> str:
    x, y = float(obj.get("x", 0)), float(obj.get("y", 0))
    size = float(obj.get("font_size", 18))
    attrs = f'id="{ident}" x="{x:.2f}" y="{y:.2f}" fill="{esc(obj.get("fill", "#111111"))}" font-family="{esc(obj.get("font_family", "Arial"))}" font-size="{size:.2f}px" font-weight="{esc(obj.get("font_weight", "normal"))}" text-anchor="{esc(obj.get("text_anchor", "start"))}" opacity="{esc(obj.get("opacity", 1))}"'
    lines = str(obj.get("content", "")).splitlines() or [""]
    if len(lines) == 1:
        return f'<text {attrs}>{esc(lines[0])}</text>'
    line_height = size * float(obj.get("line_height", 1.2))
    text_lines = []
    for index, line in enumerate(lines):
        line_id = ident if index == 0 else f"{ident}-line-{index:02d}"
        line_y = y + index * line_height
        line_attrs = attrs.replace(f'id="{ident}"', f'id="{line_id}"').replace(f'y="{y:.2f}"', f'y="{line_y:.2f}"')
        text_lines.append(f'<text {line_attrs}>{esc(line)}</text>')
    return "".join(text_lines)


def render_object(obj: dict[str, Any]) -> list[str]:
    ident = str(obj.get("id", "object"))
    kind = str(obj.get("type", "rect"))
    if kind == "text":
        return [text_part(obj, ident)]
    if kind == "soft_glow":
        return soft_glow_parts(obj, ident)
    if kind == 'native_glow':
        paint=dict(obj,type='ellipse',fill='url(#'+ident+'-paint)',opacity=1,stroke='none')
        return render_object(paint)
    if kind == "curved_arrow":
        return curved_arrow_parts(obj, ident)
    if kind == "dna":
        return [f'<g id="{ident}">'] + dna_parts(obj, ident) + ["</g>"]
    if kind == "mitochondrion":
        return [f'<g id="{ident}">'] + mitochondrion_parts(obj, ident) + ["</g>"]
    if kind == "bead_chain":
        return [f'<g id="{ident}">'] + bead_chain_parts(obj, ident) + ["</g>"]
    if kind in {"rect", "rounded_rect"}:
        radius = float(obj.get("radius", 0 if kind == "rect" else 14))
        return [f'<rect id="{ident}" x="{float(obj.get("x", 0)):.2f}" y="{float(obj.get("y", 0)):.2f}" width="{float(obj.get("width", 0)):.2f}" height="{float(obj.get("height", 0)):.2f}" rx="{radius:.2f}" {style(obj)}/>']
    if kind == "ellipse":
        return [f'<ellipse id="{ident}" cx="{float(obj.get("cx", 0)):.2f}" cy="{float(obj.get("cy", 0)):.2f}" rx="{float(obj.get("rx", 0)):.2f}" ry="{float(obj.get("ry", 0)):.2f}" {style(obj)}/>']
    if kind == "line":
        return [f'<line id="{ident}" x1="{float(obj.get("x1", 0)):.2f}" y1="{float(obj.get("y1", 0)):.2f}" x2="{float(obj.get("x2", 0)):.2f}" y2="{float(obj.get("y2", 0)):.2f}" {style(obj)}/>']
    if kind == "arrow":
        x1, y1, x2, y2 = [float(obj.get(key, 0)) for key in ("x1", "y1", "x2", "y2")]
        head = arrow_head(x1, y1, x2, y2, float(obj.get("head", 12)))
        return [f'<g id="{ident}"><line id="{ident}-shaft" x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" {style(obj)}/><polygon id="{ident}-head" points="{point_list(head)}" fill="{esc(obj.get("stroke", "#E10000"))}" stroke="none"/></g>']
    if kind == "polygon":
        return [f'<polygon id="{ident}" points="{point_list(obj.get("points", []))}" {style(obj)}/>']
    if kind == "path":
        return [f'<path id="{ident}" d="{esc(obj.get("d", ""))}" {style(obj)}/>']
    raise ValueError(f"Unsupported scene object type: {kind}")


def compose(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    canvas = manifest.get("canvas", {})
    width, height = int(canvas.get("width", 1000)), int(canvas.get("height", 1000))
    objects = list(manifest.get("objects", []))
    objects.sort(key=lambda obj: float(obj.get("z", 0)))
    parts = [f'<?xml version="1.0" encoding="UTF-8"?>', f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    from native_gradients import gradient,halo_gradient
    resource_root=ET.Element('svg')
    for resource in manifest.get('gradients',[]):
        gradient(resource_root,resource['id'],resource['stops'],resource.get('kind','radial'),**resource.get('geometry',{}))
    for obj in objects:
        if obj.get('type')=='native_glow':halo_gradient(resource_root,obj['id']+'-paint',obj.get('fill','#8ad667'),obj.get('opacity',.3))
    if list(resource_root):parts.append(ET.tostring(resource_root[0],encoding='unicode'))
    for obj in objects:
        parts.extend(render_object(obj))
    parts.append("</svg>")
    rendered = "\n".join(parts)
    from svg_contract import validate
    validate(ET.fromstring(rendered))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return {"output": str(output), "width": width, "height": height, "objects": len(objects), "local_only": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).resolve().read_text(encoding="utf-8"))
    print(json.dumps(compose(manifest, Path(args.output).resolve()), ensure_ascii=False))


if __name__ == "__main__":
    main()
