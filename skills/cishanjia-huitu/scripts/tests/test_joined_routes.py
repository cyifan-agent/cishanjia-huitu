from pathlib import Path
import sys,copy,unittest,importlib.util,xml.etree.ElementTree as E,json
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P))
from compose_scene import curved_arrow_parts
from redraw_audit import audit
S=P
loader=importlib.util.spec_from_file_location('base_redraw_tests',S/'tests/test_redraw.py');module=importlib.util.module_from_spec(loader);loader.loader.exec_module(module)
class Routes(module.RedrawTests):
 def composite(self):
  svg,plan,root,arrow=self.fixture();data=json.loads(plan.read_text());cfg=data['objects'][-1]['connector'];cfg['segments']=[[[20,35],[40,35],[60,35],[80,35]],[[80,35],[80,50],[80,65],[80,80]]];cfg.pop('points')
  arrow.clear();arrow.attrib.update({'id':'arrow','data-huitu-object-id':'arrow','data-huitu-kind':'connector','data-huitu-name':'Elbow arrow'})
  nodes=E.fromstring('<g xmlns="http://www.w3.org/2000/svg">'+''.join(curved_arrow_parts(cfg,'arrow'))+'</g>')
  for n in nodes:arrow.append(n)
  data['objects'][-1]['parts']=[{'id':n.get('id'),'role':'head' if n.tag.endswith('polygon') else 'shaft'} for n in arrow]
  self.save(svg,root);self.write(plan.name,data);return svg,plan,root,arrow,cfg
 def test_connected_elbow_stays_one_owner_with_one_terminal_head(self):
  svg,plan,_,arrow,_=self.composite();r=audit(svg,plan);self.assertEqual(r['status'],'PASS',r['errors']);self.assertEqual(len(arrow),3);self.assertEqual(sum(n.tag.endswith('polygon') for n in arrow),1)
 def test_disconnected_elbow_rejected(self):
  _,_,_,_,cfg=self.composite();cfg['segments'][1][0]=[81,35]
  with self.assertRaisesRegex(ValueError,'join'):curved_arrow_parts(cfg,'arrow')
 def test_nonfinite_segment_rejected(self):
  _,_,_,_,cfg=self.composite();cfg['segments'][1][1]=[float('nan'),50]
  with self.assertRaisesRegex(ValueError,'finite'):curved_arrow_parts(cfg,'arrow')
 def test_connected_fork_has_only_declared_terminal_arrow(self):
  cfg={'stroke':'#334a6a','stroke_width':3,'branches':[{'points':[[20,20],[20,30],[20,40],[20,50]],'termination':'none'},{'points':[[20,80],[20,70],[20,60],[20,50]],'termination':'none'},{'points':[[20,50],[40,50],[60,50],[80,50]],'termination':'arrow'}]}
  parts=curved_arrow_parts(cfg,'fork');self.assertEqual(sum('<polygon' in p for p in parts),1);self.assertEqual(len(parts),4)
  cfg['branches'][1]['points']=[[40,80],[40,70],[40,60],[40,50]]
  with self.assertRaisesRegex(ValueError,'junction'):curved_arrow_parts(cfg,'fork')
 def test_inhibition_elbow_has_one_cap_no_head(self):
  _,_,_,_,cfg=self.composite();cfg['termination']='inhibition';parts=curved_arrow_parts(cfg,'arrow');self.assertEqual(sum('-cap"' in p for p in parts),1);self.assertFalse(any('<polygon' in p for p in parts))
 def test_missing_terminal_head_fails_route_check(self):
  svg,plan,root,arrow,cfg=self.composite();arrow.remove(arrow[-1]);self.save(svg,root);data=json.loads(plan.read_text());data['objects'][-1]['parts'].pop();self.write(plan.name,data);self.assertEqual(audit(svg,plan)['status'],'FAIL')
 def test_foreign_fragment_on_second_segment_fails(self):
  svg,plan,root,arrow,cfg=self.composite();E.SubElement(arrow,'{http://www.w3.org/2000/svg}path',id='foreign',d='M150 120h10v10h-10Z',fill='#333');self.save(svg,root);data=json.loads(plan.read_text());data['objects'][-1]['parts'].append({'id':'foreign','role':'shaft'});self.write(plan.name,data);self.assertEqual(audit(svg,plan)['status'],'FAIL')
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Routes));print(json.dumps({'tests':result.testsRun,'passed':result.wasSuccessful(),'illustrator_contacted':False,'api_requests':0}));raise SystemExit(0 if result.wasSuccessful() else 1)
