"""Regression checks for editable native paint and protected-object preparation."""
import json,sys,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime_env import bootstrap
bootstrap()
import numpy as np
from svg_contract import validate
from native_gradients import halo_gradient
from object_groups import group_attributes,audit
from prepare_native_svg import prepare,explicit_rect_path
from contour_refit import closed_path
from compose_scene import compose

class NativePaintTests(unittest.TestCase):
 def root(self):return ET.Element('svg',{'xmlns':'http://www.w3.org/2000/svg','width':'100','height':'80','viewBox':'0 0 100 80','data-huitu-grouping':'semantic-v1'})
 def halo(self):
  root=self.root();paint=halo_gradient(root,'halo-paint','#ff715c',.7)
  g=ET.SubElement(root,'g',group_attributes('halo','Halo','other'))
  ET.SubElement(g,'ellipse',id='halo-shape',cx='50',cy='40',rx='30',ry='10',fill=paint)
  ET.SubElement(g,'text',id='halo-text',x='50',y='45',**{'font-family':'Arial','font-size':'12','text-anchor':'middle'}).text='Oxidative stress'
  return root
 def test_one_shape_owns_all_gradient_stops(self):
  root=self.halo();validate(root);r=audit(root)
  self.assertEqual(r['status'],'PASS');self.assertEqual(r['objects'][0]['graphic_count'],1);self.assertEqual(r['objects'][0]['text_count'],1)
 def test_gradient_resources_stay_outside_native_carrier(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);ET.ElementTree(self.halo()).write(p/'source.svg',encoding='utf-8')
   self.assertEqual(prepare(p/'source.svg',p/'graphics.svg',p/'labels.json'),1)
   root=ET.parse(p/'graphics.svg').getroot()
   self.assertTrue(root[0].tag.endswith('defs'));self.assertEqual(root[1].get('id'),'huitu-native-graphics-root')
   self.assertFalse(any(n.tag.endswith('text') for n in root.iter()))
   self.assertEqual(json.loads((p/'labels.json').read_text())['labels'][0]['object_id'],'halo')
 def test_external_or_missing_paint_rejected(self):
  for paint in ['url(https://example.com/paint)','url(#missing)','url(#halo-paint) red']:
   root=self.halo();root[-1][0].set('fill',paint)
   with self.assertRaises(ValueError):validate(root)
 def test_nonfinite_or_unordered_stop_rejected(self):
  root=self.halo();root[0][0][0].set('offset','nan')
  with self.assertRaises(ValueError):validate(root)
  root=self.halo();root[0][0][1].set('offset','1')
  with self.assertRaises(ValueError):validate(root)
 def test_native_glow_manifest_creates_one_ellipse(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'scene.svg';compose({'canvas':{'width':100,'height':80},'objects':[{'id':'halo','type':'native_glow','cx':50,'cy':40,'rx':30,'ry':10,'fill':'#ff715c','opacity':.7}]},p)
   root=ET.parse(p).getroot();self.assertEqual(sum(n.tag.endswith('ellipse') for n in root.iter()),1);validate(root)
 def test_rounded_rectangle_becomes_fixed_cubics(self):
  n=ET.Element('rect',id='cell-membrane',x='10',y='20',width='200',height='100',rx='30',fill='#eef',transform='scale(.2)')
  explicit_rect_path(n)
  self.assertEqual(n.tag,'path');self.assertEqual(n.get('id'),'cell-membrane');self.assertEqual(n.get('transform'),'scale(.2)')
  self.assertTrue(n.get('d').startswith('M 40.0 20.0'));self.assertEqual(n.get('d').count(' C '),4)
  self.assertNotIn('rx',n.attrib);self.assertNotIn('width',n.attrib)
 def test_closed_refit_preserves_noncircular_silhouette(self):
  theta=np.linspace(0,2*np.pi,240,endpoint=False);r=20+5*np.sin(5*theta)
  pts=np.column_stack([50+r*np.cos(theta),40+r*np.sin(theta)])
  d,n=closed_path(pts,.3)
  self.assertTrue(d.endswith(' Z'));self.assertGreater(n,5);self.assertLess(n,60)
if __name__=='__main__':unittest.main()
