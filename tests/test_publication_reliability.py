import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.publication_reliability import in_window, due_slot, verified, watchdog, MADRID, push_slot

class PublicationReliabilityTests(unittest.TestCase):
    def time(self, date, hour, minute=0):
        return dt.datetime.fromisoformat(f"{date}T{hour:02}:{minute:02}:00").replace(tzinfo=MADRID)

    def test_push_slot_comes_from_changed_paths_not_commit_message(self):
        self.assertEqual(push_slot(["ops/publish-morning-kick.txt"]),"09")
        self.assertEqual(push_slot(["ops/publish-kick.txt"]),"21")
        self.assertEqual(push_slot(["ops/umbral3-storage-kick.txt"]),"none")
        with self.assertRaisesRegex(ValueError,"Ambiguous"):
            push_slot(["ops/publish-morning-kick.txt","ops/publish-kick.txt"])

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

    def test_workflow_fallback_and_watchdog_keep_one_real_publisher(self):
        import yaml
        base=Path(__file__).resolve().parents[1]/".github/workflows"
        load=lambda name: yaml.load((base/name).read_text(),Loader=yaml.BaseLoader)
        live=load("umbral3_hf_storage.yml")
        fallback=live["jobs"]["live-fallback"]
        self.assertIn("needs.live-owner-approved-release.result != 'success'",fallback["if"])
        self.assertIn("needs.live-routing.outputs.slot",fallback["if"])
        self.assertIn("gh workflow run",str(fallback["steps"]))
        self.assertNotIn("IG_ACCESS_TOKEN",str(fallback))
        for name in ("publish_daily.yml","publish_morning.yml"):
            flow=load(name)
            self.assertIn("recovery_day",flow["on"]["workflow_dispatch"]["inputs"])
            job=flow["jobs"]["publicar"]
            self.assertEqual(job["concurrency"]["group"],"umbral-instagram-official")
            self.assertEqual(job["concurrency"]["queue"],"max")
            self.assertIn("needs.rollout.outputs.date",str(job["steps"]))
        watch=load("publication_watchdog.yml")
        self.assertNotIn("IG_ACCESS_TOKEN",str(watch))
        self.assertEqual(watch["permissions"]["actions"],"write")
        self.assertIn("13,43 7-9,19-21 * * *",[s["cron"] for s in watch["on"]["schedule"]])
