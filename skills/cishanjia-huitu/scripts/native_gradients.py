"""Create one editable native paint instead of many opacity-layer fragments."""
import re
import xml.etree.ElementTree as ET
from svg_contract import local_name

def gradient(root,ident,stops,kind='radial',**geometry):
    if kind not in {'radial','linear'} or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*',ident):
        raise ValueError('Native gradient needs a supported type and stable ID')
    if any(n.get('id')==ident for n in root.iter()):raise ValueError('Duplicate gradient ID')
    defs=next((n for n in root if local_name(n.tag)=='defs'),None)
    if defs is None:defs=ET.Element('defs');root.insert(0,defs)
    node=ET.SubElement(defs,kind+'Gradient',{'id':ident,**{k:str(v) for k,v in geometry.items()}})
    for offset,color,opacity in stops:
        ET.SubElement(node,'stop',{'offset':str(offset),'stop-color':color,'stop-opacity':str(opacity)})
    return 'url(#'+ident+')'

def halo_gradient(root,ident,color,peak=1):
    # Broad soft plateau with a transparent edge, source-adaptable.
    radii=[0,.25,.4,.55,.7,.82,.92,1]
    return gradient(root,ident,[(r,color,peak*(1-r**4)**2) for r in radii],cx='.5',cy='.5',r='.5')
