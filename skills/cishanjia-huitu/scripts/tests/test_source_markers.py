import sys,unittest,xml.etree.ElementTree as E
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compose_scene import curved_arrow_parts
class TestMarkers(unittest.TestCase):
 def test_horizontal(self):
  p=E.fromstring(curved_arrow_parts({'points':[[0,0],[10,0],[20,0],[30,0]],'head_style':'stealth','head_length':12,'head_width':10,'head_inset':3},'test')[-1])
  self.assertEqual(p.get('points'),'30.00,0.00 18.00,5.00 21.00,0.00 18.00,-5.00')
 def test_vertical(self):
  p=E.fromstring(curved_arrow_parts({'points':[[0,0],[0,10],[0,20],[0,30]],'head_style':'stealth','head_length':12,'head_width':10,'head_inset':3},'test')[-1])
  self.assertEqual(len(p.get('points').split()),4)
  self.assertTrue(p.get('points').startswith('0.00,30.00'))
 def test_invalid_dimensions(self):
  for v in (-1,float('nan'),float('inf')):
   with self.assertRaises(ValueError):curved_arrow_parts({'points':[[0,0],[1,0],[2,0],[3,0]],'head_style':'stealth','head_length':v},'test')
 def test_invalid_inset(self):
  with self.assertRaises(ValueError):curved_arrow_parts({'points':[[0,0],[1,0],[2,0],[3,0]],'head_style':'stealth','head_length':3,'head_inset':3},'test')
 def test_piecewise_one_head(self):
  out=curved_arrow_parts({'segments':[[[0,0],[1,0],[2,0],[3,0]],[[3,0],[3,1],[3,2],[3,3]]],'head_style':'stealth'},'test')
  self.assertEqual(sum('polygon' in p for p in out),1)
if __name__=='__main__':unittest.main()
