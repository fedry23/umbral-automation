"""Prevent deploying stale, unreviewed or already-published V3.1 scenes."""
import datetime as dt
import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.umbral3_release_policy import approved_slot,future_coverage
from scripts.umbral3_approved_restore import approved_restore

ROOT=Path(__file__).resolve().parents[1]
NOW=dt.datetime(2026,11,21,21,30,tzinfo=ZoneInfo("Europe/Madrid"))


class ReleasePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Snapshot the 21-Nov review board before 22-Nov live receipts existed.

        Policy tests must never change meaning as real Reels are published.
        Keep immutable reviews and stories; isolate only publication state.
        """
        cls._archive = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._archive.cleanup)
        snapshot = Path(cls._archive.name)
        for filename in ("stories.json", "stories_morning.json"):
            shutil.copy2(ROOT / filename, snapshot / filename)
        docs = snapshot / "docs"
        docs.mkdir()
        for filename in ("umbral3-owner-visual-signoff-2026-11-21.json",
                         "umbral3-production-rollout.json", "umbral3-automatic-qa.json"):
            shutil.copy2(ROOT / "docs" / filename, docs / filename)
        shutil.copytree(ROOT / "docs" / "visual_approvals", docs / "visual_approvals")
        published = docs / "published"
        published.mkdir()
        (docs / "pending").mkdir()
        for receipt in (ROOT / "docs" / "published").glob("*.json"):
            if receipt.stem[:10] <= "2026-11-21":
                shutil.copy2(receipt, published / receipt.name)
        cls.history = snapshot

    def test_private_art_and_story_bound_to_exact_future_slots(self):
        for day,slot in (("2026-11-22","09"),("2026-11-22","21"),
                         ("2026-11-25","09"),("2026-11-27","21")):
            with self.subTest(day=day,slot=slot):
                row=approved_slot(day,slot,self.history,NOW)
                self.assertEqual(len(row["scene_sha256"]),6)
                self.assertTrue(row["visual_approved"])
                self.assertFalse(row["ready_to_publish"])
                self.assertEqual(len(row["bundle_sha256"]),64)
    def test_refuses_11_21_already_posted_even_if_owner_approved(self):
        with self.assertRaisesRegex(RuntimeError,"publication receipt"):
            approved_slot("2026-11-21","21",self.history,NOW)
    def test_refuses_future_slot_without_review(self):
        with self.assertRaisesRegex(RuntimeError,"No exact owner-approved"):
            approved_slot("2026-11-28","09",self.history,NOW)
    def test_next_seven_days_reports_twelve_valid_and_two_missing_reviews(self):
        result=future_coverage(self.history,NOW)
        self.assertEqual(result["expected_future_slots"],14)
        self.assertEqual(result["approved"],12)
        self.assertEqual(len(result["unapproved_or_missing"]),2)
        self.assertFalse(result["production_ready"])
    def test_fails_closed_when_story_hash_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            p=Path(tmp)
            (p/"docs"/"visual_approvals").mkdir(parents=True)
            (p/"docs"/"published").mkdir()
            (p/"docs"/"pending").mkdir()
            (p/"docs"/"umbral3-owner-visual-signoff-2026-11-21.json").write_bytes(
                (ROOT/"docs"/"umbral3-owner-visual-signoff-2026-11-21.json").read_bytes())
            source=json.loads((ROOT/"stories_morning.json").read_text(encoding="utf-8"))
            for s in source:
                if s.get("publish_date")=="2026-11-22":
                    s["title"]="Tampered"
            (p/"stories_morning.json").write_text(json.dumps(source))
            src=ROOT/"docs"/"visual_approvals"/"2026-11-22_09.json"
            (p/"docs"/"visual_approvals"/"2026-11-22_09.json").write_bytes(src.read_bytes())
            with self.assertRaisesRegex(RuntimeError,"metadata does not match"):
                approved_slot("2026-11-22","09",p,NOW)
    def test_refuses_modified_candidate_index_before_restore(self):
        selected=approved_slot("2026-11-22","09",self.history,NOW)
        store=object()
        with patch("scripts.umbral3_approved_restore.find",return_value={
            "bundle_sha256":"f"*64,"story_sha256":selected["story_sha256"],
            "visual_approved":False,"ready_to_publish":False,
        }),patch("scripts.umbral3_approved_restore.restore") as operation:
            with self.assertRaisesRegex(RuntimeError,"does not match"):
                approved_restore("2026-11-22","09","/tmp/private-test",self.history,store,NOW)
            operation.assert_not_called()


if __name__=="__main__":
    unittest.main()
