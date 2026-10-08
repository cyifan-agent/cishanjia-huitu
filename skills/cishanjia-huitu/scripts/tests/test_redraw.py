"""Redraw regressions: synthetic vectors only, no Illustrator/API/user image."""
from pathlib import Path
import sys,tempfile,json,copy,unittest,xml.etree.ElementTree as ET,subprocess
sys.dont_write_bytecode=True
SCRIPTS=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SCRIPTS))
from redraw_audit import audit,SCHEMA
from compose_scene import curved_arrow_parts
from object_groups import group_attributes
from svg_contract import SVG_NS
from quality_gate import build,CHECKS

class RedrawTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def write(self,name,obj):
        path=self.path/name;path.write_text(json.dumps(obj),encoding='utf-8');return path
    def fixture(self,termination='arrow',dashed=False):
        root=ET.Element('{'+SVG_NS+'}svg',{'width':'240','height':'160','viewBox':'0 0 240 160','data-huitu-grouping':'semantic-v1','data-huitu-build':SCHEMA})
        bg=ET.SubElement(root,'{'+SVG_NS+'}g',group_attributes('background','Backdrop','background'))
        ET.SubElement(bg,'{'+SVG_NS+'}rect',{'id':'bg','width':'240','height':'160','fill':'#ddd'})
        protein=ET.SubElement(root,'{'+SVG_NS+'}g',group_attributes('protein','Protein','protein'))
        ET.SubElement(protein,'{'+SVG_NS+'}ellipse',{'id':'protein-body','cx':'180','cy':'100','rx':'18','ry':'12','fill':'#9cf'})
        arrow=ET.SubElement(root,'{'+SVG_NS+'}g',group_attributes('arrow','Arrow','connector'))
        route={'points':[[20,35],[60,10],[90,70],[125,50]],'stroke':'#20b85b','stroke_width':3,'termination':termination,'head':16,'cap_width':24,'dashed':dashed,'dash':10,'gap':7}
        generated=ET.fromstring('<g xmlns="'+SVG_NS+'">'+''.join(curved_arrow_parts(route,'arrow'))+'</g>')
        for n in generated:arrow.append(n)
        objects=[]
        for g in root:
            parts=[]
            for n in g:
                role='shape'
                if g.get('id')=='arrow':role='cap' if n.get('id').endswith('cap') else 'head' if n.tag.endswith('polygon') else 'dash' if 'dash' in n.get('id') else 'shaft'
                parts.append({'id':n.get('id'),'role':role})
            spec={'id':g.get('id'),'construction':'authored','reference_features':['Synthetic source-specific contour'],'parts':parts}
            if g.get('id')=='arrow':spec['connector']=route
            objects.append(spec)
        svg=self.path/'master.svg';ET.ElementTree(root).write(svg,encoding='utf-8')
        plan=self.write('drawing-plan.json',{'schema':SCHEMA,'canvas':[240,160],'objects':objects})
        return svg,plan,root,arrow
    def save(self,svg,root):ET.ElementTree(root).write(svg,encoding='utf-8')
    def add_part(self,plan,ident,role='shaft'):
        data=json.loads(plan.read_text());data['objects'][-1]['parts'].append({'id':ident,'role':role});self.write(plan.name,data)
    def test_clean_curved_arrow_and_all_siblings_remain_independent(self):
        svg,plan,_,_=self.fixture();report=audit(svg,plan,self.path/'checks')
        self.assertEqual(report['status'],'PASS',report['errors'])
        self.assertTrue(report['connectors'][0]['sibling_containers_unchanged'])
        moved=ET.parse(self.path/'checks/arrow-moved.svg').getroot();original=ET.parse(svg).getroot()
        self.assertEqual(ET.tostring(moved[1]),ET.tostring(original[1]))
        self.assertTrue((self.path/'checks/arrow-isolated.png').is_file())
        self.assertEqual(len(ET.parse(self.path/'checks/arrow-hidden.svg').getroot()),2)
    def test_inhibition_tbar_is_perpendicular_to_endpoint_tangent(self):
        svg,plan,_,arrow=self.fixture('inhibition');report=audit(svg,plan)
        self.assertEqual(report['status'],'PASS',report['errors']);self.assertFalse(any(n.tag.endswith('polygon') for n in arrow))
        cap=arrow[-1];dx=float(cap.get('x2'))-float(cap.get('x1'));dy=float(cap.get('y2'))-float(cap.get('y1'))
        self.assertAlmostEqual(dx*35+dy*(-20),0,delta=.01)
    def test_dashed_arrow_remains_complete(self):
        svg,plan,_,_=self.fixture(dashed=True);self.assertEqual(audit(svg,plan)['status'],'PASS')
    def test_uncapped_leader_is_supported(self):
        svg,plan,_,_=self.fixture('none');self.assertEqual(audit(svg,plan)['status'],'PASS')
    def test_foreign_protein_in_arrow_is_rejected_even_if_declared(self):
        svg,plan,root,arrow=self.fixture();ET.SubElement(arrow,'{'+SVG_NS+'}ellipse',{'id':'foreign','cx':'180','cy':'100','rx':'18','ry':'12','fill':'#9cf'})
        self.add_part(plan,'foreign');self.save(svg,root)
        report=audit(svg,plan);self.assertEqual(report['status'],'FAIL');self.assertTrue(any('foreign object' in e for e in report['errors']))
    def test_foreign_path_in_arrow_is_detected_by_route_geometry(self):
        svg,plan,root,arrow=self.fixture();ET.SubElement(arrow,'{'+SVG_NS+'}path',{'id':'foreign','d':'M170 90H190V110H170Z','fill':'#9cf'})
        self.add_part(plan,'foreign');self.save(svg,root)
        report=audit(svg,plan);self.assertEqual(report['status'],'FAIL');self.assertTrue(any('outside' in e for e in report['errors']))
    def test_arrow_cannot_carry_neighbor_label(self):
        svg,plan,root,arrow=self.fixture();ET.SubElement(arrow,'{'+SVG_NS+'}text',{'id':'foreign','x':'70','y':'100','font-size':'12'}).text='Protein'
        self.add_part(plan,'foreign','text');self.save(svg,root)
        self.assertTrue(any('text/captions' in e for e in audit(svg,plan)['errors']))
    def test_missing_head_cannot_pass_with_good_shaft(self):
        svg,plan,root,arrow=self.fixture();arrow.remove(arrow[-1]);self.save(svg,root)
        data=json.loads(plan.read_text());data['objects'][-1]['parts'].pop();self.write(plan.name,data)
        report=audit(svg,plan);self.assertEqual(report['status'],'FAIL');self.assertTrue(any('incomplete' in e for e in report['errors']))
    def test_color_mesh_is_rejected_despite_whole_object_groups(self):
        svg,plan,root,_=self.fixture();root.set('data-huitu-build','source-color-mesh');self.save(svg,root)
        self.assertEqual(audit(svg,plan)['status'],'FAIL')
    def test_renamed_pixel_mosaic_cannot_masquerade_as_authored_paths(self):
        svg,plan,root,_=self.fixture();protein=root[1];protein.clear();protein.attrib.update(group_attributes('protein','Protein','protein'))
        d=' '.join(f'M{20+i%10} {100+i//10}h1v1h-1Z' for i in range(100))
        ET.SubElement(protein,'{'+SVG_NS+'}path',{'id':'protein-body','d':d,'fill':'#9cf'});self.save(svg,root)
        self.assertTrue(any('pixel tiles' in e for e in audit(svg,plan)['errors']))
    def test_long_vector_dna_rungs_are_not_misclassified_as_pixels(self):
        svg,plan,root,_=self.fixture();body=root[1][0]
        root[1].remove(body)
        d=' '.join(f'M{20+i*2} 100h1v20h-1Z' for i in range(100))
        ET.SubElement(root[1],'{'+SVG_NS+'}path',{'id':'protein-body','d':d,'fill':'#9cf'})
        self.save(svg,root)
        report=audit(svg,plan);self.assertEqual(report['status'],'PASS',report['errors'])
    def test_plan_cannot_omit_real_foreground_parts(self):
        svg,plan,root,arrow=self.fixture();ET.SubElement(arrow,'{'+SVG_NS+'}line',{'id':'extra','x1':'10','y1':'120','x2':'50','y2':'120','stroke':'#222'});self.save(svg,root)
        self.assertTrue(any('contents' in e for e in audit(svg,plan)['errors']))
    def test_native_bridge_rejects_legacy_qa_before_any_illustrator_connection(self):
        import hashlib
        svg,_,_,_=self.fixture();qa=self.write('qa.json',{'status':'PASS','svg_sha256':hashlib.sha256(svg.read_bytes()).hexdigest()})
        result=subprocess.run(['powershell.exe','-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',str(SCRIPTS/'native_svg_import.ps1'),'-InputSvg',str(svg),'-QaReport',str(qa),'-WorkDir',str(self.path/'native'),'-OutputAi',str(self.path/'a.ai'),'-OutputPng',str(self.path/'a.png'),'-DryRun'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('HUITU_REDRAW_REQUIRED',result.stderr)
    def test_final_gate_rejects_mesh_even_with_all_visual_checks_marked_pass(self):
        import hashlib
        svg,plan,root,_=self.fixture();root.set('data-huitu-build','source-color-mesh');self.save(svg,root)
        digest=hashlib.sha256(svg.read_bytes()).hexdigest()
        metrics=self.write('metrics.json',{'svg_sha256':digest,'threshold_failures':[],'regions':[]})
        review=self.write('review.json',{'svg_sha256':digest,'checks':{k:{'status':'pass','evidence':'Synthetic adversarial fixture only'} for k in CHECKS},'unresolved_issues':[]})
        report=build(svg,metrics,review,drawing_plan=plan)
        self.assertEqual(report['status'],'FAIL');self.assertEqual(report['construction'],'unverified')
    def test_editability_dry_run_does_not_connect_to_illustrator(self):
        self.write('native-config.json',{'sha256':'synthetic','grouping':'semantic-v1'})
        self.write('native-import-report.json',{'status':'PASS','svg_sha256':'synthetic'})
        result=subprocess.run(['powershell.exe','-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',str(SCRIPTS/'verify_native_editability.ps1'),'-NativeWorkDir',str(self.path),'-OutputReport',str(self.path/'result.json'),'-DryRun'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('no Illustrator connection',result.stdout)

if __name__=='__main__':
    report_arg=None
    if '--report' in sys.argv:report_arg=Path(sys.argv[sys.argv.index('--report')+1])
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RedrawTests))
    report={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'user_images_processed':False,'illustrator_contacted':False,'api_requests':0}
    if report_arg:report_arg.write_text(json.dumps(report,indent=2),encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
