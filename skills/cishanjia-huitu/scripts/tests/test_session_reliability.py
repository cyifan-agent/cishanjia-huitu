"""Synthetic connection, text and target regressions. Never attach to Illustrator."""
import hashlib, importlib, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
from runtime_env import bootstrap
bootstrap()

class SessionTests(unittest.TestCase):
    def test_connection_fast_path_and_restart_with_fake_backends(self):
        host=shutil.which('powershell.exe')
        if not host:self.skipTest('Windows PowerShell required for injected backend test')
        r=subprocess.run([host,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(Path(__file__).with_name('connection_session_test.ps1')),str(SCRIPTS/'illustrator_connection.ps1')],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('MOCK_CONNECTION_PASS',r.stdout)
    def test_native_fonts_targets_and_live_text_with_mocks(self):
        host=os.environ.get('HUITU_NODE') or shutil.which('node')
        if not host:self.skipTest('Node required for mocked native tests')
        r=subprocess.run([host,str(Path(__file__).with_name('native_session_test.js')),str(SCRIPTS)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('NATIVE_SESSION_PASS',r.stdout)
        r=subprocess.run([host,str(Path(__file__).with_name('native_identity_test.js')),str(SCRIPTS)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('NATIVE_IDENTITY_PASS',r.stdout)
    def test_native_cli_dry_run_preserves_target_and_bound_fit(self):
        host=shutil.which('powershell.exe')
        if not host:self.skipTest('Windows PowerShell required for dry-run bridge test')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);svg=root/'m.svg'
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" data-huitu-build="vector-redraw-v1" data-huitu-grouping="semantic-v1"><g id="label" data-huitu-object-id="label" data-huitu-name="Label" data-huitu-kind="label"><text id="t" x="5" y="20" font-family="Arial" font-size="12">A+</text></g></svg>')
            digest=hashlib.sha256(svg.read_bytes()).hexdigest();qa=root/'qa.json';fit=root/'fit.json'
            qa.write_text(json.dumps({'status':'PASS','svg_sha256':digest,'construction':'vector-redraw-v1','connector_geometry_passed':True}))
            fit.write_text(json.dumps({'svg_sha256':digest,'text_elements':[{'id':'t','content':'A+','bbox_px':[10,20,30,12]}]}))
            args=[host,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(SCRIPTS/'native_svg_import.ps1'),'-InputSvg',str(svg),'-QaReport',str(qa),'-WorkDir',str(root/'job'),'-OutputAi',str(root/'out.ai'),'-OutputPng',str(root/'out.png'),'-TargetDocumentPath',str(root/'existing.ai'),'-TextFitManifest',str(fit),'-DryRun']
            r=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            config=json.loads((root/'job'/'native-dry-run.json').read_text(encoding='utf-8-sig'))
            self.assertEqual(config['labels'][0]['nativeFit']['bbox_px'],[10,20,30,12]);self.assertEqual(config['targetDocumentPath'],str(root/'existing.ai'))
            self.assertFalse((root/'out.ai').exists())
    def test_native_text_fit_manifest_binds_current_svg_and_exact_run(self):
        mod=importlib.import_module('native_text_fit')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);svg=root/'m.svg';svg.write_text('<svg width="100" height="80"/>')
            m=root/'fit.json';labels=[{'source_id':'t','content':'A+','rotation':0}]
            data={'svg_sha256':hashlib.sha256(svg.read_bytes()).hexdigest(),'text_elements':[{'id':'t','content':'A+','bbox_px':[10,20,30,12],'tracking':[{'start':1,'length':1,'value':25}]}]}
            def run():m.write_text(json.dumps(data));return mod.attach_fit(svg,labels,m,[100,80])
            result=run();self.assertEqual(result[0]['nativeFit']['bbox_px'],[10,20,30,12]);self.assertNotIn('nativeFit',labels[0])
            for change in ['stale','content','duplicate','outside','rotation','tracking']:
                bad=json.loads(json.dumps(data));test_labels=labels
                if change=='stale':bad['svg_sha256']='old'
                if change=='content':bad['text_elements'][0]['content']='B'
                if change=='duplicate':bad['text_elements']*=2
                if change=='outside':bad['text_elements'][0]['bbox_px']=[90,20,30,12]
                if change=='rotation':test_labels=[dict(labels[0],rotation=30)]
                if change=='tracking':bad['text_elements'][0]['tracking'][0]['start']=2
                m.write_text(json.dumps(bad))
                with self.assertRaises(ValueError,msg=change):mod.attach_fit(svg,test_labels,m,[100,80])
    def test_explicit_relative_drawing_plan_uses_callers_directory(self):
        from quality_gate import build,CHECKS
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);folder=root/'figure';folder.mkdir();svg=folder/'m.svg'
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" data-huitu-build="vector-redraw-v1" data-huitu-grouping="semantic-v1"><g id="background" data-huitu-object-id="background" data-huitu-name="Background" data-huitu-kind="background"><rect id="p" width="100" height="80" fill="#fff"/></g></svg>')
            digest=hashlib.sha256(svg.read_bytes()).hexdigest()
            (folder/'p.json').write_text(json.dumps({'schema':'vector-redraw-v1','canvas':[100,80],'objects':[{'id':'background','construction':'authored','reference_features':['white canvas'],'parts':[{'id':'p','role':'shape'}]}]}))
            (folder/'c.json').write_text(json.dumps({'svg_sha256':digest,'regions':[],'threshold_failures':[]}))
            (folder/'r.json').write_text(json.dumps({'svg_sha256':digest,'checks':{k:{'status':'pass','evidence':'Synthetic fixture only'} for k in CHECKS},'regions':{},'unresolved_issues':[],'drawing_plan':'p.json'}))
            previous=Path.cwd()
            try:
                os.chdir(root)
                result=build(Path('figure/m.svg'),Path('figure/c.json'),Path('figure/r.json'),drawing_plan=Path('figure/p.json'))
                self.assertEqual(result['status'],'PASS',result['errors'])
                self.assertEqual(build(svg,folder/'c.json',folder/'r.json')['status'],'PASS')
            finally:os.chdir(previous)

if __name__=='__main__':unittest.main(verbosity=2)
