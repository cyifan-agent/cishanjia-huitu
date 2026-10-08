"""Compare an actual Illustrator PNG without stretching or hiding figure changes."""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
from render_compare import load_image,save_image,region_metrics,edge_f1
import cv2,numpy as np

def compare_export(source,export,regions=None,allow_white_rounding_border=False):
    original=load_image(source);actual=load_image(export)
    h,w=original.shape[:2];ah,aw=actual.shape[:2]
    adjustment=None
    if (ah,aw)!=(h,w):
        if not allow_white_rounding_border or abs(h-ah)>1 or abs(w-aw)>1:raise ValueError('Native PNG canvas mismatch; do not resize it away')
        tails=[]
        if ah>h:tails.append(actual[h:,:,:].reshape(-1,3))
        if aw>w:tails.append(actual[:,w:,:].reshape(-1,3))
        if ah<h:tails.extend([original[ah:,:,:].reshape(-1,3),actual[-1:,:,:].reshape(-1,3)])
        if aw<w:tails.extend([original[:,aw:,:].reshape(-1,3),actual[:,-1:,:].reshape(-1,3)])
        if not tails or np.min(np.concatenate(tails))<250:raise ValueError('Rounding border contains artwork; investigate geometry')
        adjustment={'comparison_only':'Excluded or padded at most one nearly white right/bottom rounding border; no scaling; exported PNG unchanged','right_px':aw-w,'bottom_px':ah-h}
        adjusted=np.full_like(original,255)
        adjusted[:min(h,ah),:min(w,aw)]=actual[:min(h,ah),:min(w,aw)]
        actual=adjusted
    metrics=region_metrics(original,actual,regions)
    failures=[]
    for region in metrics:
        for key,limit_key,greater in [('pixel_mae_bgr','max_mae',True),('edge_f1_tolerance_2px','min_edge_f1',False),('low_contrast_edge_f1_tolerance_2px','min_low_contrast_edge_f1',False)]:
            if limit_key in region and ((region[key]>region[limit_key]) if greater else (region[key]<region[limit_key])):failures.append(region['id']+':'+limit_key)
    return {'status':'FAIL' if failures else 'PASS','source':str(source),'actual_export':str(export),
        'actual_png_sha256':hashlib.sha256(export.read_bytes()).hexdigest(),'source_size':[w,h],'export_size':[aw,ah],'canvas_adjustment':adjustment,
        'pixel_mae_bgr':round(float(cv2.absdiff(original,actual).mean()),3),
        'edge_f1_tolerance_2px':round(edge_f1(original,actual),4),'low_contrast_edge_f1_tolerance_2px':round(edge_f1(original,actual,20,60),4),
        'regions':metrics,'threshold_failures':failures,'note':'Metrics are regional regression checks; actual visual and native text review is required.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path);p.add_argument('--export',required=True,type=Path)
    p.add_argument('--regions',type=Path);p.add_argument('--report',required=True,type=Path)
    p.add_argument('--allow-white-rounding-border',action='store_true');a=p.parse_args()
    report=compare_export(a.source,a.export,a.regions,a.allow_white_rounding_border)
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='regions'},ensure_ascii=False))
    raise SystemExit(0 if report['status']=='PASS' else 1)
