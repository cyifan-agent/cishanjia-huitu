"""Load exact local font families for rendering, normalizing legacy family aliases."""
from __future__ import annotations
import os,xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from fontTools.ttLib import TTFont

@lru_cache(maxsize=1)
def local_faces():
    """Metadata only; local fonts are never packaged in the delivered artwork."""
    records=[]
    dirs=[Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts',Path.home()/'AppData/Local/Microsoft/Windows/Fonts']
    for directory in dirs:
        if not directory.is_dir():continue
        for source in directory.iterdir():
            if source.suffix.lower() not in {'.ttf','.otf'}:continue
            try:
                with TTFont(source,lazy=True) as font:
                    legacy=font['name'].getDebugName(1) or ''
                    preferred=font['name'].getDebugName(16) or legacy
                    style=(font['name'].getDebugName(2) or '').lower()
                    weight=int(font['OS/2'].usWeightClass) if 'OS/2' in font else (700 if 'bold' in style else 400)
                    italic=('italic' in style or 'oblique' in style or ('post' in font and font['post'].italicAngle!=0))
                    records.append({'file':str(source),'legacy':legacy,'preferred':preferred,'weight':weight,'italic':bool(italic)})
            except Exception:continue
    return records

def resolve_font_file(family,weight='normal',style='normal'):
    wanted=700 if str(weight).lower()=='bold' else 400 if str(weight).lower()=='normal' else int(weight)
    italic=str(style).lower() in {'italic','oblique'}
    faces=[face for face in faces_for_family(family) if face['italic']==italic and (face['weight']>=600)==(wanted>=600)]
    if not faces:raise ValueError(f'FONT_PREVIEW_STYLE_MISSING|{family}|{weight}|{style}')
    return min(faces,key=lambda face:abs(face['weight']-wanted))['file']

def faces_for_family(family):
    # Arial Narrow has typographic family Arial. Exact legacy matches must
    # outrank that alias, independently of set order or Python hash seed.
    legacy=[face for face in local_faces() if face['legacy'].casefold()==family.casefold()]
    if legacy:return legacy
    return [face for face in local_faces() if face['preferred'].casefold()==family.casefold()]

def font_files_for_svg(svg:Path,out:Path)->list[str]:
    families=set()
    for node in ET.parse(svg).getroot().iter():
        if node.tag.rsplit('}',1)[-1]=='text':
            family=node.get('font-family','Arial').split(',')[0].strip(" '\"")
            resolve_font_file(family,node.get('font-weight','normal'),node.get('font-style','normal'))
            families.add(family)
    if not families:return []
    matches={family:[] for family in families}
    out.mkdir(parents=True,exist_ok=True)
    for family in sorted(families):
        for face in faces_for_family(family):
            source=Path(face['file'])
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
