"""Behavioral regression tests; no user image or live Illustrator document."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))
from runtime_env import bootstrap
bootstrap()
import numpy as np
import cv2
import local_reconstruct as trace
import render_compare as compare
import compose_scene as scene
import hybrid_merge as merge
import manifest_lint as manifest
import quality_gate as gate
import color_mesh,preview_fonts,fit_text,svg_text_geometry,prepare_native_svg,verify_native_export,object_groups
from svg_contract import validate


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="huitu-tests-")
        self.path = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def json_file(self, name, data):
        path = self.path / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path
    def svg_file(self, name="base.svg", content=None):
        path = self.path / name
        path.write_text(content or '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" viewBox="0 0 100 80"><rect id="base" x="0" y="0" width="100" height="80" fill="#fff"/></svg>', encoding="utf-8")
        return path
    def entry(self, **change):
        entry = {"id":"label", "content":"PAR", "source_font_size_px":24, "bbox_px":[20,10,90,40],
                 "x":65,"y":38,"coordinate_space":"pixel","fill":"#111111","text_anchor":"middle"}
        entry.update(change)
        return entry
    def semantic_svg(self):
        return self.svg_file(content='<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" viewBox="0 0 100 80" data-huitu-grouping="semantic-v1" data-huitu-build="vector-redraw-v1"><g id="background" data-huitu-object-id="background" data-huitu-name="Background" data-huitu-kind="background"><rect id="bg" width="100" height="80" fill="#fff"/></g><g id="dna-1" data-huitu-object-id="dna-1" data-huitu-name="DNA 01" data-huitu-kind="dna"><rect id="strand-1" x="10" y="10" width="5" height="20" fill="#c00"/><rect id="strand-2" x="20" y="10" width="5" height="20" fill="#c00"/><text id="dna-label" x="10" y="45" font-size="12" font-family="Arial">DNA</text></g></svg>')
    def lint(self, entries, height=120):
        return manifest.lint(self.json_file("manifest.json", {"source":{"width_px":160,"height_px":height},"text_elements":entries}))

    def test_valid_manifest(self):
        self.assertEqual(self.lint([self.entry()])["status"],"PASS")
    def test_horizontal_scale_requires_finite_positive_value(self):
        for value in (0,float('nan'),20):
            self.assertEqual(self.lint([self.entry(horizontal_scale=value)])["status"],"FAIL")
    def test_anisotropic_text_cache_preserves_height_and_width(self):
        parser=svg_text_geometry.load_parser()
        atom=parser.parse_atom(ET.fromstring('<text x="10" y="30">PAR</text>'),parser.Transform(.6,0,0,1,0,0),{'font-size':'20'},1,0)
        self.assertEqual(atom['text']['fontSize'],20)
        self.assertEqual(atom['text']['horizontalScale'],60)
        self.assertEqual(atom['text']['position'],[6,30])
    def test_text_skew_and_reflection_rejected(self):
        parser=svg_text_geometry.load_parser()
        for transform in (parser.Transform(1,.2,0,1,0,0),parser.Transform(-1,0,0,1,0,0)):
            with self.assertRaises(ValueError):parser.parse_atom(ET.fromstring('<text>PAR</text>'),transform,{'font-size':'20'},1,0)
    def test_native_prepare_separates_text_and_preserves_parent_transform(self):
        svg=self.svg_file(content='<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" viewBox="0 0 100 80"><g transform="translate(3 4)"><rect id="rect" width="100" height="80" fill="#fff"/><text id="label" x="10" y="30" font-size="20" transform="scale(.6 1)">PAR</text></g></svg>')
        count=prepare_native_svg.prepare(svg,self.path/'graphics.svg',self.path/'labels.json')
        self.assertEqual(count,1)
        labels=json.loads((self.path/'labels.json').read_text())['labels']
        self.assertEqual(labels[0]['x'],9)
        self.assertEqual(labels[0]['y'],34)
        self.assertEqual(labels[0]['size'],20)
        self.assertEqual(labels[0]['horizontalScale'],60)
        graphics=ET.parse(self.path/'graphics.svg').getroot()
        self.assertFalse(any(n.tag.endswith('text') for n in graphics.iter()))
        self.assertTrue(any(n.get('id')=='rect' for n in graphics.iter()))
    def test_color_mesh_gradient_and_exact_region(self):
        image=np.empty((24,32,3),np.uint8)
        image[:]=np.arange(32,dtype=np.uint8)[None,:,None]*4+100
        trace.write_image(self.path/'source.png',image)
        m=self.json_file('labels.json',{'source':{'width_px':32,'height_px':24},'text_elements':[]})
        regions=self.json_file('regions.json',[{'id':'detail','bbox_px':[8,4,8,8],'group_as_object':True,'exact_color':True}])
        report=color_mesh.mesh(self.path/'source.png',m,self.path/'mesh.svg',regions,6)
        validate(ET.parse(self.path/'mesh.svg').getroot())
        rendered=compare.render(self.path/'mesh.svg',32,24)
        self.assertLess(np.abs(rendered.astype(float)-image).mean(),2)
        np.testing.assert_array_equal(rendered[4:12,8:16],image[4:12,8:16])
        self.assertEqual(report['raster_nodes'],0)
        self.assertEqual(report['groups'],2)
    def test_color_mesh_rejects_canvas_and_region_errors(self):
        trace.write_image(self.path/'source.png',np.ones((24,32,3),np.uint8)*255)
        m=self.json_file('labels.json',{'source':{'width_px':33,'height_px':24},'text_elements':[]})
        with self.assertRaisesRegex(ValueError,'canvas'):color_mesh.mesh(self.path/'source.png',m,self.path/'out.svg')
        m=self.json_file('labels.json',{'source':{'width_px':32,'height_px':24},'text_elements':[]})
        regions=self.json_file('regions.json',[{'id':'bad','bbox_px':[-1,4,8,8]}])
        with self.assertRaisesRegex(ValueError,'outside'):color_mesh.mesh(self.path/'source.png',m,self.path/'out.svg',regions)
    def test_preview_font_absence_fails_instead_of_fallback(self):
        path=self.svg_file(content='<svg xmlns="http://www.w3.org/2000/svg"><text font-family="Huitu-Absent-Font">PAR</text></svg>')
        with self.assertRaisesRegex(ValueError,'FONT_PREVIEW_STYLE_MISSING'):preview_fonts.font_files_for_svg(path,self.path/'fonts')
    def test_preview_narrow_family_alias_is_normalized(self):
        from fontTools.ttLib import TTFont
        path=self.svg_file(content='<svg xmlns="http://www.w3.org/2000/svg"><text font-family="Arial Narrow" font-weight="bold">PAR</text></svg>')
        files=preview_fonts.font_files_for_svg(path,self.path/'fonts')
        names=[]
        for file in files:
            with TTFont(file,lazy=True) as font:names.append(font['name'].getDebugName(16) or font['name'].getDebugName(1))
        self.assertTrue(names and all(name=='Arial Narrow' for name in names))
    def test_mixed_arial_families_do_not_steal_each_others_faces(self):
        from fontTools.ttLib import TTFont
        path=self.svg_file(content='<svg xmlns="http://www.w3.org/2000/svg" width="160" height="80" viewBox="0 0 160 80"><text x="5" y="25" font-family="Arial" font-weight="bold">PAR</text><text x="5" y="55" font-family="Arial Narrow" font-weight="bold">PAR</text></svg>')
        files=preview_fonts.font_files_for_svg(path,self.path/'fonts')
        families=set()
        for file in files:
            with TTFont(file,lazy=True) as font:families.add(font['name'].getDebugName(16) or font['name'].getDebugName(1))
        self.assertEqual(families,{'Arial','Arial Narrow'})
        self.assertNotEqual(preview_fonts.resolve_font_file('Arial','bold'),preview_fonts.resolve_font_file('Arial Narrow','bold'))
        for seed in ('1','7','14'):
            env=os.environ.copy();env['PYTHONHASHSEED']=seed
            code='import sys,tempfile;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from runtime_env import bootstrap;bootstrap();from render_compare import render;render(Path(sys.argv[2]),160,80)'
            result=subprocess.run([sys.executable,'-X','utf8','-c',code,str(SCRIPT_ROOT),str(path)],capture_output=True,text=True,env=env)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_known_label_fit_respects_regular_font(self):
        svg=self.svg_file(content='<svg xmlns="http://www.w3.org/2000/svg" width="160" height="80" viewBox="0 0 160 80"><rect width="160" height="80" fill="#fff"/><text x="25" y="43" font-family="Arial" font-size="24" fill="#111">PAR</text></svg>')
        trace.write_image(self.path/'source.png',compare.render(svg,160,80))
        trace.write_image(self.path/'cleaned.png',np.ones((80,160,3),np.uint8)*255)
        m=self.json_file('labels.json',{'source':{'width_px':160,'height_px':80},'text_elements':[self.entry(x=25,y=43,text_anchor='start',font_family='Arial',font_weight='normal')]})
        records=fit_text.fit(self.path/'source.png',self.path/'cleaned.png',m,self.path/'fitted.json')
        self.assertLess(records[0]['glyph_alpha_mse'],.001)
        self.assertEqual(json.loads((self.path/'fitted.json').read_text())['text_elements'][0]['font_weight'],'normal')
    def test_native_import_gate_and_dryrun_without_illustrator(self):
        svg=self.semantic_svg()
        sha=hashlib.sha256(svg.read_bytes()).hexdigest()
        qa=self.json_file('qa.json',{'status':'PASS','svg_sha256':sha,'construction':'vector-redraw-v1','connector_geometry_passed':True})
        args=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(SCRIPT_ROOT/'native_svg_import.ps1'),'-InputSvg',str(svg),'-QaReport',str(qa),'-WorkDir',str(self.path/'native'),'-OutputAi',str(self.path/'out.ai'),'-OutputPng',str(self.path/'out.png'),'-DryRun']
        result=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('No Illustrator connection',result.stdout)
        qa.write_text(json.dumps({'status':'PASS','svg_sha256':'stale'}))
        result=subprocess.run(args,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('HUITU_QA_INVALID',result.stderr)
    def test_native_prepare_retains_text_object_ownership(self):
        svg=self.semantic_svg()
        prepare_native_svg.prepare(svg,self.path/'graphics.svg',self.path/'labels.json')
        payload=json.loads((self.path/'labels.json').read_text())
        self.assertEqual(payload['grouping'],'semantic-v1')
        self.assertEqual(payload['labels'][0]['object_id'],'dna-1')
        self.assertEqual(payload['labels'][0]['source_id'],'dna-label')
        self.assertEqual(payload['objects'][1]['graphic_count'],2)
        root=ET.parse(self.path/'graphics.svg').getroot()
        self.assertEqual([x.get('id') for x in root[0]],['background','dna-1'])
    def test_semantic_audit_rejects_unowned_fragments(self):
        root=ET.parse(self.semantic_svg()).getroot()
        ET.SubElement(root,'{http://www.w3.org/2000/svg}path',{'id':'loose-dna-rung','d':'M10 15L20 15'})
        self.assertEqual(object_groups.audit(root)['status'],'FAIL')
    def test_object_assembly_contains_complete_parts_and_live_label(self):
        root=ET.parse(self.semantic_svg()).getroot()
        root.attrib.pop('data-huitu-grouping')
        for group in list(root):
            for node in list(group):root.append(node)
            root.remove(group)
        source=self.path/'flat.svg';ET.ElementTree(root).write(source,encoding='utf-8')
        manifest=self.json_file('objects.json',{'objects':[{'id':'background','name':'Background','kind':'background','member_ids':['bg']},
            {'id':'dna-1','name':'DNA 01','kind':'dna','member_ids':['strand-1','strand-2','dna-label']}]})
        output=self.path/'grouped.svg';report=object_groups.assemble(source,manifest,output)
        self.assertEqual(report['status'],'PASS')
        self.assertEqual(report['owners']['dna-label'],'dna-1')
        self.assertEqual(report['objects'][1]['graphic_count'],2)
        np.testing.assert_array_equal(compare.render(source,100,80),compare.render(output,100,80))
        data=json.loads(manifest.read_text());data['objects'][0]['member_ids'].append('strand-1');manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'more than one object'):object_groups.assemble(source,manifest,output)
    def semantic_mesh_inputs(self):
        backdrop=np.full((48,64,3),240,np.uint8);source=backdrop.copy()
        mask_a=np.zeros((48,64),np.uint8);mask_b=mask_a.copy()
        mask_a[8:16,8:16]=255;mask_a[8:16,20:24]=255;mask_b[26:34,40:48]=255
        source[(mask_a>0)|(mask_b>0)]=[0,0,240]
        for name,image in [('source.png',source),('background.png',backdrop),('a-mask.png',mask_a),('b-mask.png',mask_b)]:trace.write_image(self.path/name,image)
        objects=self.json_file('object-masks.json',{'objects':[{'id':'dna-1','name':'DNA 01','kind':'dna','mask_path':'a-mask.png'},
                    {'id':'protein-1','name':'Protein 01','kind':'protein','mask_path':'b-mask.png'}]})
        manifest=self.json_file('labels.json',{'source':{'width_px':64,'height_px':48},'text_elements':[{'id':'dna-label','content':'DNA','source_font_size_px':8,'bbox_px':[8,17,20,9],
                    'x':8,'y':24,'font_family':'Arial','fill':'#111111','text_anchor':'start','object_id':'dna-1'}]})
        return objects,manifest
    def test_mask_mesh_same_color_objects_remain_separate_when_moved(self):
        objects,manifest=self.semantic_mesh_inputs();output=self.path/'objects.svg'
        report=color_mesh.mesh(self.path/'source.png',manifest,output,tolerance=0,objects=objects,background=self.path/'background.png')
        self.assertTrue(report['semantic_object_groups'])
        root=ET.parse(output).getroot();check=object_groups.audit(root)
        self.assertEqual(check['status'],'PASS');self.assertEqual(len(check['objects']),3)
        before=compare.render(output,64,48)
        root[1].set('transform','translate(8 18)');moved=self.path/'moved.svg';ET.ElementTree(root).write(moved,encoding='utf-8')
        after=compare.render(moved,64,48)
        self.assertTrue(np.all(after[8:16,8:24]==240)) # no hole or baked-in original remains
        np.testing.assert_array_equal(after[26:34,40:48],before[26:34,40:48]) # other same-color object unchanged
        self.assertTrue(np.all(after[26:34,16:24]==[0,0,240]))
        prepare_native_svg.prepare(output,self.path/'graphics.svg',self.path/'native-text.json')
        payload=json.loads((self.path/'native-text.json').read_text())
        self.assertEqual(payload['labels'][0]['object_id'],'dna-1')
    def test_mask_mesh_rejects_missing_background_overlap_and_unowned_text(self):
        objects,manifest=self.semantic_mesh_inputs()
        with self.assertRaisesRegex(ValueError,'background'):color_mesh.mesh(self.path/'source.png',manifest,self.path/'out.svg',objects=objects)
        trace.write_image(self.path/'b-mask.png',compare.load_image(self.path/'a-mask.png'))
        with self.assertRaisesRegex(ValueError,'overlap'):color_mesh.mesh(self.path/'source.png',manifest,self.path/'out.svg',objects=objects,background=self.path/'background.png')
        self.semantic_mesh_inputs();data=json.loads(manifest.read_text());data['text_elements'][0]['object_id']='missing';manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'object_id'):color_mesh.mesh(self.path/'source.png',manifest,self.path/'out.svg',objects=objects,background=self.path/'background.png')
    def test_nan_and_null_rejected(self):
        self.assertEqual(self.lint([self.entry(content=None, source_font_size_px=float("nan"))])["status"],"FAIL")
    def test_malformed_box_rejected(self):
        self.assertEqual(self.lint([self.entry(bbox_px="bad")])["status"],"FAIL")
    def test_duplicate_id_rejected(self):
        self.assertEqual(self.lint([self.entry(), self.entry()])["status"],"FAIL")
    def test_normalized_font_size_accepted(self):
        entry=self.entry()
        del entry["source_font_size_px"]
        entry.update(font_size=.03,font_size_space="normalized")
        self.assertEqual(self.lint([entry],1000)["status"],"PASS")
        self.assertEqual(trace.font_size_px(entry,1000),30)
    def test_outside_box_rejected(self):
        self.assertEqual(self.lint([self.entry(bbox_px=[159,10,90,40])])["status"],"FAIL")
    def test_explicit_baseline_wins(self):
        root=ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg"/>')
        trace.add_ids_and_text(root,[self.entry(x=21,y=31)],160,120,"t")
        self.assertEqual(root[0].get("x"),"21.000")
        self.assertEqual(root[0].get("y"),"31.000")
    def test_end_anchor_uses_right_edge(self):
        root=ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg"/>')
        entry=self.entry(text_anchor="end",position_from_bbox=True)
        trace.add_ids_and_text(root,[entry],160,120,"t")
        self.assertEqual(root[0].get("x"),"110.000")
    def test_multiline_color_and_shared_rotation(self):
        root=ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg"/>')
        trace.add_ids_and_text(root,[self.entry(content="PAR\n(reduced)",rotation=25,
                                line_styles=[{},{"fill":"#c52d2a","font-weight":"bold"}])],160,120,"t")
        self.assertEqual(len(root),2)
        self.assertEqual(root[1].get("fill"),"#c52d2a")
        self.assertEqual(root[0].get("transform"),root[1].get("transform"))
        self.assertFalse(any("tspan" in node.tag for node in root.iter()))
    def test_glyph_mask_protects_same_color_graphics(self):
        image=np.full((120,160,3),235,np.uint8)
        cv2.putText(image,"PAR",(25,42),cv2.FONT_HERSHEY_SIMPLEX,0.65,(17,17,17),2)
        cv2.line(image,(100,0),(100,80),(17,17,17),3)
        entry=self.entry(bbox_px=[15,10,130,48],protect_regions=[[95,0,10,90]])
        mask=trace.glyph_mask_for_entry(image,entry,2)
        self.assertGreater(np.count_nonzero(mask),10)
        self.assertEqual(np.count_nonzero(mask[:,95:105]),0)
        cleaned,_=trace.clean_text_glyphs(image,[entry],2)
        np.testing.assert_array_equal(cleaned[:,95:105],image[:,95:105])
    def test_tight_mask_does_not_remove_red_ellipse(self):
        image=np.full((120,160,3),235,np.uint8)
        cv2.ellipse(image,(80,45),(70,30),0,0,360,(70,85,210),3)
        cv2.putText(image,"PAR",(40,50),cv2.FONT_HERSHEY_SIMPLEX,.65,(17,17,17),2)
        mask=trace.glyph_mask_for_entry(image,self.entry(bbox_px=[10,10,140,75]),2)
        red=(image[:,:,2]>180)&(image[:,:,1]<100)
        self.assertEqual(np.count_nonzero(mask[red]),0)
    def test_manual_mask_canvas_must_match(self):
        path=self.path/"mask.png"
        trace.write_image(path,np.ones((10,10),np.uint8)*255)
        with self.assertRaises(ValueError):
            trace.glyph_mask_for_entry(np.ones((120,160,3),np.uint8),self.entry(mask_mode="manual",mask_path=str(path)),2)
    def test_empty_images_have_perfect_edge_match(self):
        a=np.ones((20,20,3),np.uint8)*255
        self.assertEqual(compare.edge_f1(a,a),1)
    def test_native_export_dimension_mismatch_is_not_stretched(self):
        source=self.path/'source.png';actual=self.path/'native.png'
        trace.write_image(source,np.full((80,100,3),255,np.uint8))
        trace.write_image(actual,np.full((79,101,3),255,np.uint8))
        with self.assertRaisesRegex(ValueError,'canvas mismatch'):
            verify_native_export.compare_export(source,actual)
        report=verify_native_export.compare_export(source,actual,allow_white_rounding_border=True)
        self.assertEqual(report['status'],'PASS')
        self.assertEqual(report['canvas_adjustment']['right_px'],1)
        self.assertEqual(report['canvas_adjustment']['bottom_px'],-1)
        self.assertEqual(compare.load_image(actual).shape[:2],(79,101))
    def test_native_export_colored_border_cannot_be_cropped_away(self):
        source=self.path/'source.png';actual=self.path/'native.png'
        trace.write_image(source,np.full((80,100,3),255,np.uint8))
        image=np.full((80,101,3),255,np.uint8);image[20:40,-1]=[0,0,255]
        trace.write_image(actual,image)
        with self.assertRaisesRegex(ValueError,'contains artwork'):
            verify_native_export.compare_export(source,actual,allow_white_rounding_border=True)
    def test_native_export_critical_region_failure_survives_low_global_error(self):
        source=self.path/'source.png';actual=self.path/'native.png'
        image=np.full((80,100,3),255,np.uint8);trace.write_image(source,image)
        image[10:20,10:20]=0;trace.write_image(actual,image)
        regions=self.json_file('regions.json',[{'id':'lost-detail','bbox_px':[10,10,10,10],'max_mae':20}])
        report=verify_native_export.compare_export(source,actual,regions)
        self.assertLess(report['pixel_mae_bgr'],20)
        self.assertEqual(report['status'],'FAIL')
        self.assertEqual(report['threshold_failures'],['lost-detail:max_mae'])
    def test_source_size_export_dryrun_uses_imported_canvas_and_rejects_stale_review(self):
        graphics=self.svg_file()
        digest=hashlib.sha256(graphics.read_bytes()).hexdigest()
        self.json_file('native-import-report.json',{'status':'PASS','svg_sha256':digest,'scale':.5,'target_document':'user.ai'})
        self.json_file('native-config.json',{'input':str(graphics),'sha256':digest,'jobName':'job','canvasWidth':100,'canvasHeight':80})
        qa=self.json_file('qa.json',{'status':'PASS','svg_sha256':digest})
        args=['powershell.exe','-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',str(SCRIPT_ROOT/'export_native_figure.ps1'),'-NativeWorkDir',str(self.path),'-QaReport',str(qa),'-OutputPng',str(self.path/'result.png'),'-DryRun']
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        plan=json.loads(result.stdout.splitlines()[0])
        self.assertEqual((plan['width'],plan['height']),(100,80))
        self.assertIn('No Illustrator connection',result.stdout)
        qa.write_text(json.dumps({'status':'PASS','svg_sha256':'stale'}),encoding='utf-8')
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('NATIVE_EXPORT_REVIEW_INVALID',result.stderr)
    def test_low_contrast_edges_detect_faint_connector(self):
        source=np.ones((80,100,3),np.uint8)*240
        output=source.copy()
        cv2.line(source,(10,40),(90,40),(224,224,224),1)
        self.assertEqual(compare.edge_f1(source,output),1)
        self.assertEqual(compare.edge_f1(source,output,20,60),0)
    def test_region_negative_size_rejected(self):
        image=np.ones((80,100,3),np.uint8)*255
        regions=self.json_file("regions.json",[{"id":"bad","bbox_px":[5,5,-2,10]}])
        with self.assertRaises(ValueError):
            compare.region_metrics(image,image,regions)
    def test_region_duplicate_id_rejected(self):
        image=np.ones((80,100,3),np.uint8)*255
        regions=self.json_file("regions.json",[{"id":"x","bbox_px":[5,5,10,10]}]*2)
        with self.assertRaises(ValueError):
            compare.region_metrics(image,image,regions)
    def test_region_nonfinite_threshold_rejected(self):
        image=np.ones((80,100,3),np.uint8)*255
        regions=self.json_file("regions.json",[{"id":"x","bbox_px":[5,5,10,10],"max_mae":float("nan")}])
        with self.assertRaises(ValueError):
            compare.region_metrics(image,image,regions)
    def test_comparison_rejects_stretched_canvas(self):
        source=self.path/"source.png"
        trace.write_image(source,np.ones((80,100,3),np.uint8)*255)
        svg=self.svg_file("wrong.svg",'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 80"><rect id="x" width="200" height="80" fill="#fff"/></svg>')
        with self.assertRaises(ValueError):
            compare.compare(SimpleNamespace(source=source,svg=svg,regions=None))
    def test_region_previews_are_qa_only_and_single_preview_stays_single(self):
        source=self.path/"source.png"
        trace.write_image(source,np.ones((80,100,3),np.uint8)*255)
        regions=self.json_file("regions.json",[{"id":"x","bbox_px":[5,5,20,10]}])
        preview=self.path/"preview.png"
        report=compare.compare(SimpleNamespace(source=source,svg=self.svg_file(),regions=regions,
                          preview=preview,region_previews=self.path/"crops",contact_sheet=None,
                          diff=None,report=None,max_mae=None,min_edge_f1=None))
        self.assertEqual(compare.load_image(preview).shape[:2],(80,100))
        self.assertTrue(Path(report["regions"][0]["qa_crop"]).is_file())
    def test_region_list_and_threshold_failure(self):
        svg=self.svg_file()
        source=self.path/"source.png"
        trace.write_image(source,np.ones((80,100,3),np.uint8)*255)
        bad=self.svg_file("bad.svg",'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" viewBox="0 0 100 80"><rect id="bg" width="100" height="80" fill="#fff"/><rect id="patch" x="10" y="10" width="10" height="10" fill="#000"/></svg>')
        regions=self.json_file("regions.json",[{"id":"small","bbox_px":[10,10,10,10],"critical":True,"max_mae":20}])
        report=compare.compare(SimpleNamespace(source=str(source),svg=str(bad),regions=str(regions),
                         preview=None,contact_sheet=None,diff=None,report=None,max_mae=None,min_edge_f1=None))
        self.assertEqual(report["quality_gate"],"FAIL")
        self.assertLess(report["pixel_mae_bgr"],20)  # global score hides it
        self.assertTrue(any("region:small" in item for item in report["threshold_failures"]))
    def merge_args(self,base,overlay):
        return SimpleNamespace(base=str(base),overlay=[str(overlay)],output=str(self.path/"master.svg"),overlay_prefix=None,report=None,remove_id=[])
    def test_merge_root_styles_and_ids_preserved(self):
        base=self.svg_file()
        overlay=self.svg_file("overlay.svg",'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" viewBox="0 0 100 80" fill="#f00" opacity=".4" transform="translate(2,3)"><g id="base"><ellipse id="x" cx="50" cy="40" rx="10" ry="5"/></g></svg>')
        args=self.merge_args(base,overlay)
        merge.merge(args)
        root=ET.parse(args.output).getroot()
        validate(root)
        self.assertEqual(root[-1].get("opacity"),".4")
        self.assertEqual(root[-1].get("transform"),"translate(2,3)")
        ids=[node.get("id") for node in root.iter() if node.get("id")]
        self.assertEqual(len(ids),len(set(ids)))
    def test_merge_mismatched_canvas_rejected(self):
        base=self.svg_file()
        overlay=self.svg_file("overlay.svg",'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 80"><rect id="x" width="5" height="5"/></svg>')
        with self.assertRaises(ValueError):
            merge.merge(self.merge_args(base,overlay))
    def test_merge_explicit_replace_preserves_original(self):
        base=self.svg_file()
        original=base.read_bytes()
        overlay=self.svg_file("overlay.svg")
        args=self.merge_args(base,overlay)
        args.remove_id=["base"]
        merge.merge(args)
        self.assertEqual(base.read_bytes(),original)
        self.assertEqual(len(ET.parse(args.output).getroot()),1)
    def test_raster_overlay_rejected(self):
        base=self.svg_file()
        overlay=self.svg_file("overlay.svg",'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><image id="r" href="test.png"/></svg>')
        with self.assertRaises(ValueError):
            merge.merge(self.merge_args(base,overlay))
    def test_editable_glow_alpha_monotonic(self):
        parts=scene.soft_glow_parts({"cx":50,"cy":40,"rx":20,"ry":10,"opacity":.4},"glow")
        root=ET.fromstring("<svg>"+"".join(parts)+"</svg>")
        cumulative=0
        for element in root:
            alpha=float(element.get("opacity"))
            self.assertTrue(0<=alpha<=1)
            next_alpha=1-(1-cumulative)*(1-alpha)
            self.assertGreaterEqual(next_alpha,cumulative)
            cumulative=next_alpha
        self.assertAlmostEqual(cumulative,.4,delta=.002)
    def test_dashed_curve_is_native_paths(self):
        parts=scene.curved_arrow_parts({"points":[[0,0],[0,60],[80,60],[80,0]],"dashed":True},"arrow")
        root=ET.fromstring('<svg viewBox="0 0 100 80">'+"".join(parts)+"</svg>")
        validate(root)
        self.assertGreater(len(root),3)
        self.assertEqual(root[-1].tag,"polygon")
        self.assertFalse(any(node.get("stroke-dasharray") for node in root))
    def qa_inputs(self):
        svg=self.semantic_svg()
        digest=hashlib.sha256(svg.read_bytes()).hexdigest()
        metrics=self.json_file("compare.json",{"svg_sha256":digest,"quality_gate":"human-visual-review-required",
               "threshold_failures":[],"regions":[{"id":"heart","critical":True}]})
        review_data={"svg_sha256":digest,"checks":{key:{"status":"pass","evidence":"synthetic test only"} for key in gate.CHECKS},
                     "unresolved_issues":[],"regions":{"heart":"pass"}}
        groups=object_groups.audit(ET.parse(svg).getroot())['objects']
        plan=self.json_file('drawing-plan.json',{'schema':'vector-redraw-v1','canvas':[100,80],
            'objects':[{'id':o['id'],'construction':'authored','reference_features':['Synthetic paired DNA lines or backdrop'],
                'parts':[{'id':v,'role':'shape'} for v in o['graphic_ids']]+[{'id':v,'role':'text'} for v in o['text_ids']]} for o in groups]})
        review_data['drawing_plan']=str(plan)
        return svg,metrics,review_data
    def test_review_gate_accepts_complete_bound_review(self):
        svg,metrics,data=self.qa_inputs()
        self.assertEqual(gate.build(svg,metrics,self.json_file("review.json",data))["status"],"PASS")
    def test_review_gate_rejects_stale_review(self):
        svg,metrics,data=self.qa_inputs()
        data["svg_sha256"]="old"
        self.assertEqual(gate.build(svg,metrics,self.json_file("review.json",data))["status"],"FAIL")
    def test_review_gate_rejects_unchecked_critical_region(self):
        svg,metrics,data=self.qa_inputs()
        data["regions"]={}
        self.assertEqual(gate.build(svg,metrics,self.json_file("review.json",data))["status"],"FAIL")
    def test_review_gate_rejects_unresolved_typo(self):
        svg,metrics,data=self.qa_inputs()
        data["unresolved_issues"]=["label wrong"]
        self.assertEqual(gate.build(svg,metrics,self.json_file("review.json",data))["status"],"FAIL")
    def test_review_gate_rejects_null_evidence(self):
        svg,metrics,data=self.qa_inputs()
        data["checks"]["text"]["evidence"]=None
        self.assertEqual(gate.build(svg,metrics,self.json_file("review.json",data))["status"],"FAIL")
    def test_review_gate_rejects_fragmented_flat_output_even_with_good_visual_score(self):
        svg,metrics,data=self.qa_inputs()
        root=ET.parse(svg).getroot();root.attrib.pop('data-huitu-grouping');ET.ElementTree(root).write(svg,encoding='utf-8')
        digest=hashlib.sha256(svg.read_bytes()).hexdigest();data['svg_sha256']=digest
        metric_data=json.loads(metrics.read_text());metric_data['svg_sha256']=digest;metrics.write_text(json.dumps(metric_data))
        report=gate.build(svg,metrics,self.json_file('review.json',data))
        self.assertEqual(report['status'],'FAIL');self.assertTrue(any('movable' in x for x in report['errors']))
    def test_trace_preset_runtime_end_to_end(self):
        # Synthetic input only, not a user figure. Verify editable curves and
        # live text survive the actual installed tracer API.
        image=np.full((120,160,3),245,np.uint8)
        cv2.circle(image,(110,70),18,(80,140,220),3)
        path=self.path/"synthetic.png"
        trace.write_image(path,image)
        manifest_path=self.json_file("text.json",{"source":{"width_px":160,"height_px":120},
                         "text_elements":[self.entry(mask_mode="none")]})
        args=SimpleNamespace(input=str(path),output=str(self.path/"trace.svg"),text_manifest=str(manifest_path),
             mask_output=None,inpaint_radius=2,cleaned_output=str(self.path/"clean.png"),analysis_output=None,
             filter_speckle=1,color_precision=7,layer_difference=4,corner_threshold=60,length_threshold=2,
             max_iterations=10,splice_threshold=45,path_precision=2,id_prefix="test")
        report=trace.reconstruct(args)
        root=ET.parse(args.output).getroot()
        validate(root)
        self.assertEqual(report["live_text_entries"],1)
        self.assertTrue(any(node.tag.endswith("text") for node in root))
    def test_font_resolver_with_mock_illustrator(self):
        node=os.environ.get('HUITU_NODE') or shutil.which('node')
        if not node:self.skipTest('Node.js is needed only for mock JSX tests')
        runtime=SCRIPT_ROOT/"native_svg_import.jsx"
        harness=Path(__file__).with_name("font_resolver_test.js")
        result=subprocess.run([str(node),str(harness),str(runtime)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn("FONT_TEST_PASS",result.stdout)
    def test_native_object_routing_does_not_put_labels_in_figure_root(self):
        node=os.environ.get('HUITU_NODE') or shutil.which('node')
        if not node:self.skipTest('Node.js is needed only for mock JSX tests')
        result=subprocess.run([str(node),str(Path(__file__).with_name('native_grouping_test.js')),str(SCRIPT_ROOT/'native_svg_import.jsx')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('NATIVE_GROUP_ROUTING_PASS',result.stdout)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SkillTests))
    report={"tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
            "status":"PASS" if result.wasSuccessful() else "FAIL",
            "user_images_processed":False,"illustrator_contacted":False,"api_requests":0}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
