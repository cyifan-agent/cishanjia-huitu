"""Exact-output cache and unchanged-check regressions on synthetic vectors."""
import copy,importlib.util,json,sys,tempfile,time,unittest,subprocess,xml.etree.ElementTree as E
from pathlib import Path
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1];sys.dont_write_bytecode=True;sys.path.insert(0,str(SCRIPTS))
from runtime_env import bootstrap
bootstrap()
import numpy as np
from render_cache import RenderCache,render_png
from render_compare import render
from redraw_audit import audit
from quality_gate import build,CHECKS
from preview_fonts import font_files_for_svg,resolve_font_file

def load_fixture():
 spec=importlib.util.spec_from_file_location('speed_detail_fixture',Path(__file__).with_name('test_detail_refinement.py'))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module.DetailTests

class SpeedTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory(prefix='huitu-speed-');self.path=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def svg(self,color='#f80',extra=''):
  return '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80"><ellipse id="body" cx="60" cy="40" rx="35" ry="20" fill="'+color+'"/>'+extra+'</svg>'
 def fixture(self):
  item=load_fixture()();item.path=self.path;return item.fixture()
 def json(self,name,value):p=self.path/name;p.write_text(json.dumps(value),encoding='utf-8');return p
 def test_cached_png_bytes_are_identical_to_uncached_renderer(self):
  cache=RenderCache(self.path/'cache');a=render_png(self.svg());b=render_png(self.svg(),cache=cache);c=render_png(self.svg(),cache=cache)
  self.assertEqual(a,b);self.assertEqual(a,c);self.assertEqual(cache.stats['renderer_calls'],1);self.assertEqual(cache.stats['memory_hits'],1)
 def test_cache_is_reused_by_new_process_session_object(self):
  folder=self.path/'cache';a=RenderCache(folder).render(self.svg());second=RenderCache(folder);self.assertEqual(second.render(self.svg()),a);self.assertEqual(second.stats['disk_hits'],1);self.assertEqual(second.stats['renderer_calls'],0)
 def test_geometry_change_causes_re_render(self):
  cache=RenderCache(self.path/'cache');a=cache.render(self.svg());b=cache.render(self.svg().replace('rx="35"','rx="28"'))
  self.assertNotEqual(a,b);self.assertEqual(cache.stats['renderer_calls'],2)
 def test_gradient_stop_change_causes_re_render(self):
  svg='<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><defs><radialGradient id="g"><stop offset="0" stop-color="#f80"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs><ellipse id="glow" cx="60" cy="40" rx="35" ry="20" fill="url(#g)"/></svg>'
  cache=RenderCache();a=cache.render(svg);b=cache.render(svg.replace('#f80','#08f'));self.assertNotEqual(a,b);self.assertEqual(cache.stats['renderer_calls'],2)
 def test_dimensions_are_part_of_cache_identity(self):
  cache=RenderCache();cache.render(self.svg(),width=120,height=80);cache.render(self.svg(),width=240,height=160);self.assertEqual(cache.stats['renderer_calls'],2)
 def test_font_content_change_invalidates_even_at_same_path(self):
  svg=self.svg(extra='<text id="label" x="25" y="45" font-family="Arial" font-size="16">Nucleus</text>');font=self.path/'selected.ttf'
  font.write_bytes(Path(resolve_font_file('Arial')).read_bytes());cache=RenderCache(self.path/'cache');cache.render(svg,font_files=[str(font)])
  font.write_bytes(Path(resolve_font_file('Times New Roman')).read_bytes());cache.render(svg,font_files=[str(font)]);self.assertEqual(cache.stats['renderer_calls'],2)
 def test_equivalent_font_bytes_at_new_temp_path_reuse_cache(self):
  svg=self.svg(extra='<text id="label" x="25" y="45" font-family="Arial" font-size="16">Nucleus</text>');a=self.path/'a.ttf';b=self.path/'b.ttf';a.write_bytes(Path(resolve_font_file('Arial')).read_bytes());b.write_bytes(a.read_bytes())
  cache=RenderCache();self.assertEqual(cache.render(svg,font_files=[str(a)]),cache.render(svg,font_files=[str(b)]));self.assertEqual(cache.stats['renderer_calls'],1)
 def test_renderer_identity_change_invalidates_disk_entry(self):
  folder=self.path/'cache';RenderCache(folder).render(self.svg())
  with patch('render_cache.engine_identity',return_value='synthetic-new-engine'):
   changed=RenderCache(folder);changed.render(self.svg());self.assertEqual(changed.stats['renderer_calls'],1);self.assertEqual(changed.stats['disk_hits'],0)
 def test_corrupt_png_is_recomputed_without_using_stale_preview(self):
  folder=self.path/'cache';a=RenderCache(folder).render(self.svg());next(folder.glob('*.png')).write_bytes(b'broken')
  cache=RenderCache(folder);self.assertEqual(cache.render(self.svg()),a);self.assertEqual(cache.stats['renderer_calls'],1);self.assertEqual(cache.stats['cache_errors'],1)
 def test_non_object_cache_metadata_recovers(self):
  folder=self.path/'cache';a=RenderCache(folder).render(self.svg());next(folder.glob('*.json')).write_text('[]',encoding='utf-8');cache=RenderCache(folder);self.assertEqual(cache.render(self.svg()),a);self.assertEqual(cache.stats['renderer_calls'],1)
 def test_cache_write_error_falls_back_to_exact_render(self):
  blocked=self.path/'not-directory';blocked.write_text('x');cache=RenderCache(blocked);self.assertEqual(cache.render(self.svg()),render_png(self.svg()));self.assertGreater(cache.stats['cache_errors'],0)
 def test_memory_budget_evicts_without_changing_output(self):
  cache=RenderCache(max_memory_bytes=1);cache.render(self.svg());cache.render(self.svg());self.assertEqual(cache.stats['renderer_calls'],2);self.assertLessEqual(cache.memory_bytes,1)
 def test_comparison_pixels_with_live_fonts_unchanged(self):
  svg=self.path/'text.svg';svg.write_text(self.svg(extra='<text id="label" x="15" y="45" font-family="Arial Narrow" font-weight="bold" font-size="16">Nucleus</text>'),encoding='utf-8');cache=RenderCache(self.path/'cache')
  np.testing.assert_array_equal(render(svg,120,80),render(svg,120,80,cache));np.testing.assert_array_equal(render(svg,120,80),render(svg,120,80,cache));self.assertEqual(cache.stats['renderer_calls'],1)
 def test_normalized_narrow_font_bytes_remain_stable_across_time(self):
  svg=self.path/'narrow.svg';svg.write_text(self.svg(extra='<text id="label" x="15" y="45" font-family="Arial Narrow" font-size="16">DNA</text>'),encoding='utf-8')
  with patch('fontTools.ttLib.tables._h_e_a_d.timestampNow',return_value=1111111111):first=font_files_for_svg(svg,self.path/'fonts-a')
  with patch('fontTools.ttLib.tables._h_e_a_d.timestampNow',return_value=2222222222):second=font_files_for_svg(svg,self.path/'fonts-b')
  self.assertEqual([Path(p).read_bytes() for p in first],[Path(p).read_bytes() for p in second])
 def test_all_features_and_connectors_rechecked_with_same_results(self):
  svg,plan,_,_=self.fixture();uncached=audit(svg,plan);cache=RenderCache(self.path/'cache');first=audit(svg,plan,cache=cache);calls=cache.stats['renderer_calls'];again=audit(svg,plan,cache=cache)
  self.assertEqual(uncached,first);self.assertEqual(uncached,again);self.assertEqual(cache.stats['renderer_calls'],calls);self.assertEqual(len(again['feature_audit']['features']),3);self.assertEqual(len(again['connectors']),1)
 def test_plan_threshold_change_still_fails_with_cached_geometry(self):
  svg,plan,_,data=self.fixture();cache=RenderCache(self.path/'cache');self.assertEqual(audit(svg,plan,cache=cache)['status'],'PASS');calls=cache.stats['renderer_calls']
  data['objects'][1]['features'][0]['source_bbox_px']=[20,30,110,70];self.json(plan.name,data);report=audit(svg,plan,cache=cache)
  self.assertEqual(report['status'],'FAIL');self.assertTrue(any('bounds differ' in e for e in report['errors']));self.assertEqual(cache.stats['renderer_calls'],calls)
 def test_one_changed_owner_reuses_only_unchanged_feature_previews(self):
  svg,plan,root,_=self.fixture();cache=RenderCache(self.path/'cache');audit(svg,plan,cache=cache);before=dict(cache.stats)
  next(n for n in root.iter() if n.get('id')=='cell-nucleus').set('r','12');E.ElementTree(root).write(svg,encoding='utf-8');r=audit(svg,plan,cache=cache)
  self.assertEqual(r['status'],'FAIL');self.assertEqual(cache.stats['renderer_calls']-before['renderer_calls'],1);self.assertEqual(cache.stats['memory_hits']-before['memory_hits'],4)
 def test_final_gate_requires_fresh_visual_review_even_when_renders_hit(self):
  import hashlib
  svg,plan,root,_=self.fixture();cache=RenderCache(self.path/'cache');audit(svg,plan,cache=cache);digest=hashlib.sha256(svg.read_bytes()).hexdigest()
  metrics=self.json('metrics.json',{'svg_sha256':digest,'threshold_failures':[],'regions':[]});review=self.json('review.json',{'svg_sha256':digest,'checks':{k:{'status':'pass','evidence':'Synthetic inspected sample'} for k in CHECKS},'unresolved_issues':[]})
  self.assertEqual(build(svg,metrics,review,drawing_plan=plan,cache=cache)['status'],'PASS')
  root.set('data-revision','2');E.ElementTree(root).write(svg,encoding='utf-8');r=build(svg,metrics,review,drawing_plan=plan,cache=cache);self.assertEqual(r['status'],'FAIL');self.assertTrue(any('different SVG' in e for e in r['errors']))
 def test_cached_isolated_arrow_preview_is_exact(self):
  svg,plan,_,_=self.fixture();cache=RenderCache(self.path/'cache');a=audit(svg,plan,self.path/'plain');b=audit(svg,plan,self.path/'cached',cache)
  self.assertEqual((self.path/'plain/arrow-isolated.png').read_bytes(),(self.path/'cached/arrow-isolated.png').read_bytes());self.assertEqual(a['status'],b['status']);self.assertGreater(cache.stats['memory_hits'],0)
 def test_faster_visible_playback_changes_only_pause_in_dry_run(self):
  import hashlib
  svg,plan,_,_=self.fixture();qa=self.json('qa.json',{'status':'PASS','svg_sha256':hashlib.sha256(svg.read_bytes()).hexdigest(),'construction':'vector-redraw-v1','connector_geometry_passed':True})
  configs=[]
  for name,pause in [('fast',None),('slow','1200')]:
   work=self.path/name;args=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(SCRIPTS/'native_svg_import.ps1'),'-InputSvg',str(svg),'-QaReport',str(qa),'-WorkDir',str(work),'-OutputAi',str(self.path/'result.ai'),'-OutputPng',str(self.path/'result.png'),'-LiveDraw','-DryRun']
   if pause:args+=['-DelayMs',pause]
   r=subprocess.run(args,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertIn('No Illustrator connection',r.stdout)
   configs.append(json.loads((work/'native-dry-run.json').read_text(encoding='utf-8-sig')))
  self.assertEqual(configs[0]['delayMs'],250);self.assertEqual(configs[1]['delayMs'],1200)
  self.assertEqual(configs[0]['objectMode'],'symbol');self.assertTrue(configs[0]['liveDraw'])
  for config in configs:config.pop('delayMs');config.pop('report')
  self.assertEqual(configs[0],configs[1]);self.assertFalse((self.path/'result.ai').exists())

def benchmark():
 item=load_fixture()();item.path=benchmark_dir
 svg,plan,_,_=item.fixture();cache=RenderCache(benchmark_dir/'cache')
 start=time.perf_counter();first=audit(svg,plan,cache=cache);first_seconds=time.perf_counter()-start;first_calls=cache.stats['renderer_calls']
 start=time.perf_counter();second=audit(svg,plan,cache=cache);second_seconds=time.perf_counter()-start
 return {'scope':'Synthetic repeated feature/connector audit; excludes drawing, human review and Illustrator','identical_reports':first==second,'first_seconds':round(first_seconds,6),'repeat_seconds':round(second_seconds,6),'first_renderer_calls':first_calls,'repeat_renderer_calls':cache.stats['renderer_calls']-first_calls,'quality_checks_retained':True,'illustrator_contacted':False,'api_requests':0}

if __name__=='__main__':
 report_path=Path(sys.argv[sys.argv.index('--report')+1]) if '--report' in sys.argv else None
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SpeedTests))
 report={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'user_images_processed':False,'illustrator_contacted':False,'api_requests':0}
 if report_path:
  with tempfile.TemporaryDirectory(prefix='huitu-benchmark-') as t:
   benchmark_dir=Path(t);report['benchmark']=benchmark()
  report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
 raise SystemExit(0 if result.wasSuccessful() else 1)
