"""Export whole vector components or revise named owners without changing siblings.

Works on construction SVG/plan files; it never contacts Illustrator. A patched
master must be reviewed again before native delivery. Old files remain intact.
"""
from pathlib import Path
import argparse,copy,hashlib,json,re,xml.etree.ElementTree as E
from object_groups import audit as ownership_audit
from svg_contract import validate,local_name,view_box,SVG_NS
E.register_namespace('',SVG_NS)

URL=re.compile(r'url\(\s*#([^\s)]+)\s*\)')

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def encoded(node):return hashlib.sha256(E.tostring(node,encoding='utf-8')).hexdigest()
def owners(root):return {n.get('data-huitu-object-id'):n for n in root if n.get('data-huitu-object-id')}
def specs(plan):return {s['id']:s for s in plan['objects']}
def new_path(path,inputs=()):
    p=Path(path).resolve()
    if p in {Path(v).resolve() for v in inputs} or p.exists():raise ValueError('Use a new output path; inputs and prior revisions are preserved')
    return p
def resources(root,owner):
    wanted={m.group(1) for n in owner.iter() for value in n.attrib.values() for m in URL.finditer(value)}
    available={n.get('id'):n for defs in root if local_name(defs.tag)=='defs' for n in defs}
    missing=wanted-set(available)
    if missing:raise ValueError('Missing paint resources: '+','.join(sorted(missing)))
    return {k:available[k] for k in sorted(wanted)}
def check(root,plan):
    r=ownership_audit(root)
    if r['status']!='PASS':raise ValueError('; '.join(r['errors']))
    if plan.get('schema')!='vector-redraw-v1' or plan.get('canvas')!=view_box(root)[2:]:raise ValueError('Matching authored drawing plan required')
    if len(specs(plan))!=len(plan['objects']) or set(specs(plan))!=set(owners(root)):raise ValueError('Plan and object owner IDs differ')
    for o in r['objects']:
        part_ids=[p['id'] for p in specs(plan)[o['id']]['parts']]
        if len(part_ids)!=len(set(part_ids)) or set(part_ids)!=set(o['graphic_ids']+o['text_ids']):raise ValueError('Explicit owned parts differ: '+o['id'])

def extract(svg,plan_path,object_id,out_svg,out_plan):
    out_svg=new_path(out_svg,[svg,plan_path]);out_plan=new_path(out_plan,[svg,plan_path])
    if out_svg==out_plan:raise ValueError('Distinct output files required')
    root=E.parse(svg).getroot();plan=json.loads(Path(plan_path).read_text(encoding='utf-8-sig'));check(root,plan)
    if object_id not in owners(root):raise ValueError('Unknown semantic object')
    item=owners(root)[object_id];result=E.Element(root.tag,dict(root.attrib));paint=resources(root,item)
    if paint:
        defs=E.SubElement(result,'defs')
        for p in paint.values():defs.append(copy.deepcopy(p))
    result.append(copy.deepcopy(item));component={'schema':plan['schema'],'canvas':plan['canvas'],'objects':[copy.deepcopy(specs(plan)[object_id])],'source_svg_sha256':digest(svg),'component_requires_source_adaptation':True}
    # Feature source measurements remain bound to their original coordinate system.
    if plan.get('feature_contract'):component['feature_contract']=plan['feature_contract']
    check(result,component);out_svg.parent.mkdir(parents=True,exist_ok=True);out_plan.parent.mkdir(parents=True,exist_ok=True)
    E.ElementTree(result).write(out_svg,encoding='utf-8',xml_declaration=True);out_plan.write_text(json.dumps(component,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'status':'PASS','object_id':object_id,'component_svg':str(out_svg),'component_plan':str(out_plan),'native_or_raster_calls':0,'review_required':True}

def patch(svg,plan_path,patch_path,out_svg,out_plan):
    out_svg=new_path(out_svg,[svg,plan_path,patch_path]);out_plan=new_path(out_plan,[svg,plan_path,patch_path])
    if out_svg==out_plan:raise ValueError('Distinct output files required')
    root=E.parse(svg).getroot();plan=json.loads(Path(plan_path).read_text(encoding='utf-8-sig'));check(root,plan)
    request=json.loads(Path(patch_path).read_text(encoding='utf-8-sig'))
    if request.get('schema')!='scene-patch-v1' or request.get('base_svg_sha256')!=digest(svg) or request.get('base_plan_sha256')!=digest(plan_path):raise ValueError('Patch is missing or bound to a stale SVG/plan')
    operations=request.get('operations')
    if not isinstance(operations,list) or not operations:raise ValueError('Explicit patch operations required')
    before={k:encoded(v) for k,v in owners(root).items()};old_spec={k:json.dumps(v,sort_keys=True) for k,v in specs(plan).items()};changed=[]
    for op in operations:
        if not isinstance(op,dict):raise ValueError('Patch operations must be records')
        ident=op.get('object_id')
        if ident not in before or ident in changed:raise ValueError('Unique known object IDs required for patch operations')
        item=owners(root)[ident];definition=specs(plan)[ident]
        if op.get('op')=='translate':
            import math
            dx,dy=op.get('dx'),op.get('dy')
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (dx,dy)):raise ValueError('Finite translate dx/dy required')
            item.set('transform',f'translate({dx} {dy}) '+item.get('transform',''))
            if 'connector' in definition:
                definition['connector']['points']=[[p[0]+dx,p[1]+dy] for p in definition['connector']['points']]
            # source_bbox/landmarks remain source measurements. Moving a feature
            # away from its reference should trigger review, not erase the evidence.
        elif op.get('op')=='replace':
            base=Path(patch_path).resolve().parent
            def input_path(key):
                p=Path(op[key]);return p if p.is_absolute() else base/p
            replacement_root=E.parse(input_path('source_svg')).getroot();replacement_plan=json.loads(input_path('source_plan').read_text(encoding='utf-8-sig'));check(replacement_root,replacement_plan)
            if view_box(replacement_root)!=view_box(root):raise ValueError('Replacement must retain source pixel canvas; no implicit rescaling')
            if ident not in owners(replacement_root):raise ValueError('Replacement semantic owner ID must match target')
            replacement=copy.deepcopy(owners(replacement_root)[ident]);replacement_spec=copy.deepcopy(specs(replacement_plan)[ident])
            # Imported paints get unique IDs. A shared sibling gradient is never
            # overwritten just because a replacement uses the same old name.
            paint=resources(replacement_root,replacement);occupied={n.get('id') for n in root.iter() if n.get('id')}
            mapping={}
            for key,node in paint.items():
                salt=hashlib.sha256((ident+key+encoded(node)).encode()).hexdigest()[:12]
                new_id='patch-paint-'+salt;n=0
                while new_id in occupied:n+=1;new_id='patch-paint-'+salt+'-'+str(n)
                mapping[key]=new_id;occupied.add(new_id)
            for n in replacement.iter():
                for key,value in list(n.attrib.items()):n.set(key,URL.sub(lambda m:'url(#'+mapping[m.group(1)]+')',value))
            if paint:
                defs=next((n for n in root if local_name(n.tag)=='defs'),None)
                if defs is None:defs=E.Element('defs');root.insert(0,defs)
                for key,node in paint.items():
                    new=copy.deepcopy(node);new.set('id',mapping[key]);defs.append(new)
            if replacement_spec.get('connector'):
                for key,value in list(replacement_spec['connector'].items()):
                    if isinstance(value,str):replacement_spec['connector'][key]=URL.sub(lambda m:'url(#'+mapping[m.group(1)]+')',value)
            position=list(root).index(item);root.remove(item);root.insert(position,replacement)
            plan['objects'][next(i for i,s in enumerate(plan['objects']) if s['id']==ident)]=replacement_spec
        else:raise ValueError('Supported operations are whole-object replace and translate')
        changed.append(ident)
    check(root,plan)
    untouched=[k for k in before if k not in changed]
    if any(encoded(owners(root)[k])!=before[k] or json.dumps(specs(plan)[k],sort_keys=True)!=old_spec[k] for k in untouched):raise ValueError('Patch altered an unrelated object')
    out_svg.parent.mkdir(parents=True,exist_ok=True);out_plan.parent.mkdir(parents=True,exist_ok=True)
    E.ElementTree(root).write(out_svg,encoding='utf-8',xml_declaration=True);out_plan.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'status':'PASS','changed_objects':changed,'untouched_objects':untouched,'siblings_identical':True,'prior_review_invalidated':True,'new_svg_sha256':digest(out_svg),'new_plan_sha256':digest(out_plan),'review_required':True,'native_or_raster_calls':0}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    for mode in ('extract','patch'):
        q=sub.add_parser(mode)
        for key in ('svg','plan','output-svg','output-plan','report'):q.add_argument('--'+key,type=Path,required=True)
        q.add_argument('--object-id',required=True) if mode=='extract' else q.add_argument('--patch',type=Path,required=True)
    a=p.parse_args()
    new_path(a.report,[a.svg,a.plan,a.output_svg,a.output_plan]+([a.patch] if a.mode=='patch' else []))
    r=extract(a.svg,a.plan,a.object_id,a.output_svg,a.output_plan) if a.mode=='extract' else patch(a.svg,a.plan,a.patch,a.output_svg,a.output_plan)
    a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r,ensure_ascii=False))
