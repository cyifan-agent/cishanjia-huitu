"""Prepare local redraw evidence in one process; never approve or import artwork."""
from __future__ import annotations
import argparse,contextlib,hashlib,io,json
from pathlib import Path
from types import SimpleNamespace
from redraw_audit import audit
from render_compare import compare
from render_cache import from_directory
from quality_gate import CHECKS

def prepare(source,svg,plan,regions,output_dir,cache_dir):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    cache=from_directory(cache_dir)
    construction=audit(Path(svg),Path(plan),output_dir/'connector-checks',cache)
    (output_dir/'redraw-audit.json').write_text(json.dumps(construction,ensure_ascii=False,indent=2),encoding='utf-8')
    args=SimpleNamespace(source=str(source),svg=str(svg),regions=str(regions) if regions else None,report=str(output_dir/'comparison.json'),preview=str(output_dir/'preview.png'),region_previews=str(output_dir/'qa-regions'),contact_sheet=None,diff=None,max_mae=None,min_edge_f1=None,cache_dir=None)
    # Share fonts/module metadata and exact renderer state in this process.
    with contextlib.redirect_stdout(io.StringIO()):comparison=compare(args,cache=cache)
    template={'svg_sha256':hashlib.sha256(Path(svg).read_bytes()).hexdigest(),'drawing_plan':str(Path(plan).resolve()),'checks':{name:{'status':'unreviewed','evidence':''} for name in CHECKS},'regions':{r['id']:'unreviewed' for r in comparison['regions'] if r['critical']},'unresolved_issues':['Inspect source/preview regions and every isolated/hidden/moved connector before construction approval. Review actual native export after authorized import.']}
    (output_dir/'visual-review-template.json').write_text(json.dumps(template,ensure_ascii=False,indent=2),encoding='utf-8')
    passed=construction['status']=='PASS' and not comparison['threshold_failures']
    report={'status':'AWAITING_VISUAL_REVIEW' if passed else 'FAIL','redraw_status':construction['status'],'comparison_threshold_failures':comparison['threshold_failures'],'objects':construction['objects'],'connectors':len(construction['connectors']),'render_cache':dict(cache.stats) if cache else None,'automatic_approval':False,'illustrator_contacted':False}
    (output_dir/'review-preparation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','svg','plan','output-dir','cache-dir'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--regions',type=Path);a=p.parse_args()
    result=prepare(a.source,a.svg,a.plan,a.regions,a.output_dir,a.cache_dir)
    print(json.dumps(result,ensure_ascii=False));raise SystemExit(result['status']=='FAIL')
