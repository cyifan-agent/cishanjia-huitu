"""Fit one measured biological contour while keeping named source landmarks."""
from pathlib import Path
import argparse,json
from runtime_env import bootstrap
bootstrap()
from contour_refit import landmark_path

def refine(source,output):
    if Path(source).resolve()==Path(output).resolve():raise ValueError('Keep measured landmarks unchanged; use a separate output')
    data=json.loads(Path(source).read_text(encoding='utf-8-sig'))
    if data.get('schema')!='landmark-contour-v1':raise ValueError('landmark-contour-v1 required')
    if not isinstance(data.get('closed',True),bool):raise ValueError('closed must be a boolean')
    path,report=landmark_path(data['points'],data['landmarks'],closed=data.get('closed',True),tolerance=data.get('tolerance_px',.45),spacing=data.get('spacing_px',.5))
    result={'schema':'landmark-contour-v1','object_id':data['object_id'],'d':path,'construction':'curve-refit','review_required':True,**report}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--landmarks',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=refine(a.landmarks,a.output);print(json.dumps({'object_id':r['object_id'],'fixed_landmarks':len(r['fixed_landmarks']),'segments':r['segments'],'anchor_shift_px':r['anchor_shift_px']}))
