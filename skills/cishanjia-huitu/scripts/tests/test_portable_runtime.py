"""Portable release checks; no external skill, Illustrator, network or user art."""
from pathlib import Path
import sys, tempfile, unittest, xml.etree.ElementTree as E, math, json
SCRIPTS=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SCRIPTS))
from svg_text_geometry import Transform,parse_transform,parse_atom,collect_atoms
from setup_runtime import configure

class PortableTests(unittest.TestCase):
    def test_inherited_text_matrix_opacity_and_rotation(self):
        root=E.fromstring('<svg width="100" height="80" viewBox="0 0 100 80" font-family="Arial" fill="#123"><g transform="translate(10 20) rotate(30) scale(.6 1)" opacity=".5"><text id="t" x="10" y="20" font-size="20" fill-opacity=".8">DNA</text></g></svg>')
        t=collect_atoms(root)[0]['text'];expected=Transform(tx=10,ty=20).compose(parse_transform('rotate(30) scale(.6 1)')).point(10,20)
        for a,b in zip(t['position'],expected):self.assertAlmostEqual(a,b,places=5)
        self.assertEqual(t['opacity'],40);self.assertEqual(t['horizontalScale'],60);self.assertEqual(t['fontSize'],20);self.assertEqual(t['rotationDegrees'],30)
        self.assertEqual(t['fillColor'],[17,34,51])
    def test_rotate_about_pivot(self):
        self.assertEqual([round(v,6) for v in parse_transform('rotate(90 10 20)').point(10,25)],[5,20])
    def test_no_inherited_baseline_or_repeated_opacity(self):
        root=E.fromstring('<svg opacity=".5"><g opacity=".4"><text x="20" y="30">A</text><text x="40" y="50">B</text></g></svg>')
        records=collect_atoms(root)
        self.assertEqual([r['text']['opacity'] for r in records],[20,20])
        self.assertEqual(records[1]['text']['position'],[40,50])
    def test_skew_reflection_and_nonfinite_rejected(self):
        for raw in ('skewX(10)','scale(-1 1)','scale(0)'):
            with self.assertRaises(ValueError):parse_atom(E.fromstring('<text>A</text>'),parse_transform(raw),{},1,0)
        with self.assertRaises(ValueError):parse_transform('translate(1) trailing')
    def test_viewport_mismatch_fails_visibly(self):
        with self.assertRaisesRegex(ValueError,'canvas coordinates'):collect_atoms(E.fromstring('<svg width="100" height="80" viewBox="0 0 50 40"><text>A</text></svg>'))
    def test_runtime_config_uses_relative_private_dependency_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=configure(root,sys.executable,{'illustrator_progid':'Illustrator.Application.30'})
            self.assertEqual(config['package_roots'],['.deps']);self.assertEqual(config['illustrator_progid'],'Illustrator.Application.30')
            self.assertEqual(json.loads((root/'runtime.local.json').read_text(encoding='utf-8')),config)
    def test_bridge_has_no_app_launch_or_fixed_version(self):
        text=(SCRIPTS/'illustrator_connection.ps1').read_text(encoding='utf-8')
        self.assertNotIn('New-Object',text);self.assertNotIn('Illustrator.Application.30',text)
        self.assertIn('GetActiveObject',text)
        for name in ('native_svg_import.ps1','export_native_figure.ps1','verify_symbol_editability.ps1','verify_native_editability.ps1'):
            body=(SCRIPTS/name).read_text(encoding='utf-8');self.assertIn('Get-HuituActiveIllustrator',body);self.assertNotIn("GetActiveObject('Illustrator.Application.30')",body)

if __name__=='__main__':unittest.main()
