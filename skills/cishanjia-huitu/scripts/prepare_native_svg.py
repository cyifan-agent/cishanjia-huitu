"""Separate strict local SVG graphics and canonical live text for native import."""
from __future__ import annotations
import argparse,copy,json,xml.etree.ElementTree as ET
from pathlib import Path
from svg_text_geometry import load_parser
from svg_contract import validate
from object_groups import audit,SCHEMA
import math

def explicit_rect_path(node):
    """Prevent Illustrator live-corner preferences from changing scaled shapes."""
    x=float(node.get('x','0'));y=float(node.get('y','0'));w=float(node.get('width','0'));h=float(node.get('height','0'))
    rx=float(node.get('rx',node.get('ry','0')));ry=float(node.get('ry',node.get('rx','0')))
    rx=max(0,min(rx,w/2));ry=max(0,min(ry,h/2));k=4*(math.sqrt(2)-1)/3
    if w<=0 or h<=0:raise ValueError('Positive native rectangle dimensions required')
    if not rx or not ry:d=f'M {x} {y} L {x+w} {y} L {x+w} {y+h} L {x} {y+h} Z'
    else:
        d=f'M {x+rx} {y} L {x+w-rx} {y} C {x+w-rx+k*rx} {y} {x+w} {y+ry-k*ry} {x+w} {y+ry} L {x+w} {y+h-ry} C {x+w} {y+h-ry+k*ry} {x+w-rx+k*rx} {y+h} {x+w-rx} {y+h} L {x+rx} {y+h} C {x+rx-k*rx} {y+h} {x} {y+h-ry+k*ry} {x} {y+h-ry} L {x} {y+ry} C {x} {y+ry-k*ry} {x+rx-k*rx} {y} {x+rx} {y} Z'
    node.tag=node.tag.rsplit('}',1)[0]+'}path' if '}' in node.tag else 'path'
    for key in ('x','y','width','height','rx','ry'):node.attrib.pop(key,None)
    node.set('d',d)

def prepare(source,graphics,labels):
    root=ET.parse(source).getroot();validate(root)
    grouped=root.get('data-huitu-grouping')==SCHEMA
    grouping=audit(root) if grouped else {'objects':[],'owners':{}}
    if grouped and grouping['status']!='PASS':raise ValueError('; '.join(grouping['errors']))
    text_root=copy.deepcopy(root)
    def prune(node,text_only):
        for child in list(node):
            kind=child.tag.rsplit('}',1)[-1]
            if kind in {'svg','g','a','switch'}:prune(child,text_only)
            elif (kind!='text') if text_only else (kind=='text'):node.remove(child)
    prune(text_root,True)
    atoms=load_parser().collect_atoms(text_root) if any(node.tag.rsplit('}',1)[-1]=='text' and ''.join(node.itertext()).strip() for node in text_root.iter()) else []
    records=[]
    for atom in atoms:
        if atom['kind']!='text':raise ValueError('Unexpected graphics in text-only tree')
        t=atom['text']
        records.append({'source_id':atom['sourceId'],'object_id':grouping['owners'].get(atom['sourceId']),
            'content':t['contents'],'family':t['fontFamily'],'weight':t['fontWeight'],'style':t['fontStyle'],
            'x':t['position'][0],'y':t['position'][1],'size':t['fontSize'],'horizontalScale':t['horizontalScale'],
            'color':t['fillColor'],'opacity':t['opacity'],'rotation':t['rotationDegrees'],
            'anchor':t['textAnchor'],'letterSpacing':t['letterSpacing']})
    prune(root,False)
    for node in root.iter():
        if node.tag.rsplit('}',1)[-1]=='rect':explicit_rect_path(node)
    carrier=ET.Element('{http://www.w3.org/2000/svg}g',{'id':'huitu-native-graphics-root'})
    for child in list(root):
        if child.tag.rsplit('}',1)[-1]=='defs':continue
        root.remove(child);carrier.append(child)
    root.append(carrier)
    ET.ElementTree(root).write(graphics,encoding='utf-8',xml_declaration=True)
    objects=[{k:o[k] for k in ('id','svg_id','name','kind','graphic_count','text_count')} for o in grouping['objects']]
    labels.write_text(json.dumps({'labels':records,'objects':objects,'grouping':SCHEMA if grouped else 'flat-legacy'},ensure_ascii=False,indent=2),encoding='utf-8')
    return len(records)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('input','graphics','labels'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();print(json.dumps({'live_text':prepare(a.input,a.graphics,a.labels)}))
