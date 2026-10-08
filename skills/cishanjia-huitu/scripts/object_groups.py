"""Assemble and audit independently movable scientific SVG object groups."""
from __future__ import annotations
import argparse,copy,hashlib,json,re,xml.etree.ElementTree as ET
from pathlib import Path
from svg_contract import validate,local_name,DRAWABLE,INFO,SVG_NS

SCHEMA='semantic-v1'
KINDS={'background','cell','organelle','dna','molecule','protein','complex','connector','label','other'}

def group_attributes(ident,name,kind):
    if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,63}',ident):
        raise ValueError('Object IDs need stable short ASCII identifiers')
    if not isinstance(name,str) or not name.strip() or kind not in KINDS:
        raise ValueError('Object needs a display name and supported kind')
    return {'id':ident,'data-huitu-object-id':ident,'data-huitu-name':name,'data-huitu-kind':kind}

def audit(root):
    validate(root)
    errors=[];objects=[];owners={}
    if root.get('data-huitu-grouping')!=SCHEMA:errors.append('Explicit semantic object grouping required')
    groups=[n for n in root if local_name(n.tag) not in INFO|{'defs'}]
    for group in groups:
        ident=group.get('data-huitu-object-id')
        if local_name(group.tag)!='g' or not ident:
            errors.append('Every top-level artwork node must be an object group');continue
        try:group_attributes(ident,group.get('data-huitu-name'),group.get('data-huitu-kind'))
        except ValueError as error:errors.append(str(error));continue
        if group.get('id')!=ident:errors.append('Object ID must equal its SVG group ID')
        if any(n.get('data-huitu-object-id') for n in group.iter() if n is not group):
            errors.append('Nested semantic ownership is ambiguous; keep internal subgroups without ownership markers')
        graphics=[];texts=[]
        for node in group.iter():
            tag=local_name(node.tag)
            if tag not in DRAWABLE:continue
            node_id=node.get('id');owners[node_id]=ident
            (texts if tag=='text' else graphics).append(node_id)
        if not graphics and not texts:errors.append('Empty object group: '+ident)
        objects.append({'id':ident,'svg_id':ident,'name':group.get('data-huitu-name'),'kind':group.get('data-huitu-kind'),
                        'graphic_ids':graphics,'text_ids':texts,'graphic_count':len(graphics),'text_count':len(texts)})
    if not objects:errors.append('No semantic object groups')
    return {'status':'FAIL' if errors else 'PASS','schema':SCHEMA,'errors':errors,'objects':objects,'owners':owners,
            'meaning':'Checks structural ownership; masks, whole-object completeness and movement require visual review.'}

def assemble(source:Path,manifest:Path,output:Path):
    root=ET.parse(source).getroot();validate(root)
    data=json.loads(manifest.read_text(encoding='utf-8-sig'));entries=data.get('objects')
    if not isinstance(entries,list) or not entries:raise ValueError('Object manifest needs objects')
    direct={n.get('id'):n for n in root if local_name(n.tag) not in INFO|{'defs'}}
    if None in direct:raise ValueError('Top-level artwork containers need IDs before assembly')
    owned=set();object_ids=set();prepared=[]
    for entry in entries:
        if not isinstance(entry,dict):raise ValueError('Each object entry must be an object')
        attrs=group_attributes(entry.get('id'),entry.get('name'),entry.get('kind'))
        if attrs['id'] in object_ids:raise ValueError('Duplicate object ID')
        object_ids.add(attrs['id']);members=entry.get('member_ids')
        if not isinstance(members,list) or not members:raise ValueError('Object needs explicit member_ids')
        group=ET.Element('{'+SVG_NS+'}g',attrs)
        for ident in members:
            if ident not in direct:raise ValueError('Member must be a complete top-level node: '+str(ident))
            if ident in owned:raise ValueError('Member assigned to more than one object: '+ident)
            owned.add(ident);child=copy.deepcopy(direct[ident])
            # Old coarse region tags must not masquerade as nested ownership.
            for node in child.iter():
                for key in ('data-huitu-object-id','data-huitu-name','data-huitu-kind'):node.attrib.pop(key,None)
            group.append(child)
        prepared.append(group)
    if owned!=set(direct):raise ValueError('Unassigned top-level nodes: '+','.join(sorted(set(direct)-owned)))
    result=ET.Element(root.tag,dict(root.attrib));result.set('data-huitu-grouping',SCHEMA)
    for child in root:
        if local_name(child.tag) in INFO|{'defs'}:result.append(copy.deepcopy(child))
    for group in prepared:result.append(group)
    report=audit(result)
    if report['status']!='PASS':raise ValueError('; '.join(report['errors']))
    output.parent.mkdir(parents=True,exist_ok=True);ET.ElementTree(result).write(output,encoding='utf-8',xml_declaration=True)
    report['svg_sha256']=hashlib.sha256(output.read_bytes()).hexdigest();return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--svg',required=True,type=Path);p.add_argument('--manifest',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args()
    if a.manifest:
        if not a.output:p.error('--output is required for assembly')
        report=assemble(a.svg,a.manifest,a.output)
    else:
        report=audit(ET.parse(a.svg).getroot());report['svg_sha256']=hashlib.sha256(a.svg.read_bytes()).hexdigest()
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'objects':len(report['objects']),'errors':report['errors']},ensure_ascii=False))
    raise SystemExit(0 if report['status']=='PASS' else 1)
