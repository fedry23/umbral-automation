"""Private alternate visual renderer cannot overwrite originals or bypass Meta."""
import datetime as dt
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import yaml

from scripts.umbral3_private_rescue import check
from scripts.umbral3_machine_qa import RECOVERY_BACKEND, BACKEND, POLICY, MODEL, REVISION
from scripts.umbral3_finalize_from_reserve import require_machine_evidence
from scripts.umbral3_lightning_scenes import PIN
from scripts.umbral3_reserve import story_key

ROOT=Path(__file__).resolve().parents[1]
DAY="2026-11-28"
STORY=next(x for x in json.loads((ROOT/"stories_morning.json").read_text())
           if x.get("publish_date")==DAY)


class PrivateHorrorRescueTests(unittest.TestCase):
    def test_absent_alternative_index_requests_new_private_media_only(self):
        store=Mock()
        with patch("scripts.umbral3_private_rescue.find",return_value=None),\
             patch("scripts.umbral3_private_rescue.assert_generation_budget") as budget:
            result=check(store,DAY,"09",ROOT)
        self.assertTrue(result["generate"])
        self.assertEqual(result["backend"],RECOVERY_BACKEND)
        self.assertFalse(result["ready_to_publish"])
        budget.assert_called_once_with(store)

    def test_existing_conflicting_alternative_cannot_be_overwritten(self):
        store=Mock()
        pointer={"story_sha256":"a"*64,"model_revision":PIN,
                 "backend":RECOVERY_BACKEND,"bundle_sha256":"b"*64,"bundle_bytes":100}
        with patch("scripts.umbral3_private_rescue.find",return_value=pointer):
            with self.assertRaisesRegex(RuntimeError,"Stale or modified"):
                check(store,DAY,"09",ROOT)
        store.get.assert_not_called()

    def test_corrupt_existing_alternative_bundle_fails_sha_readback(self):
        store=Mock()
        pointer={"story_sha256":story_key(STORY),"model_revision":PIN,
                 "backend":RECOVERY_BACKEND,"bundle_sha256":"b"*64,"bundle_bytes":100}
        store.get.return_value=b"x"*100
        with patch("scripts.umbral3_private_rescue.find",return_value=pointer):
            with self.assertRaisesRegex(RuntimeError,"corrupt"):
                check(store,DAY,"09",ROOT)

    def test_rejects_retrospective_and_wrong_civil_slot(self):
        store=Mock()
        with self.assertRaises(ValueError):
            check(store,"2026-11-27","09",ROOT)
        with self.assertRaises(ValueError):
            check(store,DAY,"18",ROOT)

    def test_private_rescue_workflow_has_no_publication_capabilities(self):
        flow=yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                       Loader=yaml.BaseLoader)
        job=flow["jobs"]["automatic-morning-horror-rescue"]
        self.assertEqual(job["permissions"],{"contents":"read","id-token":"write"})
        self.assertIn("refs/heads/main",job["if"])
        self.assertIn("UMBRAL directed horror private rescue",job["if"])
        self.assertEqual(job["env"]["UMBRAL_HORROR_DIRECTION"],"horror-v3-1")
        self.assertNotIn("IG_ACCESS_TOKEN",str(job))
        self.assertNotIn("graph.facebook.com",str(job))
        self.assertIn("--mode certify",str(job))
        self.assertIn("--require-stored",str(job))
        self.assertIn("--mode check",str(job))

    def test_correct_rescued_sha_certificate_is_valid_but_never_human_signed(self):
        assets={f"scene_{i:02}.png":{"sha256":str(i)*64} for i in range(6)}
        proof={"version":1,"kind":"umbral3-automatic-machine-qa",
               "policy":POLICY,"date":DAY,"slot":"09",
               "story_sha256":story_key(STORY),
               "backend":RECOVERY_BACKEND,
               "model_revision":PIN,"clip_model":MODEL,
               "clip_revision":REVISION,"bundle_sha256":"a"*64,
               "human_review":False,"machine_approved":True,
               "ready_to_publish":False,
               "scene_sha256":{k:v["sha256"] for k,v in assets.items()},
               "image_scores":[45]*6,
               "semantic":{"passed":True,"matching_scenes":5,
                           "horror_scenes":5}}
        self.assertTrue(require_machine_evidence(proof,DAY,"09",STORY,assets,ROOT))
        for mutation in (
            {"backend":"unknown"},
            {"human_review":True},
            {"semantic":{"passed":True,"matching_scenes":5,"horror_scenes":1}},
            {"scene_sha256":{**proof["scene_sha256"],"scene_01.png":"f"*64}},
            {"ready_to_publish":True},
            {"bundle_sha256":"invalid"},
        ):
            with self.subTest(mutation=mutation),self.assertRaisesRegex(RuntimeError,"Machine certificate"):
                require_machine_evidence({**proof,**mutation},DAY,"09",STORY,assets,ROOT)

    def test_failed_initial_28_nov_pilot_stays_failed(self):
        flow=yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                       Loader=yaml.BaseLoader)
        job=flow["jobs"]["automatic-art-private-pilot"]
        final=next(s for s in job["steps"] if s.get("name","").startswith("Fail unless BOTH"))
        self.assertIn("exit 1",final["run"])
        self.assertIn('if [ "$MORNING" != success ] || [ "$EVENING" != success ]',
                      final["run"])
        self.assertIn("steps.auto_morning.outcome",str(final))
        self.assertIn("steps.auto_evening.outcome",str(final))

if __name__=="__main__":
    unittest.main()
