"""Check authored-vector construction and isolate every declared connector.

Checks are geometry/ownership evidence, not proof of anatomical fidelity.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,math,re,xml.etree.ElementTree as ET
from pathlib import Path
from runtime_env import bootstrap
bootstrap()
import cv2,numpy as np,resvg_py
from object_groups import audit as grouping_audit
from svg_contract import local_name,view_box,SVG_NS
from compose_scene import curved_arrow_parts
from render_cache import render_png,from_directory

SCHEMA='vector-redraw-v1'
ROLES={'shape','outline','detail','shading','highlight','text','shaft','dash','head','cap'}
ARROW_ROLES={'shaft','dash','head','cap'}
# The mesh helper's compact rectangle encoding, detected even after ID renaming.
TILE=re.compile(r'M\s*([-+\d.eE]+)[ ,]+([-+\d.eE]+)\s*h\s*([-+\d.eE]+)\s*v\s*([-+\d.eE]+)\s*h\s*([-+\d.eE]+)\s*Z',re.I)

def rendered_alpha(root,cache=None):
    payload=render_png(ET.tostring(root,encoding='unicode'),cache=cache)
    image=cv2.imdecode(np.frombuffer(payload,np.uint8),cv2.IMREAD_UNCHANGED)
    return image[:,:,3] if image.shape[2]==4 else np.full(image.shape[:2],255,np.uint8)

def isolated(root,group):
    result=ET.Element(root.tag,dict(root.attrib))
    for child in root:
        if local_name(child.tag)=='defs':result.append(copy.deepcopy(child))
    result.append(copy.deepcopy(group));return result

def connector_expected(root,spec):
    data=spec.get('connector')
    if not isinstance(data,dict):raise ValueError('Connector needs an explicit planned route')
    if 'branches' in data:
        branches=data['branches']
        if not isinstance(branches,list) or not branches:raise ValueError('Explicit connected branch routes required')
        for branch in branches:
            if not isinstance(branch,dict) or 'branches' in branch:raise ValueError('Flat connector branch declarations required')
            single={k:v for k,v in data.items() if k not in {'branches','points','segments'}};single.update(branch)
            connector_expected(root,{'id':spec['id'],'connector':single})
        result=ET.Element(root.tag,dict(root.attrib))
        for child in root:
            if local_name(child.tag)=='defs':result.append(copy.deepcopy(child))
        result.append(ET.fromstring('<g xmlns="'+SVG_NS+'">'+''.join(curved_arrow_parts(data,spec['id']+'-expected'))+'</g>'))
        return result
    if 'segments' in data:
        segments=data['segments']
        if not isinstance(segments,list) or not segments:raise ValueError('Connector requires connected cubic segments')
        for segment in segments:
            single=dict(data);single.pop('segments');single['points']=segment
            connector_expected(root,{'id':spec['id'],'connector':single})
        result=ET.Element(root.tag,dict(root.attrib))
        for child in root:
            if local_name(child.tag)=='defs':result.append(copy.deepcopy(child))
        result.append(ET.fromstring('<g xmlns="'+SVG_NS+'">'+''.join(curved_arrow_parts(data,spec['id']+'-expected'))+'</g>'))
        return result
    points=data.get('points')
    if not isinstance(points,list) or len(points)!=4 or any(not isinstance(p,list) or len(p)!=2 or any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in p) for p in points):
        raise ValueError('Route requires four finite cubic control points')
    width=data.get('stroke_width')
    if not isinstance(width,(int,float)) or not math.isfinite(width) or width<=0:raise ValueError('Positive connector stroke_width required')
    if data.get('termination') not in {'arrow','inhibition','none'}:raise ValueError('Declare arrow/inhibition/none termination')
    result=ET.Element(root.tag,dict(root.attrib))
    for child in root:
        if local_name(child.tag)=='defs':result.append(copy.deepcopy(child))
    nodes=ET.fromstring('<g xmlns="'+SVG_NS+'">'+''.join(curved_arrow_parts(data,spec['id']+'-expected'))+'</g>')
    result.append(nodes);return result

def audit(svg:Path,plan:Path,artifacts:Path|None=None,cache=None):
    root=ET.parse(svg).getroot();structure=grouping_audit(root)
    errors=list(structure['errors']);records=[]
    data=json.loads(plan.read_text(encoding='utf-8-sig'))
    if data.get('schema')!=SCHEMA:errors.append('Authored vector drawing-plan schema required')
    if root.get('data-huitu-build')!=SCHEMA:errors.append('Master is not declared as an authored vector redraw')
    if any(n.get('data-huitu-build') in {'source-color-mesh','auto-trace-draft'} for n in root.iter()):
        errors.append('Diagnostic source mesh/whole-image trace cannot be final artwork')
    vb=view_box(root)
    if vb[:2]!=[0,0] or data.get('canvas')!=vb[2:]:errors.append('Drawing plan canvas must match source-pixel viewBox')
    entries=data.get('objects',[])
    if not isinstance(entries,list):raise ValueError('Drawing plan objects must be a list')
    declared={}
    for entry in entries:
        if not isinstance(entry,dict) or not isinstance(entry.get('id'),str):errors.append('Invalid planned object');continue
        if entry['id'] in declared:errors.append('Duplicate planned object: '+entry['id'])
        declared[entry['id']]=entry
    groups={n.get('data-huitu-object-id'):n for n in root if n.get('data-huitu-object-id')}
    if set(declared)!=set(groups):errors.append('Plan must declare exactly all final object groups')
    for obj in structure['objects']:
        ident=obj['id'];spec=declared.get(ident)
        if not spec:continue
        group=groups[ident];nodes={n.get('id'):n for n in group.iter() if local_name(n.tag) in {'path','rect','ellipse','circle','polygon','polyline','line','text'}}
        if spec.get('construction') not in {'authored','curve-refit'}:errors.append('Non-drawing construction: '+ident)
        features=spec.get('reference_features')
        if not isinstance(features,list) or not features or any(not isinstance(v,str) or not v.strip() for v in features):errors.append('Source-specific feature checklist required: '+ident)
        parts=spec.get('parts',[])
        if not isinstance(parts,list):errors.append('Explicit vector parts required: '+ident);continue
        by_id={}
        for part in parts:
            if not isinstance(part,dict) or part.get('role') not in ROLES or not isinstance(part.get('id'),str):errors.append('Invalid vector part role: '+ident);continue
            if part['id'] in by_id:errors.append('Duplicate vector part: '+part['id'])
            by_id[part['id']]=part
        if set(by_id)!=set(nodes):errors.append('Planned parts do not match actual object contents: '+ident)
        small_tiles=0;tiles=0
        for node in nodes.values():
            if local_name(node.tag)=='rect':
                try:rw,rh=float(node.get('width','0')),float(node.get('height','0'))
                except ValueError:continue
                tiles+=1;small_tiles+=int(rw>0 and rh>0 and max(rw,rh)<=2)
            for match in TILE.finditer(node.get('d','')):
                rw,rh=abs(float(match[3])),abs(float(match[4]));tiles+=1;small_tiles+=int(max(rw,rh)<=2)
        if small_tiles>=64 and small_tiles/max(1,tiles)>.8:errors.append('Dense source-resolution pixel tiles: '+ident)
        if obj['kind']!='connector':continue
        start_errors=len(errors)
        if obj['text_count']:errors.append('Connector must not contain neighboring text/captions: '+ident)
        if any(local_name(n.tag) not in {'g','path','line','polyline','polygon'} for n in group.iter()):errors.append('Connector contains a foreign object shape: '+ident)
        if any(p.get('role') not in ARROW_ROLES for p in by_id.values()):errors.append('Connector owns a non-arrow part: '+ident)
        record={'id':ident,'status':'FAIL','route_check':'not-run'}
        try:
            expected_root=connector_expected(root,spec)
            actual_root=isolated(root,group)
            actual=rendered_alpha(actual_root,cache)>8;expected=rendered_alpha(expected_root,cache)>8
            if not actual.any() or not expected.any():raise ValueError('Connector is empty or outside canvas')
            # Two source pixels allow native antialiasing and modest curve refits.
            distance=cv2.distanceTransform((~expected).astype(np.uint8),cv2.DIST_L2,cv2.DIST_MASK_PRECISE)
            reverse=cv2.distanceTransform((~actual).astype(np.uint8),cv2.DIST_L2,cv2.DIST_MASK_PRECISE)
            foreign=int((actual&(distance>2)).sum());missing=int((expected&(reverse>2)).sum())
            if foreign:errors.append('Connector has marks outside its planned route: '+ident)
            if missing>max(1,int(expected.sum()*.02)):errors.append('Connector route/head/cap is incomplete: '+ident)
            record.update(route_check='rendered-support',outside_route_pixels=foreign,missing_route_pixels=missing)
            if artifacts:
                artifacts.mkdir(parents=True,exist_ok=True)
                preview=artifacts/(ident+'-isolated.png')
                preview.write_bytes(render_png(ET.tostring(actual_root,encoding='unicode'),cache=cache))
                hidden=copy.deepcopy(root)
                for child in list(hidden):
                    if child.get('data-huitu-object-id')==ident:hidden.remove(child)
                ET.ElementTree(hidden).write(artifacts/(ident+'-hidden.svg'),encoding='utf-8',xml_declaration=True)
                record['isolated_preview']=str(preview.resolve())
            # Proves sibling containers are unchanged, not correctness of declared ownership.
            moved=copy.deepcopy(root)
            before={k:ET.tostring(v) for k,v in groups.items() if k!=ident}
            for child in moved:
                if child.get('data-huitu-object-id')==ident:child.set('transform','translate(25 15) '+child.get('transform',''))
            after={n.get('data-huitu-object-id'):ET.tostring(n) for n in moved if n.get('data-huitu-object-id') and n.get('data-huitu-object-id')!=ident}
            if before!=after:errors.append('Connector translation alters sibling containers: '+ident)
            record['sibling_containers_unchanged']=before==after
            if artifacts:ET.ElementTree(moved).write(artifacts/(ident+'-moved.svg'),encoding='utf-8',xml_declaration=True)
        except (ValueError,RuntimeError) as error:errors.append(ident+': '+str(error))
        if len(errors)==start_errors:record['status']='PASS'
        records.append(record)
    feature_result=None
    if data.get('feature_contract'):
        from feature_audit import audit as feature_audit
        feature_result=feature_audit(root,data,cache);errors.extend(feature_result['errors'])
    return {'status':'FAIL' if errors else 'PASS','schema':SCHEMA,'svg_sha256':hashlib.sha256(svg.read_bytes()).hexdigest(),
            'drawing_plan_sha256':hashlib.sha256(plan.read_bytes()).hexdigest(),'errors':errors,'objects':len(groups),
            'connectors':records,'connector_geometry_passed':all(r['status']=='PASS' for r in records),'feature_audit':feature_result,
            'meaning':'Checks declared construction, tile signatures and route isolation. Authorship, biological detail, hidden footprints and actual Illustrator movement still need visual/native review.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--svg',required=True,type=Path);p.add_argument('--plan',required=True,type=Path)
    p.add_argument('--artifacts',type=Path);p.add_argument('--report',required=True,type=Path);p.add_argument('--cache-dir',type=Path);a=p.parse_args()
    cache=from_directory(a.cache_dir)
    report=audit(a.svg,a.plan,a.artifacts,cache)
    if cache:report['render_cache']=dict(cache.stats)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='connectors'},ensure_ascii=False))
    raise SystemExit(0 if report['status']=='PASS' else 1)
