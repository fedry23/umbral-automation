import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from PIL import Image
from scripts.umbral3_queue import plan, process, BudgetStore, SLOT_CAP, HEADROOM
from scripts.umbral3_storage import LocalStore, object_key

ROOT = Path(__file__).resolve().parents[1]
NOW = dt.datetime(2027, 3, 28, 0, tzinfo=dt.timezone.utc)

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raw = json.loads((ROOT / "tests/fixtures/umbral3_stories.json").read_text())
        self.a = dict(raw[0], publish_date="2027-03-28")
        self.b = dict(raw[1], publish_date="2027-03-28")
        self.catalogs = {"09": [self.a], "21": [self.b]}
        self.recipe = {"model": "mock"}
        self.store = BudgetStore(LocalStore(Path(self.tmp.name) / "store"))
        self.generator = Mock(side_effect=self.images)

    def images(self, story, folder):
        for i in range(len(story["scenes"])):
            Image.new("RGB", (256,384), (i*20,40,30)).save(folder / f"scene_{i:02}.png")

    def test_plan_dst_and_missing(self):
        rows = [r for r, _ in plan(NOW, self.catalogs)]
        self.assertEqual(len(rows), 14)
        self.assertEqual(rows[0]["scheduled_utc"], "2027-03-28T07:00:00+00:00")
        self.assertEqual(rows[0]["state"], "awaiting_visual_assets")
        self.assertEqual(rows[2]["state"], "missing_story")

    def test_duplicate_across_slots_and_dates(self):
        self.catalogs["21"] = [dict(self.a, publish_date="2027-03-29")]
        rows = [r for r, _ in plan(NOW, self.catalogs)]
        self.assertEqual(rows[0]["state"], "duplicate_narration")
        self.assertEqual(rows[3]["state"], "duplicate_narration")

    def test_ambiguous_and_invalid(self):
        self.catalogs["09"].append(self.b)
        self.catalogs["21"] = [{"publish_date": "2027-03-28", "narration": "test"}]
        rows = [r for r, _ in plan(NOW, self.catalogs)]
        self.assertEqual(rows[0]["state"], "ambiguous_story")
        self.assertEqual(rows[1]["state"], "invalid_storyboard")

    def test_batch_reuse_and_no_publish_claim(self):
        first = process(NOW, self.catalogs, self.recipe, self.store, self.generator, 1)
        self.assertEqual(first["visual_assets_prepared"], 1)
        second = process(NOW, self.catalogs, self.recipe, self.store, self.generator, 1)
        self.assertEqual(second["visual_assets_prepared"], 2)
        third = process(NOW, self.catalogs, self.recipe, self.store, self.generator, 0)
        self.assertEqual(third["visual_assets_prepared"], 2)
        self.assertEqual(third["ready_reels"], 0)
        self.assertEqual(self.generator.call_count, 2)

    def test_corrupt_not_replaced(self):
        self.store.store.put_new(object_key(self.a, "2027-03-28", "09", self.recipe), b"bad")
        result = process(NOW, self.catalogs, self.recipe, self.store, self.generator, 0)
        self.assertEqual(result["slots"][0]["state"], "storage_or_integrity_error")
        self.generator.assert_not_called()

    def test_quota_before_generation(self):
        self.store.quota_reader = lambda: {"free": HEADROOM + SLOT_CAP - 1}
        result = process(NOW, self.catalogs, self.recipe, self.store, self.generator, 1)
        self.assertEqual(result["attempted_generation"], 0)
        self.assertEqual(result["slots"][0]["state"], "storage_or_integrity_error")
        self.generator.assert_not_called()

    def test_failed_generation_consumes_budget(self):
        self.generator.side_effect = RuntimeError("failure")
        result = process(NOW, self.catalogs, self.recipe, self.store, self.generator, 1)
        self.assertEqual(result["attempted_generation"], 1)
        self.assertEqual(self.generator.call_count, 1)
        self.assertEqual(result["ready_reels"], 0)
