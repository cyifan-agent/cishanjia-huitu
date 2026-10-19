"""Bind optional measured native text fitting to a reviewed SVG revision."""
from __future__ import annotations
import argparse,copy,hashlib,json,math
from pathlib import Path

def attach_fit(svg,labels,manifest,canvas):
    data=json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
    if data.get('svg_sha256')!=hashlib.sha256(Path(svg).read_bytes()).hexdigest():
        raise ValueError('Native text fit manifest belongs to a different SVG')
    entries=data.get('text_elements')
    if not isinstance(entries,list):raise ValueError('Native text fit text_elements list required')
    result=copy.deepcopy(labels);known={r['source_id']:r for r in result};seen=set()
    for e in entries:
        ident=e.get('id') if isinstance(e,dict) else None
        if ident not in known or ident in seen:raise ValueError('Unknown or duplicate native text fit ID')
        seen.add(ident);label=known[ident]
        if e.get('content')!=label['content']:raise ValueError('Native text fit must preserve exact live content')
        if abs(label.get('rotation',0))>1e-8:raise ValueError('Rotated text requires manual native fitting')
        b=e.get('bbox_px')
        if not isinstance(b,list) or len(b)!=4 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in b):raise ValueError('Finite measured native text bbox required')
        x,y,w,h=b
        if x<0 or y<0 or w<=0 or h<=0 or x+w>canvas[0] or y+h>canvas[1]:raise ValueError('Native text bbox outside source canvas')
        tracking=e.get('tracking',[])
        if not isinstance(tracking,list):raise ValueError('Native text tracking must be an explicit list')
        occupied=set();units=len(label['content'].encode('utf-16-le'))//2
        for span in tracking:
            if not isinstance(span,dict):raise ValueError('Invalid native text tracking span')
            start,length,value=span.get('start'),span.get('length'),span.get('value')
            if isinstance(start,bool) or not isinstance(start,int) or isinstance(length,bool) or not isinstance(length,int) or start<0 or length<=0 or start+length>units:raise ValueError('Tracking span outside live text UTF-16 indices')
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>1000:raise ValueError('Finite tracking value within -1000..1000 required')
            covered=set(range(start,start+length))
            if occupied&covered:raise ValueError('Overlapping native tracking spans')
            occupied.update(covered)
        label['nativeFit']={'bbox_px':b,'tracking':tracking}
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('svg','labels','manifest'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--width',type=float,required=True);p.add_argument('--height',type=float,required=True)
    a=p.parse_args();payload=json.loads(a.labels.read_text(encoding='utf-8-sig'))
    payload['labels']=attach_fit(a.svg,payload['labels'],a.manifest,[a.width,a.height])
    a.labels.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'native_text_fits':sum('nativeFit' in v for v in payload['labels'])}))
