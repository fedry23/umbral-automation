"""Guard against silent GitHub schedule skips for the approved morning Reel.

No Meta writes in tests. The exact owner-initiated catch-up must not become
an unrestricted workflow dispatch or change future civil slots.
"""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]

class MissedMorningScheduleRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.load(
            (ROOT / ".github/workflows/umbral3_hf_storage.yml").read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )

    def test_verified_morning_render_can_reattempt_v31_if_scheduler_skips(self):
        trigger = self.config["on"]["workflow_run"]
        self.assertEqual(trigger["workflows"], ["UMBRAL - Generación 09:00"])
        self.assertEqual(trigger["types"], ["completed"])
        self.assertEqual(trigger["branches"], ["main"])
        for name in ("live-routing", "live-owner-approved-release"):
            gate = self.config["jobs"][name]["if"]
            self.assertIn("github.event.workflow_run.conclusion == 'success'", gate)
            self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository", gate)
            self.assertIn("github.event.workflow_run.name == 'UMBRAL - Generación 09:00'", gate)
            self.assertIn("github.event.workflow_run.event == 'schedule'", gate)
            self.assertIn("refs/heads/main", gate)

    def test_one_time_recovery_reuses_existing_meta_safe_publisher(self):
        for name in ("live-routing", "live-owner-approved-release"):
            self.assertIn(
                "github.event.head_commit.message == 'UMBRAL official catchup 2026-11-22 09'",
                self.config["jobs"][name]["if"],
            )
        publisher = self.config["jobs"]["live-owner-approved-release"]
        self.assertEqual(publisher["concurrency"]["group"], "umbral-instagram-official")
        steps = str(publisher["steps"])
        for critical in (
            "scripts/reconcile_publications.py",
            "docs/published",
            "docs/pending",
            "scripts/ensure_meta_compatible.py",
            "scripts/publish_daily.py prepare",
            "scripts/publish_daily.py publish",
        ):
            self.assertIn(critical, steps)
        slot_step = next(s["run"] for s in publisher["steps"] if s.get("name") == "Select the EXACT scheduled civil slot")
        self.assertIn("[ \"$(TZ=Europe/Madrid date +%F)\" = '2026-11-22' ]", slot_step)

        # Critical: shell must expand real date/slot variables, not literal
        # escaped $ expressions that produce bad MP4 and receipt names.
        shell_runs = "\\n".join(step.get("run", "") for step in publisher["steps"])
        self.assertNotIn(chr(92) + "${", shell_runs)
        self.assertIn('key="${key}_09"', shell_runs)
        self.assertIn('short="${UMBRAL_DAY//-/}"', shell_runs)

    def test_old_scheduled_and_private_jobs_stay_separate(self):
        workflow = self.config
        self.assertIn("42 20 * * *", [s["cron"] for s in workflow["on"]["schedule"]])
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(workflow["on"]["push"]["paths"], ["ops/umbral3-storage-kick.txt"])
        self.assertEqual(workflow["jobs"]["daily-refill"]["permissions"],
                         {"contents": "read", "id-token": "write"})

if __name__ == "__main__":
    unittest.main()
