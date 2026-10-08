"""Check explicitly inventoried biological features, ownership and source landmarks.

This validates declarations and measured geometry, not automatic anatomical recognition.
"""
from pathlib import Path
import argparse,copy,json,math,tempfile,xml.etree.ElementTree as E
from runtime_env import bootstrap
bootstrap()
import numpy as np,cv2,resvg_py
from object_groups import audit as ownership_audit
from svg_contract import local_name,DRAWABLE,view_box
from preview_fonts import font_files_for_svg
from render_cache import render_png,from_directory

SCHEMA='source-features-v1'
BIOLOGICAL={'cell','organelle','dna','molecule','protein','complex'}

def finite(raw,label,positive=False):
    if isinstance(raw,bool) or not isinstance(raw,(int,float)) or not math.isfinite(raw) or (positive and raw<=0):raise ValueError(label+' needs a finite '+('positive ' if positive else '')+'number')
    return float(raw)

def support(root,owner,part_ids,temporary,cache=None):
    selected=set(part_ids)
    def filtered(node):
        if local_name(node.tag) in DRAWABLE:return copy.deepcopy(node) if node.get('id') in selected else None
        out=E.Element(node.tag,dict(node.attrib))
        for child in node:
            keep=filtered(child)
            if keep is not None:out.append(keep)
        return out if len(out) else None
    isolated=E.Element(root.tag,dict(root.attrib))
    for n in root:
        if local_name(n.tag)=='defs':isolated.append(copy.deepcopy(n))
    isolated.append(filtered(owner))
    path=Path(temporary)/'feature.svg';E.ElementTree(isolated).write(path,encoding='utf-8',xml_declaration=True)
    files=font_files_for_svg(path,Path(temporary)/'fonts')
    rgba=cv2.imdecode(np.frombuffer(render_png(E.tostring(isolated,encoding='unicode'),font_files=files,cache=cache),np.uint8),cv2.IMREAD_UNCHANGED)
    mask=rgba[:,:,3]>8 if rgba.shape[2]==4 else np.ones(rgba.shape[:2],bool)
    return mask

def audit(root,plan,cache=None):
    structure=ownership_audit(root);errors=list(structure['errors']);records=[]
    if plan.get('feature_contract')!=SCHEMA:errors.append('source-features-v1 declaration required')
    canvas=view_box(root)
    if canvas[:2]!=[0,0] or plan.get('canvas')!=canvas[2:]:errors.append('Feature plan canvas mismatch')
    groups={g.get('data-huitu-object-id'):g for g in root if g.get('data-huitu-object-id')}
    owners=structure['owners'];entries={e['id']:e for e in plan.get('objects',[])}
    if set(entries)!=set(groups):errors.append('Feature plan must declare all owners')
    with tempfile.TemporaryDirectory(prefix='huitu-feature-review-') as temporary:
      for ident,owner in groups.items():
        entry=entries.get(ident,{})
        features=entry.get('features',[]);required=entry.get('required_features',[])
        if not isinstance(required,list) or any(not isinstance(k,str) or not k for k in required) or len(set(required))!=len(required):errors.append(ident+': unique required_features keys needed');continue
        if not isinstance(features,list):errors.append(ident+': features must be a list');continue
        if owner.get('data-huitu-kind') in BIOLOGICAL and (not features or not required):errors.append(ident+': biological feature inventory required')
        keys=set();covered=set()
        for f in features:
          if not isinstance(f,dict):errors.append(ident+': feature record must be an object');continue
          key=f.get('key');start=len(errors)
          if not isinstance(key,str) or not key.strip() or key in keys:errors.append(ident+': unique feature key required');continue
          keys.add(key);parts=f.get('part_ids')
          if not isinstance(parts,list) or not parts or any(not isinstance(p,str) for p in parts) or len(set(parts))!=len(parts):errors.append(ident+'/'+key+': explicit unique feature parts required');continue
          foreign=[p for p in parts if owners.get(p)!=ident]
          if foreign:errors.append(ident+'/'+key+': missing or foreign-owner parts: '+','.join(foreign));continue
          if covered.intersection(parts):errors.append(ident+'/'+key+': vector parts assigned to multiple primary features')
          covered.update(parts)
          count=f.get('expected_parts',{})
          if not isinstance(count,dict):errors.append(ident+'/'+key+': expected_parts must be an object');continue
          if all(isinstance(count.get(k),int) and not isinstance(count.get(k),bool) for k in ('min','max')) and count['min']>count['max']:errors.append(ident+'/'+key+': minimum part count exceeds maximum')
          for limit,actual_ok in [('min',lambda n:len(parts)>=n),('max',lambda n:len(parts)<=n)]:
            n=count.get(limit)
            if n is not None:
              if isinstance(n,bool) or not isinstance(n,int) or n<1:errors.append(ident+'/'+key+': positive integer part limit required')
              elif not actual_ok(n):errors.append(ident+'/'+key+': part-count '+limit+' constraint failed')
          r={'object_id':ident,'feature':key,'parts':len(parts),'status':'FAIL'}
          try:
            marks=f.get('landmarks',[])
            if not isinstance(marks,list) or any(not isinstance(m,dict) for m in marks):raise ValueError('landmarks must be a list of measurement records')
            if f.get('source_bbox_px') is not None or f.get('landmarks'):
              mask=support(root,owner,parts,temporary,cache)
              ys,xs=np.where(mask)
              if not len(xs):raise ValueError('Declared feature has no visible vector support')
              bbox=[int(xs.min()),int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)];r['actual_bbox_px']=bbox
              expected=f.get('source_bbox_px')
              if expected is not None:
                if not isinstance(expected,list) or len(expected)!=4:raise ValueError('source_bbox_px needs x/y/width/height')
                expected=[finite(v,'source bbox') for v in expected]
                if expected[2]<=0 or expected[3]<=0:raise ValueError('Source bbox must have positive dimensions')
                if expected[0]<0 or expected[1]<0 or expected[0]+expected[2]>canvas[2] or expected[1]+expected[3]>canvas[3]:raise ValueError('Source bbox outside source canvas')
                margin=finite(f.get('max_bbox_error_px',3),'bbox tolerance',True)
                # Compare sides rather than width alone, so translations cannot hide.
                sides=[bbox[0],bbox[1],bbox[0]+bbox[2],bbox[1]+bbox[3]];target=[expected[0],expected[1],expected[0]+expected[2],expected[1]+expected[3]]
                error=max(abs(a-b) for a,b in zip(sides,target));r['bbox_error_px']=round(error,4)
                if error>margin:errors.append(ident+'/'+key+': measured source bounds differ')
              boundary=mask&~cv2.erode(mask.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
              distances={}
              for mark in marks:
                point=mark.get('point');kind=mark.get('kind','boundary')
                if not isinstance(point,list) or len(point)!=2 or kind not in {'boundary','inside'}:raise ValueError('Landmark requires point and boundary/inside kind')
                px,py=[finite(v,'landmark point') for v in point]
                tol=finite(mark.get('max_error_px',2),'landmark tolerance',True)
                if not 0<=px<mask.shape[1] or not 0<=py<mask.shape[0]:raise ValueError('Landmark outside source canvas')
                if kind not in distances:distances[kind]=cv2.distanceTransform((~(boundary if kind=='boundary' else mask)).astype(np.uint8),cv2.DIST_L2,cv2.DIST_MASK_PRECISE)
                error=float(distances[kind][min(mask.shape[0]-1,round(py)),min(mask.shape[1]-1,round(px))]);r.setdefault('landmark_errors_px',[]).append(round(error,4))
                if error>tol:errors.append(ident+'/'+key+': source landmark missed: '+str(mark.get('name',point)))
          except (ValueError,TypeError) as e:errors.append(ident+'/'+key+': '+str(e))
          if len(errors)==start:r['status']='PASS'
          records.append(r)
        if set(required)-keys:errors.append(ident+': missing required anatomical features: '+','.join(sorted(set(required)-keys)))
        graphic_ids={n.get('id') for n in owner.iter() if local_name(n.tag) in DRAWABLE-{'text'}}
        if owner.get('data-huitu-kind') in BIOLOGICAL and graphic_ids-covered:errors.append(ident+': biological vector parts without feature assignment: '+','.join(sorted(graphic_ids-covered)))
    return {'status':'FAIL' if errors else 'PASS','schema':SCHEMA,'errors':errors,'features':records,'meaning':'Checks authored feature inventory, ownership, part counts and measured landmarks. Does not recognize anatomy, prove topology, or replace enlarged visual review.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--svg',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--cache-dir',type=Path);a=p.parse_args()
    cache=from_directory(a.cache_dir)
    r=audit(E.parse(a.svg).getroot(),json.loads(a.plan.read_text(encoding='utf-8-sig')),cache)
    if cache:r['render_cache']=dict(cache.stats)
    a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':r['status'],'features':len(r['features']),'errors':r['errors']}));raise SystemExit(0 if r['status']=='PASS' else 1)
