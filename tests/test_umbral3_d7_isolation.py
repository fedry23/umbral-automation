"""Release-critical regressions: heavy D+7 queue must not block official Meta slot."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class D7IsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.load(
            (ROOT / ".github/workflows/umbral3_hf_storage.yml").read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )

    def test_private_reserve_and_official_publication_use_distinct_workflow_locks(self):
        group = self.workflow["concurrency"]["group"]
        self.assertIn("github.event.schedule", group)
        self.assertIn("42 20 * * *", group)
        self.assertIn("umbral3-private-bucket", group)
        self.assertIn("umbral3-official-schedule", group)
        self.assertNotEqual("umbral3-private-bucket", "umbral3-official-schedule")
        live = self.workflow["jobs"]["live-owner-approved-release"]
        self.assertEqual(live["concurrency"]["group"], "umbral-instagram-official")
        for workflow in ("publish_morning.yml", "publish_daily.yml"):
            fallback = yaml.load(
                (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8"),
                Loader=yaml.BaseLoader,
            )
            self.assertEqual(fallback["concurrency"]["group"], "umbral-instagram-official")

    def test_one_off_actual_refill_is_private_and_never_uses_meta_credentials(self):
        job = self.workflow["jobs"]["integration-nextweek-refill-smoke"]
        self.assertEqual(job["needs"], "verify")
        self.assertIn("refs/heads/integration/umbral-3", job["if"])
        self.assertIn("github.event_name == 'push'", job["if"])
        self.assertEqual(job["permissions"], {"contents": "read", "id-token": "write"})
        self.assertEqual(job["env"]["UMBRAL_HORROR_DIRECTION"], "horror-v3")
        self.assertNotIn("IG_ACCESS_TOKEN", job.get("env", {}))
        script = "\n".join(s.get("run", "") for s in job["steps"])
        self.assertIn("--today 2026-11-21 --slot 09", script)
        self.assertIn("--single", script)
        self.assertIn("stored_full_candidate", script)
        self.assertIn("ready_to_publish", script)
        self.assertNotIn("publish_daily.py", script)
        self.assertNotIn("IG_ACCESS_TOKEN", script)
        self.assertNotIn("graph.facebook.com", script)
        self.assertNotIn("docs/published", script)

    def test_main_refill_stays_off_until_explicit_release(self):
        refill = self.workflow["jobs"]["daily-refill"]
        self.assertIn("vars.UMBRAL3_RESERVE_ENABLED != 'false'", refill["if"])
        self.assertIn("refs/heads/main", refill["if"])
        self.assertIn("42 20 * * *", refill["if"])


    def test_two_different_d7_private_jobs_cover_both_civil_slots(self):
        jobs = self.workflow["jobs"]
        first = jobs["integration-nextweek-refill-smoke"]
        second = jobs["integration-nextweek-refill-evening-smoke"]
        self.assertIn("2026-11-28 09", first["if"])
        self.assertIn("2026-11-28 21", second["if"])
        for slot, job in (("09", first), ("21", second)):
            self.assertEqual(job["permissions"], {"contents": "read", "id-token": "write"})
            script = "\n".join(s.get("run", "") for s in job["steps"])
            self.assertIn("--slot " + slot, script)
            self.assertIn("--single", script)
            self.assertIn("stored_full_candidate", script)
            self.assertIn("ready_to_publish", script)
            self.assertNotIn("IG_ACCESS_TOKEN", script)
            self.assertNotIn("publish_daily.py", script)
        self.assertNotEqual(first["if"], second["if"])

    def test_nextweek_pair_exists_without_fabricating_owner_signoff(self):
        import datetime as dt
        import json
        from zoneinfo import ZoneInfo
        from scripts.storyboard import validate_storyboard
        from scripts.umbral3_reserve import story_key
        from scripts.umbral3_release_policy import approved_slot
        day = "2026-11-28"
        ids = set()
        for slot, filename in (("09", "stories_morning.json"), ("21", "stories.json")):
            stories = json.loads((ROOT / filename).read_text(encoding="utf-8"))
            selected = [s for s in stories if s.get("publish_date") == day]
            self.assertEqual(len(selected), 1, f"Expected one D+7 story for {slot}")
            story = selected[0]
            self.assertEqual(len(validate_storyboard(story)), 6)
            self.assertTrue(140 <= len(story["narration"].split()) <= 170)
            self.assertNotIn("episode_number", story)
            ids.add(story_key(story))
            with self.assertRaisesRegex(RuntimeError, "No exact owner-approved artwork"):
                approved_slot(day, slot, ROOT, dt.datetime(2026, 11, 21, 22, 0,
                              tzinfo=ZoneInfo("Europe/Madrid")))
        self.assertEqual(len(ids), 2)
