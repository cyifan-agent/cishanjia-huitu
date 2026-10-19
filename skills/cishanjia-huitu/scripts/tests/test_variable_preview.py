"""Tiny authored variable fonts; no system font dependency or user artwork."""
from pathlib import Path
import os,sys,tempfile,unittest
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SCRIPTS))
from runtime_env import bootstrap
bootstrap()
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.designspaceLib import DesignSpaceDocument,AxisDescriptor,SourceDescriptor
from fontTools.varLib import build
from fontTools.ttLib import TTFont,TTCollection
from fontTools.varLib.instancer import instantiateVariableFont
import preview_fonts

def tiny_variable(folder,width=80):
    folder.mkdir(exist_ok=True);ds=DesignSpaceDocument();axis=AxisDescriptor();axis.name='Weight';axis.tag='wght';axis.minimum=100;axis.default=100;axis.maximum=900;ds.addAxis(axis)
    for weight,stem in [(100,width),(900,width+160)]:
        fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(['.notdef','space','A','plus']);fb.setupCharacterMap({32:'space',65:'A',43:'plus'})
        glyphs={}
        for name in ['.notdef','space','A','plus']:
            pen=TTGlyphPen(None)
            if name!='space':pen.moveTo((50,0));pen.lineTo((50+stem,0));pen.lineTo((50+stem,700));pen.lineTo((50,700));pen.closePath()
            glyphs[name]=pen.glyph()
        fb.setupGlyf(glyphs);fb.setupHorizontalMetrics({n:(600,50) for n in glyphs});fb.setupHorizontalHeader(ascent=800,descent=-200)
        fb.setupNameTable({'familyName':'Synthetic Variable','styleName':'Thin' if weight==100 else 'Black','uniqueFontIdentifier':'Synthetic-'+str(weight),'fullName':'Synthetic Variable '+str(weight),'psName':'SyntheticVariable-'+str(weight)})
        fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200,usWeightClass=weight);fb.setupPost();fb.setupMaxp()
        p=folder/f'{weight}.ttf';fb.save(p)
        desc=SourceDescriptor();desc.path=str(p.resolve());desc.name=str(weight);desc.location={'Weight':weight};desc.familyName='Synthetic Variable';desc.styleName=str(weight);ds.addSource(desc)
    design=folder/'test.designspace';ds.write(design);font,_,_=build(design);font.recalcTimestamp=False;dest=folder/'variable.ttf';font.save(dest);return dest

class VariableTests(unittest.TestCase):
    def test_ttc_faces_are_discovered_and_materialized(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=tiny_variable(root/'source');fonts=root/'windows'/'Fonts';fonts.mkdir(parents=True)
            col=TTCollection();col.fonts=[instantiateVariableFont(TTFont(source),{'wght':w},inplace=True) for w in (400,700)]
            col.save(fonts/'synthetic.ttc');col.close()
            with patch.dict(os.environ,{'WINDIR':str(root/'windows')}),patch.object(Path,'home',return_value=root/'profile'):
                preview_fonts.local_faces.cache_clear()
                try:
                    faces=preview_fonts.local_faces();self.assertEqual(len(faces),2)
                    p=preview_fonts.resolve_font_file('Synthetic Variable',700,cache_dir=root/'cache')
                    with TTFont(p) as f:self.assertEqual(f['OS/2'].usWeightClass,700)
                finally:preview_fonts.local_faces.cache_clear()
    def test_inherited_family_and_missing_glyph_are_checked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=tiny_variable(root/'source');svg=root/'m.svg'
            faces=[{'file':str(source),'legacy':'Synthetic Variable','preferred':'Synthetic Variable','weight':100,'italic':False,'variable_axes':{'wght':[100,100,900]}}]
            svg.write_text('<svg font-family="Synthetic Variable"><g font-weight="700"><text>A</text></g></svg>')
            with patch.object(preview_fonts,'local_faces',return_value=faces):
                files=preview_fonts.font_files_for_svg(svg,root/'fonts',cache_dir=root/'cache')
                with TTFont(files[0]) as f:self.assertEqual(f['OS/2'].usWeightClass,700)
                svg.write_text('<svg font-family="Synthetic Variable"><text>骨</text></svg>',encoding='utf8')
                with self.assertRaisesRegex(ValueError,'GLYPH_MISSING'):preview_fonts.font_files_for_svg(svg,root/'fonts',cache_dir=root/'cache')
    def test_bold_is_instanced_and_reused_without_changing_source(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=tiny_variable(root/'source');original=source.read_bytes()
            faces=[{'file':str(source),'legacy':'Synthetic Variable','preferred':'Synthetic Variable','weight':100,'italic':False,'variable_axes':{'wght':[100,100,900]}}]
            with patch.object(preview_fonts,'local_faces',return_value=faces):
                normal=Path(preview_fonts.resolve_font_file('Synthetic Variable',400,cache_dir=root/'cache'))
                bold=Path(preview_fonts.resolve_font_file('Synthetic Variable',700,cache_dir=root/'cache'))
                self.assertNotEqual(normal,bold);self.assertEqual(source.read_bytes(),original)
                with TTFont(normal) as f:self.assertNotIn('fvar',f);self.assertEqual(f['OS/2'].usWeightClass,400)
                with TTFont(bold) as f:self.assertEqual(f['OS/2'].usWeightClass,700)
                before=bold.stat().st_mtime_ns
                self.assertEqual(Path(preview_fonts.resolve_font_file('Synthetic Variable',700,cache_dir=root/'cache')),bold)
                self.assertEqual(bold.stat().st_mtime_ns,before)
                saved=bold.read_bytes();bold.write_bytes(b'corrupt')
                self.assertEqual(Path(preview_fonts.resolve_font_file('Synthetic Variable',700,cache_dir=root/'cache')).read_bytes(),saved)
                old=source.stat();tiny_variable(root/'replacement',width=110).replace(source);os.utime(source,ns=(old.st_atime_ns,old.st_mtime_ns))
                self.assertNotEqual(Path(preview_fonts.resolve_font_file('Synthetic Variable',700,cache_dir=root/'cache')),bold)

if __name__=='__main__':unittest.main(verbosity=2)
