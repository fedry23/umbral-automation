"""Verify real owner-reviewed 84-frame SHA registry and fail-closed publishing."""
import json
from pathlib import Path
import unittest

from scripts.umbral3_visual_approval import require_visual_approval

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"docs"/"umbral3-owner-visual-signoff-2026-11-21.json"


class OwnerMixedReviewTests(unittest.TestCase):
    def test_fourteen_exact_story_and_scene_approvals(self):
        report=json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(report["visual_approved"],14)
        self.assertFalse(report["production_ready"])
        self.assertFalse(report["merge_pr_18_authorized"])
        self.assertEqual(report["private_board_sha256"],
                         "859be1ef1001f5be6476c87db5c90a47f866a30b19d91a39597bbea748e14b2e")
        self.assertEqual([x["index"] for x in report["entries"]],list(range(14)))
        seen=set()
        for item in report["entries"]:
            with self.subTest(index=item["index"]):
                day,slot=item["date"],item["slot"]
                name=day+("_09" if slot=="09" else "")+".json"
                self.assertEqual(item["record"],"docs/visual_approvals/"+name)
                self.assertNotIn((day,slot),seen)
                seen.add((day,slot))
                row=json.loads((ROOT/item["record"]).read_text(encoding="utf-8"))
                self.assertEqual(row["scene_sha256"],item["scene_sha256"])
                self.assertEqual(row["story_sha256"],item["story_sha256"])
                self.assertEqual(set(row["scene_sha256"]),
                                 {f"scene_{j:02}.png" for j in range(6)})
                assets={k:{"sha256":v} for k,v in item["scene_sha256"].items()}
                self.assertTrue(require_visual_approval(ROOT,day,slot,
                                 item["story_sha256"],assets))
                assets["scene_00.png"]["sha256"]="f"*64
                with self.assertRaises(RuntimeError):
                    require_visual_approval(ROOT,day,slot,
                                            item["story_sha256"],assets)

if __name__=="__main__":
    unittest.main()
