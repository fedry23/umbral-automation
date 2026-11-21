"""A future 21h intent must not falsely fail CI or bypass strict production."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.ci_receipt_gate import check
from scripts.episode_state import inventory

TZ = ZoneInfo("Europe/Madrid")


class CiReceiptGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for part in ("docs/published", "docs/pending"):
            (self.root / part).mkdir(parents=True)
        (self.root / "docs/published/2026-11-21_09.json").write_text(json.dumps({
            "date": "2026-11-21", "episode_number": 16,
            "instagram_media_id": "18137894143763489",
            "verification": "published_media_read_back",
            "permalink": "https://www.instagram.com/reel/example/",
            "slot": "09"}), encoding="utf-8")
        self.pending = self.root / "docs/pending/2026-11-21.json"
        self.pending.write_text(json.dumps({
            "date": "2026-11-21", "slot": "21", "status": "publish_intent",
            "episode_number": 17, "container": "17938493697185965"
        }), encoding="utf-8")

    def when(self, hour, minute):
        return dt.datetime(2026, 11, 21, hour, minute, tzinfo=TZ)

    def test_future_intent_is_reported_not_erased(self):
        before = self.pending.read_bytes()
        report = check(self.root, now=self.when(19, 50))
        self.assertEqual(report["last_confirmed_episode"], 16)
        self.assertEqual(report["pending_intents"], ["2026-11-21.json"])
        self.assertFalse(report["production_ready"])
        self.assertEqual(before, self.pending.read_bytes())
        with self.assertRaisesRegex(ValueError, "Unresolved publication"):
            inventory(self.root)

    def test_overdue_intent_still_fails_ci(self):
        with self.assertRaisesRegex(ValueError, "reconcile Meta"):
            check(self.root, now=self.when(21, 46))

    def test_malformed_intent_never_passes(self):
        row = json.loads(self.pending.read_text())
        row["status"] = "success"
        self.pending.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, "Untrusted pending"):
            check(self.root, now=self.when(19, 50))

    def test_resolved_receipt_no_longer_blocks(self):
        row = json.loads(self.pending.read_text())
        row.update({"status": "published", "instagram_media_id": "999000111",
                    "permalink": "https://www.instagram.com/reel/verified/",
                    "verification": "published_media_read_back"})
        (self.root / "docs/published/2026-11-21.json").write_text(json.dumps(row))
        report = check(self.root, now=self.when(22, 0))
        self.assertTrue(report["production_ready"])
        self.assertEqual(report["last_confirmed_episode"], 17)


if __name__ == "__main__":
    unittest.main()
