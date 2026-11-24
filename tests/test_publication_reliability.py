import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.publication_reliability import in_window, due_slot, verified, watchdog, MADRID

class PublicationReliabilityTests(unittest.TestCase):
    def time(self, date, hour, minute=0):
        return dt.datetime.fromisoformat(f"{date}T{hour:02}:{minute:02}:00").replace(tzinfo=MADRID)

    def test_civil_window_and_stale_queued_runs(self):
        for day in ("2026-11-24","2027-07-15"):
            self.assertTrue(in_window(day,"09",self.time(day,6)))
            self.assertTrue(in_window(day,"21",self.time(day,18)))
            self.assertFalse(in_window(day,"21",self.time(day,3)))
            self.assertFalse(in_window(day,"09",self.time(day,19)))
            self.assertFalse(in_window("2026-11-23","21",self.time(day,21)))

    def test_watchdog_uses_local_civil_time_not_utc(self):
        for day in ("2026-11-24","2027-07-15"):
            self.assertEqual(due_slot(self.time(day,9,13))[0],"09")
            self.assertEqual(due_slot(self.time(day,21,43))[0],"21")
            self.assertIsNone(due_slot(self.time(day,8,43))[0])

    def test_verified_receipt_requires_real_meta_readback(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"receipt.json"
            self.assertFalse(verified(p,"2026-11-24","09"))
            row={"date":"2026-11-24","slot":"09","verification":"pending","instagram_media_id":"12345","permalink":"https://www.instagram.com/reel/abc/"}
            p.write_text(json.dumps(row))
            self.assertFalse(verified(p,"2026-11-24","09"))
            row["verification"]="published_media_read_back"
            p.write_text(json.dumps(row))
            self.assertTrue(verified(p,"2026-11-24","09"))
            self.assertFalse(verified(p,"2026-11-24","21"))

    def test_ambiguous_intent_never_dispatches(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"docs/pending").mkdir(parents=True)
            (root/"docs/pending/2026-11-24_09.json").write_text("{}")
            with patch("scripts.publication_reliability.subprocess.run") as run:
                with self.assertRaisesRegex(RuntimeError,"AMBIGUOUS"):
                    watchdog(self.time("2026-11-24",9,13),root)
                run.assert_not_called()

    def test_missing_receipt_dispatches_exact_dated_workflow(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ",{"GITHUB_REPOSITORY":"fedry23/umbral-automation"}):
            with patch("scripts.publication_reliability.active_publisher",return_value=False), patch("scripts.publication_reliability.subprocess.run") as run:
                watchdog(self.time("2026-11-24",21,13),Path(folder))
                run.assert_called_once_with(["gh","workflow","run","publish_daily.yml","--repo","fedry23/umbral-automation","--ref","main","-f","recovery_day=2026-11-24"],check=True)

    def test_active_publisher_does_not_duplicate_and_overdue_is_error(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ",{"GITHUB_REPOSITORY":"fedry23/umbral-automation"}):
            with patch("scripts.publication_reliability.active_publisher",return_value=True), patch("scripts.publication_reliability.subprocess.run") as run:
                with self.assertRaisesRegex(RuntimeError,"OVERDUE"):
                    watchdog(self.time("2026-11-24",10,13),Path(folder))
                run.assert_not_called()
