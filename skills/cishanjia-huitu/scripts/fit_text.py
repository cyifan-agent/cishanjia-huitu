"""Fit known live labels to local glyph pixels; does not perform OCR."""
from __future__ import annotations
import argparse,json,html,tempfile
from pathlib import Path
from runtime_env import bootstrap
bootstrap()
import cv2,numpy as np,resvg_py
from PIL import ImageFont
from local_reconstruct import read_image,parse_rgb,font_size_px
from preview_fonts import font_files_for_svg,resolve_font_file
from manifest_lint import lint

def fit(source:Path,cleaned:Path,manifest:Path,output:Path,report:Path|None=None,families_to_try:list[str]|None=None,width_adjustment:float=.02):
    original=read_image(source);background=read_image(cleaned)
    if original.shape!=background.shape:raise ValueError('Source and cleaned image dimensions must match')
    validation=lint(manifest)
    if validation['status']!='PASS':raise ValueError('Invalid text manifest: '+str(validation['errors']))
    data=json.loads(manifest.read_text(encoding='utf-8-sig'))
    if (data['source']['width_px'],data['source']['height_px'])!=(original.shape[1],original.shape[0]):raise ValueError('Manifest canvas must match source')
    if not np.isfinite(width_adjustment) or not 0<=width_adjustment<=.12:raise ValueError('Width adjustment must be finite and within 0..0.12')
    records=[];candidates={};groups={}
    # Entries sharing one source style use one family, rather than selecting
    # an unrelated family independently for every short word.
    for entry in data['text_elements']:
        key=entry.get('style_group') or 'declared:'+entry.get('font_family','Arial')+'|'+str(entry.get('font_weight','normal'))+'|'+entry.get('font_style','normal')
        if not isinstance(key,str) or not key.strip():raise ValueError('style_group must be a nonempty string')
        groups.setdefault(key,[]).append(entry)
    with tempfile.TemporaryDirectory(prefix='huitu-fit-fonts-') as temporary:
        dummy=Path(temporary)/'font-request.svg'
        families={entry.get('font_family','Arial') for entry in data['text_elements']}
        families.update(families_to_try or [])
        dummy.write_text('<svg xmlns="http://www.w3.org/2000/svg">'+''.join('<text font-family="'+html.escape(name,quote=True)+'" font-weight="'+html.escape(str(entry.get('font_weight','normal')),quote=True)+'" font-style="'+html.escape(str(entry.get('font_style','normal')),quote=True)+'">x</text>' for name in families for entry in data['text_elements'])+'</svg>',encoding='utf-8')
        files=font_files_for_svg(dummy,Path(temporary)/'fonts')
        for entry in data['text_elements']:
            if '\n' in entry['content']:raise ValueError('Fit spatially separate lines as separate entries')
            if entry.get('rotation',0):raise ValueError('Rotated labels need manual fitting')
            x,y,w,h=map(int,entry['bbox_px']);a=original[y:y+h,x:x+w].astype(np.float32)
            bg=background[y:y+h,x:x+w].astype(np.float32)
            color=np.array(parse_rgb(entry.get('fill','#111111'))[::-1],np.float32)
            delta=bg-color
            target=np.clip(np.sum((bg-a)*delta,axis=2)/np.maximum(1,np.sum(delta*delta,axis=2)),0,1)
            size=float(font_size_px(entry,original.shape[0]));sx=float(entry.get('horizontal_scale',1))
            ox,oy=float(entry['x'])-x,float(entry['y'])-y
            by_family={}
            weight=entry.get('font_weight','normal');style=entry.get('font_style','normal')
            for family_candidate in (families_to_try or [entry.get('font_family','Arial')]):
              natural=ImageFont.truetype(resolve_font_file(family_candidate,weight,style),100)
              original_font=ImageFont.truetype(resolve_font_file(entry.get('font_family','Arial'),weight,style),100)
              width_ratio=original_font.getlength(entry['content'])/natural.getlength(entry['content'])
              best=None
              for factor in np.linspace(.92,1.08,9):
               for width_factor in ([1.] if width_adjustment==0 else [1-width_adjustment,1.,1+width_adjustment]):
                candidate=size*factor;scale=sx/factor*width_ratio*width_factor
                content=html.escape(entry['content']);family=html.escape(family_candidate,quote=True)
                markup=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><text x="{ox}" y="{oy}" text-anchor="{entry.get("text_anchor","start")}" font-family="{family}" font-size="{candidate}" font-weight="{weight}" font-style="{style}" fill="#000" transform="translate({ox} {oy}) scale({scale} 1) translate({-ox} {-oy})">{content}</text></svg>'
                payload=resvg_py.svg_to_bytes(svg_string=markup,font_files=files,skip_system_fonts=True)
                rgba=cv2.imdecode(np.frombuffer(payload,np.uint8),cv2.IMREAD_UNCHANGED);alpha=rgba[:,:,3].astype(np.float32)/255
                for dx in (-1.5,-1,-.5,0,.5,1,1.5):
                    for dy in (-2,-1.5,-1,-.5,0,.5,1,1.5,2):
                        if not 0<=float(entry['x'])+dx<=original.shape[1] or not 0<=float(entry['y'])+dy<=original.shape[0]:continue
                        moved=cv2.warpAffine(alpha,np.float32([[1,0,dx],[0,1,dy]]),(w,h),flags=cv2.INTER_LINEAR)
                        error=float(np.mean((target-moved)**2))
                        if best is None or error<best[0]:best=(error,candidate,scale,dx,dy,family_candidate)
              by_family[family_candidate]=best
            candidates[entry['id']]={'fits':by_family,'area':w*h}
    group_report=[]
    for key,entries in groups.items():
        shared=set.intersection(*(set(candidates[e['id']]['fits']) for e in entries))
        if not shared:raise ValueError('Typography group has no common family candidates: '+key)
        scores={f:sum(candidates[e['id']]['fits'][f][0]*candidates[e['id']]['area'] for e in entries)/sum(candidates[e['id']]['area'] for e in entries) for f in shared}
        family=min(sorted(shared),key=lambda f:scores[f])
        group_report.append({'style_group':key,'font_family':family,'entries':len(entries),'candidate_scores':{f:round(scores[f],6) for f in sorted(shared)}})
        for entry in entries:
            error,candidate,scale,dx,dy,_=candidates[entry['id']]['fits'][family]
            entry.update(source_font_size_px=round(candidate,4),horizontal_scale=round(scale,6),x=round(float(entry['x'])+dx,4),y=round(float(entry['y'])+dy,4),font_family=family)
            records.append({'id':entry['id'],'style_group':key,'glyph_alpha_mse':round(error,6),'font_family':family,'font_size':entry['source_font_size_px'],'horizontal_scale':entry['horizontal_scale'],'dx':dx,'dy':dy})
    order={e['id']:i for i,e in enumerate(data['text_elements'])};records.sort(key=lambda r:order[r['id']])
    output.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    if report:report.write_text(json.dumps({'local_only':True,'ocr_performed':False,'review_required':True,'text_entries':len(records),'typography_groups':group_report,'fits':records},ensure_ascii=False,indent=2),encoding='utf-8')
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','cleaned','manifest','output'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--report',type=Path);p.add_argument('--families',help='Comma-separated installed font families');p.add_argument('--width-adjustment',type=float,default=.02);args=p.parse_args()
    fits=fit(args.source,args.cleaned,args.manifest,args.output,args.report,args.families.split(',') if args.families else None,args.width_adjustment)
    print(json.dumps({'entries_fitted':len(fits),'mean_glyph_alpha_mse':round(float(np.mean([item['glyph_alpha_mse'] for item in fits])),6)}))
