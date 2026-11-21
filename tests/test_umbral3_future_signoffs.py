"""Future artwork is never approved by the original immutable 84-image board.

These are synthetic unit fixtures only; this test NEVER writes real approvals.
"""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from scripts.umbral3_reserve import story_key
from scripts.umbral3_release_policy import approved_slot

ROOT = Path(__file__).resolve().parents[1]
DAY, SLOT, KEY = "2026-11-28", "09", "2026-11-28_09"
NOW = dt.datetime(2026, 11, 21, 22, 0, tzinfo=ZoneInfo("Europe/Madrid"))


class FutureSignoffTests(unittest.TestCase):
    def setup_fixture(self, base):
        root = Path(base)
        (root / "docs" / "published").mkdir(parents=True)
        (root / "docs" / "pending").mkdir()
        (root / "docs" / "visual_approvals").mkdir()
        (root / "docs" / "umbral3-future-signoffs").mkdir()
        (root / "docs" / "umbral3-owner-visual-signoff-2026-11-21.json").write_bytes(
            (ROOT / "docs" / "umbral3-owner-visual-signoff-2026-11-21.json").read_bytes()
        )
        source = (ROOT / "stories_morning.json").read_bytes()
        (root / "stories_morning.json").write_bytes(source)
        story = next(x for x in json.loads(source) if x.get("publish_date") == DAY)
        digest = story_key(story)
        scene = {f"scene_{i:02}.png": f"{i+1:064x}" for i in range(6)}
        approved = {
            "version": 1, "status": "approved", "date": DAY, "slot": SLOT,
            "reviewer": "fedry23", "reviewed_at": "2026-11-21T21:00:00Z",
            "private_bucket": "Fedry23/umbral-private", "story_sha256": digest,
            "scene_sha256": scene,
            "notes": "Explicit synthetic test review of board " + "a"*64 +
                     " and private candidate " + "b"*64 +
                     "; this is never a real owner's approval.",
        }
        extension = {
            "version": 1, "kind": "umbral3-explicit-owner-future-signoff",
            "owner": "fedry23", "date": DAY, "slot": SLOT,
            "title": story["title"], "reviewed_at": approved["reviewed_at"],
            "reviewed_board_sha256": "a"*64,
            "backend": "sdxl-lightning-2steps-ov-int8-horror-v3",
            "story_sha256": digest, "private_candidate_bundle_sha256": "b"*64,
            "scene_sha256": scene, "record": "docs/visual_approvals/" + KEY + ".json",
        }
        (root / "docs" / "visual_approvals" / (KEY + ".json")).write_text(
            json.dumps(approved), encoding="utf-8"
        )
        (root / "docs" / "umbral3-future-signoffs" / (KEY + ".json")).write_text(
            json.dumps(extension), encoding="utf-8"
        )
        return approved, extension

    def test_approved_future_art_requires_two_exact_owner_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            approved, extension = self.setup_fixture(tmp)
            result = approved_slot(DAY, SLOT, tmp, NOW)
            self.assertEqual(result["bundle_sha256"], "b"*64)
            self.assertEqual(result["scene_sha256"], approved["scene_sha256"])
            self.assertTrue(result["visual_approved"])
            self.assertFalse(result["ready_to_publish"])

    def test_missing_future_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.setup_fixture(tmp)
            (Path(tmp) / "docs" / "umbral3-future-signoffs" / (KEY + ".json")).unlink()
            with self.assertRaisesRegex(RuntimeError, "No exact owner-approved artwork"):
                approved_slot(DAY, SLOT, tmp, NOW)

    def test_tampered_future_board_and_candidate_are_rejected(self):
        for field, replacement in (
            ("reviewed_board_sha256", "c"*64),
            ("private_candidate_bundle_sha256", "d"*64),
            ("story_sha256", "e"*64),
            ("title", "Changed script"),
            ("owner", "another-person"),
            ("record", "docs/visual_approvals/another.json"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                _, extension = self.setup_fixture(tmp)
                extension[field] = replacement
                (Path(tmp) / "docs" / "umbral3-future-signoffs" / (KEY + ".json")).write_text(
                    json.dumps(extension), encoding="utf-8"
                )
                with self.assertRaises((RuntimeError, ValueError)):
                    approved_slot(DAY, SLOT, tmp, NOW)

    def test_new_media_without_second_explicit_signoff_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.setup_fixture(tmp)
            (Path(tmp) / "docs" / "visual_approvals" / (KEY + ".json")).unlink()
            with self.assertRaises(RuntimeError):
                approved_slot(DAY, SLOT, tmp, NOW)

    def test_future_review_does_not_approve_other_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.setup_fixture(tmp)
            # The morning signoff cannot be reused for the same evening date.
            (Path(tmp) / "stories.json").write_bytes((ROOT / "stories.json").read_bytes())
            with self.assertRaisesRegex(RuntimeError, "No exact owner-approved artwork"):
                approved_slot(DAY, "21", tmp, NOW)
