"""Frozen acceptance checkpoint for the first authored seven-day reserve."""
import datetime as dt
import json
from pathlib import Path
import unittest
from scripts.umbral3_queue import plan
from scripts.storyboard import validate_storyboard

ROOT = Path(__file__).resolve().parents[1]

class EditorialReserveTests(unittest.TestCase):
    def test_first_seven_days_have_fourteen_distinct_storyboards(self):
        catalogs = {slot: json.loads((ROOT / filename).read_text(encoding="utf-8"))
                    for slot, filename in (("09", "stories_morning.json"), ("21", "stories.json"))}
        now = dt.datetime(2026, 11, 20, 21, 1, tzinfo=dt.timezone(dt.timedelta(hours=1)))
        rows = plan(now, catalogs)
        self.assertEqual(len(rows), 14)
        self.assertEqual({r["state"] for r, _ in rows}, {"awaiting_visual_assets"})
        self.assertEqual(len({s["title"].casefold() for _, s in rows}), 14)
        self.assertEqual(len({r["story_sha256"] for r, _ in rows}), 14)
        for r, s in rows:
            with self.subTest(slot=r["slot"], day=r["date"]):
                self.assertEqual(s["editorial_protocol"], "fixed-v1")
                self.assertEqual(len(validate_storyboard(s)), 6)
                self.assertTrue(s["narration"].startswith(s["hook"]))
                self.assertFalse(r["ready_to_publish"])
                self.assertFalse(r["visual_approved"])
