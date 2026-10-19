import json,sys,tempfile,unittest
from pathlib import Path
SCRIPTS=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SCRIPTS))
from runtime_env import bootstrap
bootstrap()
from render_compare import render,save_image
from review_prepare import prepare
from quality_gate import build

class PrepareTests(unittest.TestCase):
    def test_preparation_keeps_human_review_pending_and_existing_review_intact(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);svg=root/'m.svg';plan=root/'p.json';source=root/'s.png';out=root/'qa';out.mkdir()
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" data-huitu-build="vector-redraw-v1" data-huitu-grouping="semantic-v1"><g id="background" data-huitu-object-id="background" data-huitu-name="Background" data-huitu-kind="background"><rect id="p" width="100" height="80" fill="#fff"/></g></svg>')
            data={'schema':'vector-redraw-v1','canvas':[100,80],'objects':[{'id':'background','construction':'authored','reference_features':['white canvas'],'parts':[{'id':'p','role':'shape'}]}]};plan.write_text(json.dumps(data))
            save_image(source,render(svg,100,80));review=out/'visual-review.json';review.write_text('existing manual review')
            r=prepare(source,svg,plan,None,out,root/'cache');self.assertEqual(r['status'],'AWAITING_VISUAL_REVIEW');self.assertFalse(r['automatic_approval']);self.assertEqual(review.read_text(),'existing manual review')
            result=build(svg,out/'comparison.json',out/'visual-review-template.json',drawing_plan=plan)
            self.assertEqual(result['status'],'FAIL');self.assertTrue(any('visual check' in s for s in result['errors']))
            data['objects'][0]['parts']=[];plan.write_text(json.dumps(data));r=prepare(source,svg,plan,None,out,root/'cache');self.assertEqual(r['status'],'FAIL')

if __name__=='__main__':unittest.main(verbosity=2)
