"""Adaptive editable solid-color vector patches; preserves raster shading without embedding it."""
from __future__ import annotations
import argparse,json,math,xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from runtime_env import bootstrap
bootstrap()
import numpy as np
from local_reconstruct import read_image,read_manifest,add_ids_and_text,SVG_NS
from manifest_lint import lint
from object_groups import group_attributes,audit,SCHEMA

def mesh(source:Path,manifest:Path,output:Path,regions:Path|None=None,tolerance:float=8,objects:Path|None=None,background:Path|None=None):
    image=read_image(source);h,w=image.shape[:2]
    validation=lint(manifest)
    if validation['status']!='PASS':raise ValueError('Invalid text manifest: '+str(validation['errors']))
    canvas=json.loads(manifest.read_text(encoding='utf-8-sig')).get('source',{})
    if (canvas.get('width_px'),canvas.get('height_px'))!=(w,h):raise ValueError('Manifest canvas must match source')
    if not 0<=tolerance<=32:raise ValueError('tolerance must be 0..32 RGB levels')
    owner=np.zeros((h,w),np.uint16);exact=np.zeros((h,w),np.uint8);names=['background'];object_attrs=[]
    if objects:
        if background is None:raise ValueError('Semantic mask mode requires a separately reconstructed background')
        backdrop=read_image(background)
        if backdrop.shape!=image.shape:raise ValueError('Background canvas must match source')
        data=json.loads(objects.read_text(encoding='utf-8-sig'));entries=data.get('objects')
        if not isinstance(entries,list) or not entries:raise ValueError('Object-mask manifest needs objects')
        object_attrs=[group_attributes('background','Background','background')];seen={'background'}
        for entry in entries:
            if not isinstance(entry,dict):raise ValueError('Each object entry must be an object')
            attrs=group_attributes(entry.get('id'),entry.get('name'),entry.get('kind'))
            if attrs['id'] in seen:raise ValueError('Duplicate object ID')
            if attrs['data-huitu-kind']=='background':raise ValueError('Use the independent background source')
            if len(names)>=65535:raise ValueError('Too many grouped objects')
            seen.add(attrs['id']);names.append(attrs['id']);object_attrs.append(attrs)
            mask_path=entry.get('mask_path')
            if not mask_path:
                if attrs['data-huitu-kind']!='label':raise ValueError('Each graphical object needs a precise ownership mask')
                continue
            mask_path=Path(mask_path)
            if not mask_path.is_absolute():mask_path=objects.parent/mask_path
            mask_image=read_image(mask_path)
            if mask_image.shape!=image.shape:raise ValueError('Ownership mask canvas must match source')
            if not np.array_equal(mask_image[:,:,0],mask_image[:,:,1]) or not np.array_equal(mask_image[:,:,0],mask_image[:,:,2]):raise ValueError('Ownership mask must be grayscale')
            mask=mask_image[:,:,0]>127
            if not np.any(mask):raise ValueError('Object ownership mask is empty')
            if np.any(owner[mask]):raise ValueError('Object masks overlap; resolve visible ownership explicitly')
            owner[mask]=len(names)-1
        for entry in read_manifest(manifest):
            if entry.get('object_id') not in seen:raise ValueError('Every live label needs a declared object_id')
    if regions:
        entries=json.loads(regions.read_text(encoding='utf-8-sig'))
        entries=entries.get('regions',entries) if isinstance(entries,dict) else entries
        seen=set()
        if not isinstance(entries,list):raise ValueError('Regions must be a list')
        for region in entries:
            if not isinstance(region,dict) or not isinstance(region.get('id'),str) or region['id'] in seen:raise ValueError('Regions need unique string IDs')
            seen.add(region['id'])
            box=region.get('bbox_px')
            if not isinstance(box,list) or len(box)!=4 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or int(v)!=v for v in box):raise ValueError('Region bbox must contain four finite integer pixels')
            x,y,rw,rh=map(int,box)
            if x<0 or y<0 or rw<=0 or rh<=0 or x+rw>w or y+rh>h:raise ValueError('Region bbox outside source')
            if region.get('exact_color'):exact[y:y+rh,x:x+rw]=1
            if not region.get('group_as_object'):continue
            if objects:raise ValueError('Do not mix rectangular region ownership with precise object masks')
            if len(names)>=65535:raise ValueError('Too many grouped regions')
            names.append(str(region['id']));owner[y:y+rh,x:x+rw]=len(names)-1
    patches=defaultdict(list);leaf_count=0
    def collect(data_image,ownership,precision_map,foreground_only=False):
        def visit(x,y,rw,rh):
            nonlocal leaf_count
            region=ownership[y:y+rh,x:x+rw];min_owner,max_owner=int(region.min()),int(region.max())
            if foreground_only and max_owner==0:return
            data=data_image[y:y+rh,x:x+rw];precision=precision_map[y:y+rh,x:x+rw]
            uniform_owner=min_owner==max_owner and int(precision.min())==int(precision.max())
            threshold=0 if precision[0,0] else tolerance
            spread=data.max(axis=(0,1)).astype(np.int16)-data.min(axis=(0,1)).astype(np.int16)
            if (uniform_owner and np.max(spread)<=threshold) or rw==rh==1:
                step=1 if precision[0,0] else 4
                color=np.rint(data.mean(axis=(0,1))/step)*step
                color=np.clip(color,0,255).astype(int)
                key=(int(region[0,0]),tuple(color[::-1]));patches[key].append((x,y,rw,rh));leaf_count+=1;return
            if rw>1 and rh>1:
                a,b=rw//2,rh//2
                for rect in ((x,y,a,b),(x+a,y,rw-a,b),(x,y+b,a,rh-b),(x+a,y+b,rw-a,rh-b)):visit(*rect)
            elif rw>1:
                a=rw//2;visit(x,y,a,rh);visit(x+a,y,rw-a,rh)
            else:
                b=rh//2;visit(x,y,rw,b);visit(x,y+b,rw,rh-b)
        visit(0,0,w,h)
    if objects:collect(backdrop,np.zeros_like(owner),np.zeros_like(exact))
    collect(image,owner,exact,foreground_only=bool(objects))
    root=ET.Element('{'+SVG_NS+'}svg',{'width':str(w),'height':str(h),'viewBox':f'0 0 {w} {h}','data-huitu-build':'source-color-mesh'})
    if objects:root.set('data-huitu-grouping',SCHEMA)
    groups={index:ET.SubElement(root,'{'+SVG_NS+'}g',object_attrs[index] if objects else {'id':f'object-{index:03d}','data-object-name':name}) for index,name in enumerate(names)}
    path_count=0
    def coalesce(rects):
        for _ in range(3):
            previous_count=len(rects)
            for horizontal in (True,False):
                ordered=sorted(rects,key=lambda r:(r[1],r[3],r[0]) if horizontal else (r[0],r[2],r[1]))
                combined=[]
                for r in ordered:
                    if combined:
                        px,py,pw,ph=combined[-1];x,y,rw,rh=r
                        if horizontal and y==py and rh==ph and x==px+pw:
                            combined[-1]=(px,py,pw+rw,ph);continue
                        if not horizontal and x==px and rw==pw and y==py+ph:
                            combined[-1]=(px,py,pw,ph+rh);continue
                    combined.append(r)
                rects=combined
            if len(rects)==previous_count:break
        return rects
    merged_count=0
    # Bound compound subpaths for both native Illustrator import and cached playback.
    for (index,color),rects in sorted(patches.items()):
        rects=coalesce(rects);merged_count+=len(rects)
        for offset in range(0,len(rects),256):
            d=' '.join(f'M{x} {y}h{rw}v{rh}h{-rw}Z' for x,y,rw,rh in rects[offset:offset+256])
            fill='#'+''.join(f'{value:02X}' for value in color)
            ET.SubElement(groups[index],'{'+SVG_NS+'}path',{'id':f'mesh-{path_count:06d}','d':d,'fill':fill,'shape-rendering':'crispEdges'})
            path_count+=1
    add_ids_and_text(root,read_manifest(manifest),w,h,'huitu')
    if objects:
        by_id={names[index]:group for index,group in groups.items()}
        for node in list(root):
            if node.tag.rsplit('}',1)[-1]!='text':continue
            target=by_id[node.get('data-huitu-owner')];root.remove(node);target.append(node)
        check=audit(root)
        if check['status']!='PASS':raise ValueError('; '.join(check['errors']))
    output.parent.mkdir(parents=True,exist_ok=True);ET.ElementTree(root).write(output,encoding='utf-8',xml_declaration=True)
    return {'backend':'adaptive-color-mesh-local','editable_paths':path_count,'rectangular_patches':merged_count,'quadtree_leaves':leaf_count,
            'groups':len(groups),'tolerance_rgb':tolerance,'raster_nodes':0,'semantic_object_groups':bool(objects),
            'limitation':'Source-scale appearance is preserved; shaded objects comprise many editable patches rather than a few smooth semantic curves.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','manifest','output'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--regions',type=Path);p.add_argument('--tolerance',type=float,default=8);p.add_argument('--report',type=Path)
    p.add_argument('--objects',type=Path);p.add_argument('--background-source',type=Path)
    a=p.parse_args();report=mesh(a.source,a.manifest,a.output,a.regions,a.tolerance,a.objects,a.background_source)
    if a.report:a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report))
