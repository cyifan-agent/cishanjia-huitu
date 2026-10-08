"""Behavioral detail/ownership/revision tests on synthetic artwork only."""
import os,shutil,copy,json,re,sys,tempfile,unittest,subprocess,xml.etree.ElementTree as E
from pathlib import Path
sys.dont_write_bytecode=True
SCRIPTS=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SCRIPTS))
from runtime_env import bootstrap
bootstrap()
import numpy as np
from contour_refit import landmark_path,bezier,closed_path
from refine_contour import refine
from feature_audit import audit as feature_audit
from scene_patch import extract,patch,digest,owners,encoded
from object_groups import group_attributes
from compose_scene import curved_arrow_parts
from redraw_audit import audit as redraw_audit
from svg_contract import validate,SVG_NS,local_name
from render_compare import render
from local_reconstruct import write_image
from fit_text import fit as fit_labels
from manifest_lint import lint

class DetailTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory(prefix='huitu-detail-');self.path=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def write(self,name,value):
  p=self.path/name;p.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');return p
 def save(self,path,root):E.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
 def curves(self,d):
  values=np.array([float(v) for v in re.findall(r'[-+]?(?:\d*\.\d+|\d+)',d)])
  result=[];start=values[:2]
  for n in values[2:].reshape(-1,3,2):
   c=np.vstack([start,n]);result.append(c);start=c[-1]
  return result
 def contour(self):
  return [[30,30],[75,30],[75,55],[95,55],[95,30],[140,30],[140,100],[30,100]]
 def fixture(self):
  root=E.Element('{'+SVG_NS+'}svg',{'width':'240','height':'160','viewBox':'0 0 240 160','data-huitu-grouping':'semantic-v1','data-huitu-build':'vector-redraw-v1'})
  defs=E.SubElement(root,'defs');gradient=E.SubElement(defs,'linearGradient',id='paint')
  E.SubElement(gradient,'stop',offset='0',**{'stop-color':'#65ceca'});E.SubElement(gradient,'stop',offset='1',**{'stop-color':'#eeeefa'})
  bg=E.SubElement(root,'g',group_attributes('background','Background','background'))
  E.SubElement(bg,'rect',id='bg',width='240',height='160',fill='#fff')
  cell=E.SubElement(root,'g',group_attributes('cell','Cell with notch','cell'))
  E.SubElement(cell,'path',id='cell-body',d='M30 30H75V55H95V30H140V100H30Z',fill='url(#paint)')
  E.SubElement(cell,'circle',id='cell-nucleus',cx='70',cy='80',r='7',fill='#e78')
  other=E.SubElement(root,'g',group_attributes('neighbor','Protein','protein'))
  E.SubElement(other,'ellipse',id='protein-body',cx='185',cy='95',rx='15',ry='10',fill='url(#paint)')
  E.SubElement(other,'text',id='protein-label',x='185',y='99',**{'font-family':'Arial','font-size':'10','text-anchor':'middle'}).text='MIF'
  arrow=E.SubElement(root,'g',group_attributes('arrow','Activation','connector'))
  route={'points':[[15,125],[50,135],[100,115],[150,125]],'stroke':'#20b85b','stroke_width':3,'termination':'arrow','head':12,'dashed':False}
  for n in E.fromstring('<g xmlns="'+SVG_NS+'">'+''.join(curved_arrow_parts(route,'arrow'))+'</g>'):arrow.append(n)
  entries=[]
  for owner in (bg,cell,other,arrow):
   parts=[{'id':n.get('id'),'role':'text' if local_name(n.tag)=='text' else 'head' if local_name(n.tag)=='polygon' else 'shaft' if owner is arrow else 'shape'} for n in owner]
   spec={'id':owner.get('id'),'construction':'authored','reference_features':['Synthetic reference'],'parts':parts}
   if owner is arrow:spec['connector']=route
   if owner is cell:spec.update(required_features=['body','nucleus'],features=[{'key':'body','part_ids':['cell-body'],'expected_parts':{'min':1,'max':1},'source_bbox_px':[30,30,110,70],'max_bbox_error_px':1,'landmarks':[{'point':[75,55],'name':'notch','max_error_px':1}]},{'key':'nucleus','part_ids':['cell-nucleus'],'expected_parts':{'min':1,'max':1},'source_bbox_px':[63,73,14,14],'max_bbox_error_px':1}])
   if owner is other:spec.update(required_features=['body'],features=[{'key':'body','part_ids':['protein-body'],'source_bbox_px':[170,85,30,20],'max_bbox_error_px':1}])
   entries.append(spec)
  plan={'schema':'vector-redraw-v1','canvas':[240,160],'feature_contract':'source-features-v1','objects':entries}
  svg=self.path/'master.svg';self.save(svg,root);plan_path=self.write('plan.json',plan)
  return svg,plan_path,root,plan
 def request(self,svg,plan,operations):return self.write('patch.json',{'schema':'scene-patch-v1','base_svg_sha256':digest(svg),'base_plan_sha256':digest(plan),'operations':operations})
 def patch_run(self,svg,plan,request):return patch(svg,plan,request,self.path/'revised.svg',self.path/'revised.json')
 def test_pinned_corners_keep_exact_notch_and_bounds(self):
  pts=self.contour();d,r=landmark_path(pts,[{'index':i,'kind':'corner'} for i in range(len(pts))],spacing=25)
  curves=self.curves(d);endpoints=np.vstack([curves[0][0]]+[c[-1] for c in curves])
  for point in pts:self.assertTrue(np.any(np.linalg.norm(endpoints-point,axis=1)<1e-6))
  self.assertEqual(r['anchor_shift_px'],0);self.assertEqual(r['segments'],8)
  # Segments between corners stay on their measured straight boundaries.
  samples=np.vstack([bezier(c,np.linspace(0,1,20)) for c in curves]);self.assertGreaterEqual(samples[:,0].min(),30-1e-9);self.assertLessEqual(samples[:,0].max(),140+1e-9)
 def test_smooth_anchor_has_matching_join_tangents(self):
  theta=np.linspace(0,2*np.pi,64,endpoint=False);p=np.column_stack([50+20*np.cos(theta),50+12*np.sin(theta)])
  d,_=landmark_path(p,[{'index':i,'kind':'smooth'} for i in (0,16,32,48)])
  curves=self.curves(d)
  for i in (0,16,32,48):
   anchor=p[i];left=next(c for c in curves if np.linalg.norm(c[-1]-anchor)<.001);right=next(c for c in curves if np.linalg.norm(c[0]-anchor)<.001)
   a=left[-1]-left[-2];b=right[1]-right[0]
   self.assertGreater(np.dot(a,b)/np.linalg.norm(a)/np.linalg.norm(b),.9999)
 def test_open_contour_pins_endpoints_without_closure(self):
  d,r=landmark_path([[0,0],[5,8],[10,0]],[],closed=False,spacing=100)
  curves=self.curves(d);np.testing.assert_allclose(curves[0][0],[0,0]);np.testing.assert_allclose(curves[-1][-1],[10,0]);self.assertFalse(d.endswith('Z'));self.assertEqual(len(r['fixed_landmarks']),2)
 def test_coarse_sampling_does_not_discard_measured_bend(self):
  p=[[0,0],[5,10],[10,0]];d,_=landmark_path(p,[],closed=False,spacing=100,tolerance=.01)
  sample=np.vstack([bezier(c,np.linspace(0,1,100)) for c in self.curves(d)])
  self.assertGreater(sample[:,1].max(),9.9)
 def test_invalid_landmarks_and_sampling_fail_clearly(self):
  for marks in ([{'index':0},{'index':0}],[{'index':99},{'index':1}],['bad'],[],None):
   with self.assertRaises(ValueError):landmark_path(self.contour(),marks)
  for spacing in (0,float('nan'),1e-12):
   with self.assertRaises(ValueError):landmark_path(self.contour(),[{'index':0},{'index':4}],spacing=spacing)
 def test_contour_cli_output_records_manual_review(self):
  source=self.write('landmarks.json',{'schema':'landmark-contour-v1','object_id':'cell','points':self.contour(),'landmarks':[{'index':i,'kind':'corner'} for i in range(8)]})
  r=refine(source,self.path/'contour.json');self.assertEqual(r['construction'],'curve-refit');self.assertTrue(r['review_required']);self.assertEqual(len(r['fixed_landmarks']),8)
 def test_closed_legacy_fit_handles_coarse_spacing(self):
  d,n=closed_path([[0,0],[20,0],[20,20],[0,20]],spacing=100)
  self.assertTrue(d.endswith(' Z'));self.assertGreaterEqual(n,4)
 def test_serialized_anchor_rounding_is_reported_honestly(self):
  p=np.array(self.contour(),float)+.000037
  _,r=landmark_path(p,[{'index':i,'kind':'corner'} for i in range(8)])
  self.assertAlmostEqual(r['anchor_shift_px'],np.sqrt(2)*.000037,places=10)
 def test_complete_source_features_pass_with_shared_paint(self):
  _,_,root,plan=self.fixture();r=feature_audit(root,plan);self.assertEqual(r['status'],'PASS',r['errors']);self.assertEqual(len(r['features']),3)
 def test_missing_nucleus_feature_fails_even_with_group_intact(self):
  _,_,root,plan=self.fixture();plan['objects'][1]['features'].pop()
  r=feature_audit(root,plan);self.assertEqual(r['status'],'FAIL');self.assertTrue(any('required anatomical' in e for e in r['errors']))
 def test_foreign_owner_part_cannot_complete_feature(self):
  _,_,root,plan=self.fixture();plan['objects'][1]['features'][1]['part_ids']=['protein-body']
  self.assertTrue(any('foreign-owner' in e for e in feature_audit(root,plan)['errors']))
 def test_unassigned_internal_decoration_fails(self):
  _,_,root,plan=self.fixture();E.SubElement(owners(root)['cell'],'circle',id='bleb',cx='90',cy='80',r='2',fill='#e78')
  self.assertTrue(any('without feature assignment' in e for e in feature_audit(root,plan)['errors']))
 def test_fragment_count_cannot_pass_by_omitting_required_parts(self):
  _,_,root,plan=self.fixture();f=plan['objects'][1]['features'][1];f['expected_parts']={'min':2,'max':3}
  self.assertTrue(any('part-count min' in e for e in feature_audit(root,plan)['errors']))
 def test_same_part_cannot_stand_in_for_two_primary_features(self):
  _,_,root,plan=self.fixture();plan['objects'][1]['features'][1]['part_ids']=['cell-body']
  self.assertTrue(any('multiple primary features' in e for e in feature_audit(root,plan)['errors']))
 def test_generic_silhouette_misses_source_notch(self):
  _,_,root,plan=self.fixture();body=owners(root)['cell'][0];body.set('d','M30 30H140V100H30Z')
  r=feature_audit(root,plan);self.assertTrue(any('source landmark missed' in e for e in r['errors']));self.assertEqual(r['features'][0]['bbox_error_px'],0)
 def test_parent_transform_is_included_in_measured_bounds(self):
  _,_,root,plan=self.fixture();owners(root)['cell'].set('transform','translate(10 0)')
  self.assertTrue(any('bounds differ' in e for e in feature_audit(root,plan)['errors']))
 def test_malformed_landmark_is_a_reported_failure(self):
  _,_,root,plan=self.fixture();plan['objects'][1]['features'][0]['landmarks']=['bad']
  self.assertEqual(feature_audit(root,plan)['status'],'FAIL')
 def test_feature_failure_propagates_into_drawing_gate(self):
  svg,plan_path,_,plan=self.fixture();plan['objects'][1]['features'].pop();self.write(plan_path.name,plan)
  r=redraw_audit(svg,plan_path);self.assertEqual(r['status'],'FAIL');self.assertEqual(r['feature_audit']['status'],'FAIL')
 def test_planned_gradient_arrow_renders_its_paint_definitions(self):
  svg,plan_path,root,plan=self.fixture();arrow=owners(root)['arrow'];route=plan['objects'][-1]['connector'];route['stroke']='url(#paint)';arrow.clear();arrow.attrib.update(group_attributes('arrow','Activation','connector'))
  for n in E.fromstring('<g xmlns="'+SVG_NS+'">'+''.join(curved_arrow_parts(route,'arrow'))+'</g>'):arrow.append(n)
  self.save(svg,root);self.write(plan_path.name,plan);r=redraw_audit(svg,plan_path);self.assertEqual(r['status'],'PASS',r['errors'])
 def test_extract_retains_whole_protein_text_and_native_paint(self):
  svg,plan,_,_=self.fixture();r=extract(svg,plan,'neighbor',self.path/'component.svg',self.path/'component.json')
  root=E.parse(self.path/'component.svg').getroot();validate(root);self.assertEqual(set(owners(root)),{'neighbor'});self.assertEqual(len(owners(root)['neighbor']),2);self.assertTrue(any(local_name(n.tag)=='linearGradient' for n in root.iter()));self.assertTrue(r['review_required'])
 def test_translation_preserves_siblings_and_source_measurements(self):
  svg,plan,root,data=self.fixture();old_svg=digest(svg);old_plan=digest(plan);request=self.request(svg,plan,[{'op':'translate','object_id':'cell','dx':3,'dy':4}])
  r=self.patch_run(svg,plan,request);result=E.parse(self.path/'revised.svg').getroot();revised=json.loads((self.path/'revised.json').read_text())
  self.assertEqual(encoded(owners(result)['neighbor']),encoded(owners(E.parse(svg).getroot())['neighbor']));self.assertEqual(revised['objects'][1]['features'],data['objects'][1]['features']);self.assertEqual(digest(svg),old_svg);self.assertEqual(digest(plan),old_plan);self.assertTrue(r['prior_review_invalidated'])
 def test_translate_connector_updates_declared_route(self):
  svg,plan,_,data=self.fixture();request=self.request(svg,plan,[{'op':'translate','object_id':'arrow','dx':4,'dy':2}]);self.patch_run(svg,plan,request)
  revised=json.loads((self.path/'revised.json').read_text());self.assertEqual(revised['objects'][-1]['connector']['points'][0],[19,127]);r=redraw_audit(self.path/'revised.svg',self.path/'revised.json');self.assertEqual(r['status'],'PASS',r['errors'])
 def replacement(self,svg,plan):
  extract(svg,plan,'cell',self.path/'replacement.svg',self.path/'replacement.json');r=E.parse(self.path/'replacement.svg').getroot();next(n for n in r.iter() if local_name(n.tag)=='stop').set('stop-color','#ee9988');self.save(self.path/'replacement.svg',r)
  return {'op':'replace','object_id':'cell','source_svg':'replacement.svg','source_plan':'replacement.json'}
 def test_replacement_paint_collision_does_not_recolor_neighbor(self):
  svg,plan,root,_=self.fixture();op=self.replacement(svg,plan);request=self.request(svg,plan,[op]);r=self.patch_run(svg,plan,request)
  revised=E.parse(self.path/'revised.svg').getroot();self.assertEqual(encoded(owners(E.parse(svg).getroot())['neighbor']),encoded(owners(revised)['neighbor']));self.assertEqual(owners(revised)['neighbor'][0].get('fill'),'url(#paint)');self.assertTrue(owners(revised)['cell'][0].get('fill').startswith('url(#patch-paint-'));self.assertEqual(next(n for n in revised.iter() if n.get('id')=='paint')[0].get('stop-color'),'#65ceca');self.assertTrue(r['siblings_identical']);validate(revised)
 def test_stale_patch_rejected_before_writing(self):
  svg,plan,root,_=self.fixture();request=self.request(svg,plan,[{'op':'translate','object_id':'cell','dx':1,'dy':0}]);owners(root)['cell'][1].set('r','8');self.save(svg,root)
  with self.assertRaisesRegex(ValueError,'stale'):self.patch_run(svg,plan,request)
  self.assertFalse((self.path/'revised.svg').exists())
 def test_replacement_different_canvas_rejected(self):
  svg,plan,_,_=self.fixture();op=self.replacement(svg,plan);r=E.parse(self.path/'replacement.svg').getroot();r.set('viewBox','0 0 300 160');r.set('width','300');self.save(self.path/'replacement.svg',r);data=json.loads((self.path/'replacement.json').read_text());data['canvas']=[300,160];self.write('replacement.json',data);request=self.request(svg,plan,[op])
  with self.assertRaisesRegex(ValueError,'canvas'):self.patch_run(svg,plan,request)
 def test_duplicate_operation_rejected_without_partial_output(self):
  svg,plan,_,_=self.fixture();op={'op':'translate','object_id':'cell','dx':1,'dy':0};request=self.request(svg,plan,[op,op])
  with self.assertRaisesRegex(ValueError,'Unique'):self.patch_run(svg,plan,request)
  self.assertFalse((self.path/'revised.svg').exists())
 def test_patch_cannot_overwrite_original_master(self):
  svg,plan,_,_=self.fixture();request=self.request(svg,plan,[{'op':'translate','object_id':'cell','dx':1,'dy':0}])
  with self.assertRaisesRegex(ValueError,'new output'):patch(svg,plan,request,svg,self.path/'new-plan.json')
 def font_source(self,styles,scales=None):
  scales=scales or [1]*len(styles);source=self.path/'font.svg';entries=[];text=[]
  for i,(family,weight,style) in enumerate(styles):
   y=30+i*40;content='Nucleus' if i==0 else 'Mitochondrion'
   text.append(f'<text x="10" y="{y}" font-family="{family}" font-weight="{weight}" font-style="{style}" font-size="20" fill="#111" transform="translate(10 {y}) scale({scales[i]} 1) translate(-10 {-y})">{content}</text>')
   entries.append({'id':f't{i}','content':content,'source_font_size_px':20,'bbox_px':[5,y-24,210,30],'x':10,'y':y,'fill':'#111111','text_anchor':'start','font_family':'Arial','font_weight':weight,'font_style':style,'style_group':'labels','horizontal_scale':1})
  source.write_text('<svg xmlns="'+SVG_NS+'" width="240" height="110" viewBox="0 0 240 110"><rect width="240" height="110" fill="#fff"/>'+''.join(text)+'</svg>',encoding='utf-8')
  write_image(self.path/'source.png',render(source,240,110));write_image(self.path/'background.png',np.full((110,240,3),255,np.uint8));return self.write('text.json',{'source':{'width_px':240,'height_px':110},'text_elements':entries})
 def test_group_fitting_keeps_family_coherent_and_styles_live(self):
  m=self.font_source([('Arial','normal','normal'),('Arial','bold','italic')]);records=fit_labels(self.path/'source.png',self.path/'background.png',m,self.path/'fitted.json',self.path/'font-report.json',['Arial','Times New Roman'])
  data=json.loads((self.path/'fitted.json').read_text());self.assertEqual({r['font_family'] for r in records},{'Arial'});self.assertEqual(data['text_elements'][1]['font_weight'],'bold');self.assertEqual(data['text_elements'][1]['font_style'],'italic');self.assertEqual([r['id'] for r in records],['t0','t1']);self.assertLess(max(r['glyph_alpha_mse'] for r in records),.001);self.assertEqual(len(json.loads((self.path/'font-report.json').read_text())['typography_groups']),1)
 def test_distinct_declared_style_groups_can_use_distinct_families(self):
  m=self.font_source([('Arial','normal','normal'),('Times New Roman','normal','normal')]);data=json.loads(m.read_text());data['text_elements'][1]['style_group']='serif-labels';self.write(m.name,data)
  records=fit_labels(self.path/'source.png',self.path/'background.png',m,self.path/'fitted.json',families_to_try=['Arial','Times New Roman']);self.assertEqual([r['font_family'] for r in records],['Arial','Times New Roman'])
 def test_controlled_width_fit_reduces_real_glyph_error(self):
  m=self.font_source([('Arial','normal','normal')],[1.08]);before=fit_labels(self.path/'source.png',self.path/'background.png',m,self.path/'fixed-width.json',width_adjustment=0);after=fit_labels(self.path/'source.png',self.path/'background.png',m,self.path/'fitted.json',width_adjustment=.08)
  self.assertLess(after[0]['glyph_alpha_mse'],before[0]['glyph_alpha_mse']*.4);self.assertAlmostEqual(after[0]['horizontal_scale'],1.08,places=3)
 def test_empty_style_group_rejected_by_manifest(self):
  m=self.font_source([('Arial','normal','normal')]);data=json.loads(m.read_text());data['text_elements'][0]['style_group']=' ';self.write(m.name,data);self.assertEqual(lint(m)['status'],'FAIL')
 def test_excessive_width_fit_rejected(self):
  m=self.font_source([('Arial','normal','normal')])
  with self.assertRaisesRegex(ValueError,'Width adjustment'):fit_labels(self.path/'source.png',self.path/'background.png',m,self.path/'fitted.json',width_adjustment=.5)
 def test_native_gradient_stroke_inspector_without_illustrator(self):
  node=os.environ.get('HUITU_NODE') or shutil.which('node')
  if not node:self.skipTest('Node.js is needed only for mock JSX tests')
  result=subprocess.run([str(node),str(Path(__file__).with_name('gradient_stroke_test.js')),str(SCRIPTS/'verify_symbol_editability.ps1')],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr);self.assertIn('PASS',result.stdout)

if __name__=='__main__':
 report_path=Path(sys.argv[sys.argv.index('--report')+1]) if '--report' in sys.argv else None
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DetailTests))
 if report_path:report_path.write_text(json.dumps({'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'user_images_processed':False,'illustrator_contacted':False,'api_requests':0},indent=2),encoding='utf-8')
 raise SystemExit(0 if result.wasSuccessful() else 1)
