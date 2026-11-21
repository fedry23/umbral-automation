"""Only an explicit exact-scene owner review can unlock live finalization."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.umbral3_visual_approval import require_visual_approval

DAY="2026-11-22"
SLOT="09"
STORY="b"*64

class VisualApprovalTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        folder=self.root/"docs"/"visual_approvals"
        folder.mkdir(parents=True)
        self.file=folder/"2026-11-22_09.json"
        self.assets={f"scene_{n:02}.png":{"sha256":f"{n+1:064x}","bytes":101} for n in range(6)}
        self.approval={
            "version":1,"status":"approved","date":DAY,"slot":SLOT,
            "reviewer":"fedry23","private_bucket":"Fedry23/umbral-private",
            "reviewed_at":"2026-11-20T12:00:00+00:00","story_sha256":STORY,
            "scene_sha256":{k:v["sha256"] for k,v in self.assets.items()},
            "notes":"I inspected every scene, characters and story continuity."
        }
    def write(self):
        self.file.write_text(json.dumps(self.approval),encoding="utf-8")
    def approved(self):
        return require_visual_approval(self.root,DAY,SLOT,STORY,self.assets)
    def test_missing_review_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,"missing"):
            self.approved()
    def test_exact_owner_review_passes(self):
        self.write()
        self.assertTrue(self.approved())
    def test_tampered_scene_cannot_use_approval(self):
        self.write()
        self.assets["scene_03.png"]["sha256"]="a"*64
        with self.assertRaisesRegex(RuntimeError,"different visual"):
            self.approved()
    def test_wrong_story_cannot_use_approval(self):
        self.write()
        self.approval["story_sha256"]="c"*64
        self.write()
        with self.assertRaisesRegex(RuntimeError,"does not match"):
            self.approved()
    def test_fake_reviewer_cannot_use_approval(self):
        self.approval["reviewer"]="ai"
        self.write()
        with self.assertRaisesRegex(RuntimeError,"does not match"):
            self.approved()
    def test_local_boolean_cannot_use_approval(self):
        self.approval["visual_approved"]=True
        self.write()
        with self.assertRaisesRegex(RuntimeError,"does not match"):
            self.approved()
    def test_future_review_date_fails(self):
        self.approval["reviewed_at"]="2099-01-01T00:00:00+00:00"
        self.write()
        with self.assertRaisesRegex(RuntimeError,"future"):
            self.approved()
    def test_mismatched_day_and_slot_fail(self):
        self.write()
        for day,slot in (("2026-11-23","09"),("2026-11-22","21")):
            with self.subTest(day=day,slot=slot),self.assertRaisesRegex(RuntimeError,"missing"):
                require_visual_approval(self.root,day,slot,STORY,self.assets)
    def test_symlink_review_refused(self):
        self.file.symlink_to(self.root/"missing")
        with self.assertRaisesRegex(RuntimeError,"missing"):
            self.approved()
