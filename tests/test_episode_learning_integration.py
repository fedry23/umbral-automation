import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path

from scripts.episode_state import next_episode, planned_episode, validate_episode
from scripts.adaptive_learning import analyze


class EpisodeIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for directory in ("published", "pending"):
            (self.root / "docs" / directory).mkdir(parents=True)

    def put(self, directory, key, payload):
        (self.root / "docs" / directory / (key + ".json")).write_text(json.dumps(payload))

    def receipt(self, key, number, media_id=None, verification="published_media_read_back"):
        self.put("published", key, dict(date=key[:10], episode_number=number,
                 instagram_media_id=media_id or str(number), permalink="https://example.com/reel",
                 verification=verification))

    def test_two_slots_after_confirmed_morning(self):
        self.receipt("2026-11-18", 11)
        self.assertEqual(planned_episode("2026-11-19", "09", self.root), 12)
        self.assertEqual(planned_episode("2026-11-19", "21", self.root, anticipate_morning=True), 13)
        self.receipt("2026-11-19_09", 12)
        self.assertEqual(planned_episode("2026-11-19", "21", self.root), 13)
        self.assertEqual(planned_episode("2026-11-19", "09", self.root), 12)

    def test_failed_morning_does_not_consume(self):
        self.receipt("2026-11-18", 11)
        self.assertEqual(planned_episode("2026-11-19", "21", self.root, anticipate_morning=True), 13)
        with self.assertRaisesRegex(ValueError, "Stale"):
            validate_episode("2026-11-19", "21", 13, self.root)
        self.assertEqual(validate_episode("2026-11-19", "21", 12, self.root), 12)

    def test_unresolved_blocks_both_slots_then_verified_recovers(self):
        self.put("pending", "2026-11-19_09", {"status": "publish_intent", "episode_number": 11})
        for slot in ("09", "21"):
            with self.assertRaisesRegex(ValueError, "Unresolved"):
                planned_episode("2026-11-19", slot, self.root)
        self.receipt("2026-11-19_09", 11)
        self.assertEqual(planned_episode("2026-11-19", "21", self.root), 12)

    def test_unverified_receipt_blocks(self):
        self.receipt("2026-11-19_09", 11, verification="pending")
        with self.assertRaisesRegex(ValueError, "Unverified"):
            next_episode(self.root)

    def test_test_reel_does_not_consume(self):
        self.receipt("test-cinematic-episode-999", 999)
        self.assertEqual(next_episode(self.root), 11)

    def test_duplicate_media_and_number_block(self):
        self.receipt("2026-11-18", 11)
        self.receipt("2026-11-19_09", 12, media_id="11")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            next_episode(self.root)
        self.receipt("2026-11-19_09", 11, media_id="12")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            next_episode(self.root)

    def test_concurrent_render_is_read_only(self):
        self.receipt("2026-11-18", 11)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            numbers = list(pool.map(lambda _: planned_episode("2026-11-19", "09", self.root), range(64)))
        self.assertEqual(set(numbers), {12})
        self.assertEqual(next_episode(self.root), 12)
        self.assertFalse(list((self.root / "docs/pending").iterdir()))

    def test_legacy_migration_exact_only(self):
        legacy = dict(date="2026-11-16", title="La costura", instagram_media_id="18096307043444916")
        self.put("published", "2026-11-16", legacy)
        self.assertEqual(next_episode(self.root), 11)
        self.put("published", "2026-11-16", {**legacy, "instagram_media_id": "other"})
        with self.assertRaises(ValueError):
            next_episode(self.root)

    def test_shared_workflow_lock(self):
        import yaml
        for name in ("publish_daily.yml", "publish_morning.yml"):
            flow = yaml.load((Path(".github/workflows") / name).read_text(), Loader=yaml.BaseLoader)
            self.assertEqual(flow["concurrency"]["group"], "umbral-instagram-official")
            self.assertEqual(flow["concurrency"]["cancel-in-progress"], "false")
            self.assertIn("refs/heads/main", flow["jobs"]["publicar"]["if"])


class LearningIntegration(unittest.TestCase):
    def test_real_snapshot_advisory_only(self):
        rows = json.loads(Path("learning/baseline-2026-11-18.json").read_text())["rows"]
        result = analyze(rows)
        self.assertEqual(result["sample_size"], 8)
        self.assertEqual(result["reach_sum"], 268)
        self.assertFalse(result["automatic_changes"])

    def test_invalid_rows_and_duplicate(self):
        valid = {"media_id": "a", "media_reach": 10, "media_reel_skip_rate": .6,
                 "media_reel_avg_watch_time": 1000}
        invalid = [None, {}, {**valid, "media_id": "b", "media_reach": True},
                   {**valid, "media_id": "c", "media_reel_skip_rate": 2},
                   {**valid, "media_id": "d", "media_reel_avg_watch_time": float("nan")}]
        self.assertEqual(analyze(invalid)["status"], "insufficient_data")
        self.assertEqual(analyze([valid, valid] + invalid)["sample_size"], 1)
