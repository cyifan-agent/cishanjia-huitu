"""Self-contained SVG live-text geometry; no external skill or path parser."""
from __future__ import annotations
from dataclasses import dataclass
import math, re, sys

NUMBER = r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'

def rounded(value):
    return round(float(value), 6)

def parse_number(value, default=0):
    if value is None:return default
    raw=str(value).strip()
    if not re.fullmatch(NUMBER+r'(?:px|pt)?',raw):
        raise ValueError('Explicit finite pixel text coordinate required: '+raw)
    result=float(re.match(NUMBER,raw)[0])
    if not math.isfinite(result):raise ValueError('Non-finite text coordinate')
    return result

@dataclass(frozen=True)
class Transform:
    xx:float=1; xy:float=0; yx:float=0; yy:float=1; tx:float=0; ty:float=0
    def point(self,x,y):return [self.xx*x+self.yx*y+self.tx,self.xy*x+self.yy*y+self.ty]
    def compose(self,b):
        return Transform(self.xx*b.xx+self.yx*b.xy,self.xy*b.xx+self.yy*b.xy,
                         self.xx*b.yx+self.yx*b.yy,self.xy*b.yx+self.yy*b.yy,
                         self.xx*b.tx+self.yx*b.ty+self.tx,self.xy*b.tx+self.yy*b.ty+self.ty)

def parse_transform(raw):
    result=Transform();end=0
    for match in re.finditer(r'([A-Za-z]+)\s*\(([^)]*)\)',raw or ''):
        if (raw[end:match.start()]).strip(' ,\t\r\n'):raise ValueError('Malformed SVG transform')
        name=match[1];body=match[2];tokens=re.findall(NUMBER,body)
        if re.sub(NUMBER,'',body).strip(' ,\t\r\n'):raise ValueError('Malformed SVG transform arguments')
        args=[float(t) for t in tokens]
        if not all(math.isfinite(x) for x in args):raise ValueError('Non-finite transform')
        if name=='matrix' and len(args)==6:t=Transform(*args)
        elif name=='translate' and len(args) in (1,2):t=Transform(tx=args[0],ty=args[1] if len(args)==2 else 0)
        elif name=='scale' and len(args) in (1,2):t=Transform(xx=args[0],yy=args[-1])
        elif name=='rotate' and len(args) in (1,3):
            a=math.radians(args[0]);t=Transform(math.cos(a),math.sin(a),-math.sin(a),math.cos(a))
            if len(args)==3:t=Transform(tx=args[1],ty=args[2]).compose(t).compose(Transform(tx=-args[1],ty=-args[2]))
        elif name in ('skewX','skewY') and len(args)==1:
            v=math.tan(math.radians(args[0]));t=Transform(yx=v) if name=='skewX' else Transform(xy=v)
        else:raise ValueError('Unsupported SVG transform: '+name)
        result=result.compose(t);end=match.end()
    if (raw or '')[end:].strip(' ,\t\r\n'):raise ValueError('Malformed SVG transform')
    return result

def rgb(raw):
    raw=str(raw).strip().lower()
    if raw in {'black','white'}:return [0,0,0] if raw=='black' else [255,255,255]
    if re.fullmatch(r'#[0-9a-f]{3}',raw):raw='#'+''.join(c*2 for c in raw[1:])
    if re.fullmatch(r'#[0-9a-f]{6}',raw):return [int(raw[i:i+2],16) for i in (1,3,5)]
    match=re.fullmatch(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',raw)
    if match and all(0<=int(c)<=255 for c in match.groups()):return [int(c) for c in match.groups()]
    raise ValueError('Explicit RGB fill required for live text: '+raw)

def parse_atom(element,transform,presentation,opacity,index):
    if element.tag.rsplit('}',1)[-1]!='text':raise ValueError('Live text parser accepts only text')
    if list(element):raise ValueError('Nested text must be split into live runs')
    presentation={**presentation,**element.attrib}
    sx=math.hypot(transform.xx,transform.xy);sy=math.hypot(transform.yx,transform.yy)
    dot=transform.xx*transform.yx+transform.xy*transform.yy
    if sx<=0 or sy<=0 or transform.xx*transform.yy-transform.xy*transform.yx<=0 or abs(dot)>1e-6*sx*sy:
        raise ValueError('Text skew/reflection/zero scale needs explicit reconstruction')
    if any(presentation.get(k,'0') not in ('0','','0px') for k in ('dx','dy')):
        raise ValueError('Text dx/dy needs an explicit baseline')
    p=transform.point(parse_number(presentation.get('x')),parse_number(presentation.get('y')))
    size=parse_number(presentation.get('font-size'),16)
    if size<=0:raise ValueError('Positive text font size required')
    fill_opacity=parse_number(presentation.get('fill-opacity'),1)
    if not 0<=opacity<=1 or not 0<=fill_opacity<=1:raise ValueError('Opacity outside 0..1')
    return {'kind':'text','sourceId':element.get('id',f'text-{index}'),'text':{
        'contents':element.text or '', 'fontFamily':presentation.get('font-family','Arial'),
        'fontWeight':presentation.get('font-weight','normal'),'fontStyle':presentation.get('font-style','normal'),
        'position':[rounded(v) for v in p],'fontSize':rounded(size*sy),
        'horizontalScale':rounded(sx/sy*100),'fillColor':rgb(presentation.get('fill','#000000')),
        'opacity':rounded(opacity*fill_opacity*100),'rotationDegrees':rounded(math.degrees(math.atan2(transform.xy,transform.xx))),
        'textAnchor':presentation.get('text-anchor','start'),
        'letterSpacing':rounded(parse_number(presentation.get('letter-spacing'),0)*sy)}}

def collect_atoms(root):
    # Native SVG coordinates must match the declared canvas; unsupported
    # viewport remapping fails visibly rather than shifting text silently.
    if root.get('viewBox'):
        box=[float(x) for x in re.split(r'[\s,]+',root.get('viewBox').strip())]
        width=parse_number(root.get('width'),box[2]);height=parse_number(root.get('height'),box[3])
        if len(box)!=4 or box!=[0,0,width,height]:raise ValueError('Reconstruct live text in canvas coordinates before native import')
    records=[]
    inherited={'font-family','font-weight','font-style','font-size','fill','fill-opacity','text-anchor','letter-spacing','visibility'}
    def walk(node,parent_transform,presentation,opacity):
        tag=node.tag.rsplit('}',1)[-1]
        if tag in {'defs','metadata','title','desc'}:return
        own=dict(node.attrib)
        if 'style' in own:
            for pair in own['style'].split(';'):
                if pair.strip():
                    key,value=pair.split(':',1);own[key.strip()]=value.strip()
        if own.get('display')=='none':return
        current={k:v for k,v in presentation.items() if k in inherited};current.update(own)
        combined=parent_transform.compose(parse_transform(own.get('transform','')))
        opacity*=parse_number(own.get('opacity'),1)
        if tag=='text':
            if current.get('visibility')!='hidden' and (node.text or '').strip():
                records.append(parse_atom(node,combined,current,opacity,len(records)))
        else:
            for child in node:walk(child,combined,current,opacity)
    walk(root,Transform(),{},1)
    return records

def load_parser():
    """Compatibility facade for native preparer; all implementation is bundled."""
    return sys.modules[__name__]
