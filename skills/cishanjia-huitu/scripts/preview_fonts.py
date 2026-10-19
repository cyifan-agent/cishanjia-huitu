"""Load exact local font families for rendering, normalizing legacy family aliases."""
from __future__ import annotations
import os,xml.etree.ElementTree as ET,hashlib,json,tempfile,uuid
from functools import lru_cache
from pathlib import Path
from fontTools.ttLib import TTFont,TTCollection
from fontTools import version as fonttools_version

@lru_cache(maxsize=1)
def local_faces():
    """Metadata only; local fonts are never packaged in the delivered artwork."""
    records=[]
    dirs=[Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts',Path.home()/'AppData/Local/Microsoft/Windows/Fonts']
    for directory in dirs:
        if not directory.is_dir():continue
        for source in directory.iterdir():
            if source.suffix.lower() not in {'.ttf','.otf','.ttc','.otc'}:continue
            try:
                collection=TTCollection(source,lazy=True) if source.suffix.lower() in {'.ttc','.otc'} else None
                fonts=collection.fonts if collection is not None else [TTFont(source,lazy=True)]
                for index,font in enumerate(fonts):
                    legacy=font['name'].getDebugName(1) or ''
                    preferred=font['name'].getDebugName(16) or legacy
                    style=(font['name'].getDebugName(2) or '').lower()
                    weight=int(font['OS/2'].usWeightClass) if 'OS/2' in font else (700 if 'bold' in style else 400)
                    italic=('italic' in style or 'oblique' in style or ('post' in font and font['post'].italicAngle!=0))
                    axes={a.axisTag:[a.minValue,a.defaultValue,a.maxValue] for a in font['fvar'].axes} if 'fvar' in font else {}
                    records.append({'file':str(source),'legacy':legacy,'preferred':preferred,'weight':weight,'italic':bool(italic),'variable_axes':axes,'font_index':index if collection is not None else None})
                if collection is not None:collection.close()
                else:fonts[0].close()
            except Exception:continue
    return records

def resolve_font_file(family,weight='normal',style='normal',cache_dir=None):
    wanted=700 if str(weight).lower()=='bold' else 400 if str(weight).lower()=='normal' else int(weight)
    italic=str(style).lower() in {'italic','oblique'}
    def accepts(face):
        axis=face.get('variable_axes',{}).get('wght')
        return face['italic']==italic and ((axis and axis[0]<=wanted<=axis[2]) or (not axis and (face['weight']>=600)==(wanted>=600)))
    faces=[face for face in faces_for_family(family) if accepts(face)]
    if not faces:raise ValueError(f'FONT_PREVIEW_STYLE_MISSING|{family}|{weight}|{style}')
    face=min(faces,key=lambda face:(0 if face.get('variable_axes',{}).get('wght') else abs(face['weight']-wanted),bool(face.get('variable_axes'))))
    return variable_instance(face,family,wanted,cache_dir) if face.get('variable_axes') or face.get('font_index') is not None else face['file']

def variable_instance(face,family,weight,cache_dir=None):
    """Static preview font cache keyed by source bytes; never edit installed fonts."""
    from fontTools.varLib.instancer import instantiateVariableFont
    source=Path(face['file']);raw=source.read_bytes()
    key=hashlib.sha256(raw+json.dumps({'family':family,'weight':weight,'font_index':face.get('font_index'),'fonttools':fonttools_version,'tool':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},sort_keys=True).encode()).hexdigest()
    folder=Path(cache_dir) if cache_dir is not None else Path(tempfile.gettempdir())/'huitu-font-instances-v1'
    folder.mkdir(parents=True,exist_ok=True);destination=folder/(key+'.ttf');meta=folder/(key+'.json')
    try:
        if destination.is_file() and json.loads(meta.read_text(encoding='utf-8')).get('sha256')==hashlib.sha256(destination.read_bytes()).hexdigest():return str(destination)
    except (OSError,ValueError,TypeError):pass
    font=TTFont(source,recalcTimestamp=False,fontNumber=face['font_index'] if face.get('font_index') is not None else -1)
    try:
        axes={a.axisTag:a.defaultValue for a in font['fvar'].axes} if 'fvar' in font else {}
        if 'wght' in axes:axes['wght']=weight
        else:weight=face['weight']
        if axes:font=instantiateVariableFont(font,axes,inplace=True)
        font.recalcTimestamp=False
        style='Bold' if weight>=600 else 'Regular'
        for record in list(font['name'].names):
            if record.nameID in {1,16}:value=family
            elif record.nameID in {2,17}:value=style
            elif record.nameID==6:value='HuituPreview-'+key[:20]
            else:continue
            font['name'].setName(value,record.nameID,record.platformID,record.platEncID,record.langID)
        font['OS/2'].usWeightClass=weight
        font['OS/2'].fsSelection=(font['OS/2'].fsSelection & ~0x60) | (0x20 if weight>=600 else 0x40)
        font['head'].macStyle=(font['head'].macStyle & ~1) | int(weight>=600)
        pending=destination.with_suffix('.'+uuid.uuid4().hex+'.tmp')
        try:font.save(pending);pending.replace(destination)
        finally:
            if pending.exists():pending.unlink()
    finally:font.close()
    meta.write_text(json.dumps({'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}),encoding='utf-8')
    return str(destination)

def faces_for_family(family):
    # Arial Narrow has typographic family Arial. Exact legacy matches must
    # outrank that alias, independently of set order or Python hash seed.
    legacy=[face for face in local_faces() if face['legacy'].casefold()==family.casefold()]
    if legacy:return legacy
    return [face for face in local_faces() if face['preferred'].casefold()==family.casefold()]

def font_files_for_svg(svg:Path,out:Path,cache_dir=None)->list[str]:
    requests=set();runs=[]
    def walk(node,inherited):
        own=dict(inherited);own.update(node.attrib)
        for pair in node.get('style','').split(';'):
            if ':' in pair:
                k,v=pair.split(':',1);own[k.strip()]=v.strip()
        if node.tag.rsplit('}',1)[-1]=='text':
            family=own.get('font-family','Arial').split(',')[0].strip(" '\"")
            request=(family,own.get('font-weight','normal'),own.get('font-style','normal'));requests.add(request);runs.append((request,node.text or ''))
        for child in node:walk(child,own)
    walk(ET.parse(svg).getroot(),{})
    if not requests:return []
    families={v[0] for v in requests};matches={family:[] for family in families}
    out.mkdir(parents=True,exist_ok=True)
    resolved={request:resolve_font_file(*request,cache_dir=cache_dir) for request in requests};cmaps={}
    for request,content in runs:
        selected=resolved[request]
        if selected not in cmaps:
            with TTFont(selected,lazy=True) as font:cmaps[selected]=font.getBestCmap() or {}
        cmap=cmaps[selected]
        import unicodedata
        missing=sorted({ord(ch) for ch in content if not ch.isspace() and unicodedata.category(ch)!='Cf' and not (0xFE00<=ord(ch)<=0xFE0F or 0xE0100<=ord(ch)<=0xE01EF) and ord(ch) not in cmap})
        if missing:raise ValueError('FONT_PREVIEW_GLYPH_MISSING|'+request[0]+'|'+','.join(f'U+{n:04X}' for n in missing))
    for family in sorted(families):
        sources={resolved[request] for request in requests if request[0]==family}
        for source_path in sorted(sources):
            source=Path(source_path)
            try:
                font=TTFont(source,lazy=True)
                legacy=font['name'].getDebugName(1) or ''
                preferred=font['name'].getDebugName(16) or legacy
                # fontdb prefers typographic names. Windows/Illustrator may
                # instead identify Arial Narrow by its legacy family name.
                if family.casefold()==legacy.casefold() and preferred.casefold()!=legacy.casefold():
                    style=font['name'].getDebugName(2) or 'Regular'
                    for record in list(font['name'].names):
                        if record.nameID in {16,17}:
                            font['name'].setName(family if record.nameID==16 else style,record.nameID,
                                                 record.platformID,record.platEncID,record.langID)
                    font['name'].setName(family,16,3,1,1033)
                    font['name'].setName(style,17,3,1,1033)
                    destination=out/(source.stem+'-preview'+source.suffix)
                    # Preview alias normalization must be deterministic across
                    # sessions; timestamp-only changes are not new glyphs.
                    font.recalcTimestamp=False
                    font.save(destination);matches[family].append(str(destination))
                else:matches[family].append(str(source))
                font.close()
            except Exception:
                continue
    missing=[family for family,files in matches.items() if not files]
    if missing:raise ValueError('FONT_PREVIEW_MISSING|'+','.join(missing))
    return [file for files in matches.values() for file in files]
