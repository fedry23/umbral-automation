"""Owner's explicit v3 six-scene visual signoff is byte-bound, not universal."""
import json
from pathlib import Path
import unittest
from scripts.umbral3_visual_approval import require_visual_approval

ROOT=Path(__file__).resolve().parents[1]
APPROVAL=ROOT/"docs/visual_approvals/2026-11-22.json"

class OwnerReviewedV3Tests(unittest.TestCase):
    def test_exact_six_approved_images_are_bound_to_civil_slot(self):
        obj=json.loads(APPROVAL.read_text(encoding="utf-8"))
        self.assertEqual(obj["status"],"approved")
        self.assertEqual(obj["slot"],"21")
        self.assertEqual(obj["date"],"2026-11-22")
        self.assertEqual(len(obj["scene_sha256"]),6)
        assets={n:{"sha256":sha,"bytes":100} for n,sha in obj["scene_sha256"].items()}
        self.assertTrue(require_visual_approval(ROOT,obj["date"],obj["slot"],obj["story_sha256"],assets))
        with self.assertRaisesRegex(RuntimeError,"missing"):
            require_visual_approval(ROOT,obj["date"],"09",obj["story_sha256"],assets)
        with self.assertRaisesRegex(RuntimeError,"missing"):
            require_visual_approval(ROOT,"2026-11-23","21",obj["story_sha256"],assets)
    def test_modified_scene_or_narration_cannot_reuse_approval(self):
        obj=json.loads(APPROVAL.read_text(encoding="utf-8"))
        assets={n:{"sha256":sha,"bytes":100} for n,sha in obj["scene_sha256"].items()}
        assets["scene_03.png"]["sha256"]="a"*64
        with self.assertRaisesRegex(RuntimeError,"different visual"):
            require_visual_approval(ROOT,obj["date"],obj["slot"],obj["story_sha256"],assets)
        assets["scene_03.png"]["sha256"]=obj["scene_sha256"]["scene_03.png"]
        with self.assertRaisesRegex(RuntimeError,"does not match"):
            require_visual_approval(ROOT,obj["date"],obj["slot"],"b"*64,assets)
