"""Editable local SVG with owned shapes, live text and native gradients."""
from __future__ import annotations
import math
import re
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
DRAWABLE = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text"}
CONTAINERS = {"svg", "g", "a", "switch"}
INFO = {"title", "desc", "metadata"}
RESOURCES = {"defs", "linearGradient", "radialGradient", "stop"}
GRADIENTS = {"linearGradient", "radialGradient"}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def view_box(root: ET.Element) -> list[float]:
    raw = root.get("viewBox")
    if not raw:
        raw = f"0 0 {root.get('width', '')} {root.get('height', '')}"
    values = [float(value) for value in re.split(r"[\s,]+", raw.strip())]
    if len(values) != 4 or not all(math.isfinite(value) for value in values) or values[2] <= 0 or values[3] <= 0:
        raise ValueError("finite positive viewBox required")
    return values


def validate(root: ET.Element, require_ids: bool = True) -> None:
    if local_name(root.tag) != "svg":
        raise ValueError("root must be svg")
    view_box(root)
    ids = set()
    gradients = {n.get('id') for n in root.iter() if local_name(n.tag) in GRADIENTS}
    parents = {child:parent for parent in root.iter() for child in parent}
    for element in root.iter():
        tag = local_name(element.tag)
        if tag not in DRAWABLE | CONTAINERS | INFO | RESOURCES:
            raise ValueError(f"unsupported editable SVG node: {tag}")
        if tag == 'defs' and (parents.get(element) is not root or any(local_name(n.tag) not in GRADIENTS for n in element)):
            raise ValueError('Only root-level native gradient definitions are supported')
        if tag in GRADIENTS:
            if not element.get('id') or local_name(parents.get(element, root).tag) != 'defs':
                raise ValueError('Native gradients need a stable ID inside defs')
            if not list(element) or any(local_name(n.tag) != 'stop' for n in element):
                raise ValueError('Gradient must contain color stops only')
            if element.get('gradientUnits','objectBoundingBox') not in {'objectBoundingBox','userSpaceOnUse'}:
                raise ValueError('Unsupported gradient coordinate units')
            offsets=[]
            for stop in element:
                raw=stop.get('offset','')
                try: offset=float(raw[:-1])/100 if raw.endswith('%') else float(raw)
                except ValueError: raise ValueError('Finite gradient stop offset required')
                if not math.isfinite(offset) or not 0 <= offset <= 1: raise ValueError('Gradient stop offset outside 0..1')
                offsets.append(offset)
                opacity=float(stop.get('stop-opacity','1'))
                if not math.isfinite(opacity) or not 0 <= opacity <= 1: raise ValueError('Gradient stop opacity outside 0..1')
                if not re.fullmatch(r'#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?',stop.get('stop-color','')):
                    raise ValueError('Explicit hexadecimal gradient color required')
            if offsets != sorted(offsets): raise ValueError('Gradient stops must be ordered')
        if tag == 'stop' and local_name(parents.get(element,root).tag) not in GRADIENTS:
            raise ValueError('Color stop outside a gradient')
        for key, value in element.attrib.items():
            if local_name(key).lower().startswith("on") or local_name(key).lower().endswith("href"):
                raise ValueError("linked resources and event handlers are unsupported")
            if "url(" in value.lower():
                match=re.fullmatch(r'url\(#([A-Za-z_][A-Za-z0-9_.-]*)\)',value)
                if tag not in DRAWABLE or key not in {'fill','stroke'} or not match or match[1] not in gradients:
                    raise ValueError('Only internal native gradient paint references are supported')
            if key in {"class", "filter", "mask", "clip-path"}:
                raise ValueError(f"unsupported SVG attribute: {key}")
            if key not in {"id", "font-family"} and re.search(r"(?<![A-Za-z])(?:nan|[-+]?infinity)(?![A-Za-z])", value, re.I):
                raise ValueError("non-finite SVG geometry")
        ident = element.get("id")
        if require_ids and tag in DRAWABLE and not ident:
            raise ValueError("drawable without stable id")
        if ident:
            if ident in ids:
                raise ValueError(f"duplicate SVG id: {ident}")
            ids.add(ident)
        if tag == "path" and not element.get("d", "").strip():
            raise ValueError("empty path")
        if tag == "text" and list(element):
            raise ValueError("text must contain a single live text run")
