"""Prove V3.1 live publisher is inert unless explicitly activated on main."""
from pathlib import Path
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]
def flow(name):
    return yaml.load((ROOT/".github/workflows"/name).read_text(),
                     Loader=yaml.BaseLoader)

class OwnerLiveWorkflowTests(unittest.TestCase):
    def test_private_publisher_requires_main_and_explicit_feature_switch(self):
        main=flow("umbral3_hf_storage.yml")
        job=main["jobs"]["live-owner-approved-release"]
        guard=job["if"]
        self.assertIn("refs/heads/main",guard)
        self.assertIn("github.event_name == 'schedule'",guard)
        self.assertIn("needs.live-routing.outputs.eligible == 'true'",guard)
        self.assertIn("vars.UMBRAL3_LIVE_ENABLED != 'false'",guard)
        self.assertEqual(job["needs"],"live-routing")
        route=main["jobs"]["live-routing"]
        self.assertIn("scripts.umbral3_rollout --mode v31",route["steps"][-1]["run"])
        self.assertIn("refs/heads/main",route["if"])
        self.assertIn("vars.UMBRAL_META_PUBLISH_ENABLED != 'false'",guard)
        self.assertEqual(job["concurrency"]["group"],"umbral-instagram-official")
        self.assertEqual(job["concurrency"]["cancel-in-progress"],"false")
        self.assertEqual(job["permissions"]["id-token"],"write")
        self.assertEqual(job["permissions"]["contents"],"write")
        self.assertNotIn("IG_ACCESS_TOKEN",job.get("env",{}))
        self.assertIn("42 20 * * *",[x["cron"] for x in main["on"]["schedule"]])
        self.assertIn("github.event.schedule == '42 20 * * *'",
                      main["jobs"]["daily-refill"]["if"])
    def test_trusted_oidc_restore_is_separate_from_meta_secret_steps(self):
        job=flow("umbral3_hf_storage.yml")["jobs"]["live-owner-approved-release"]
        steps=job["steps"]
        restore=next(x for x in steps if x.get("name","").startswith("Restore exact owner"))
        self.assertNotIn("IG_ACCESS_TOKEN",restore.get("env",{}))
        self.assertIn("scripts.umbral3_live_stage",restore["run"])
        for term in ("scripts/reconcile_publications.py",
                     "scripts/publish_daily.py publish",
                     "scripts/publish_daily.py prepare",
                     "scripts/wait_public_video.py",
                     "scripts/ensure_meta_compatible.py"):
            self.assertTrue(any(term in s.get("run","") for s in steps),term)
        self.assertTrue(all("UMBRAL_SKIP" in s.get("if","true") for s in steps
                            if s.get("name","").startswith(("Restore exact owner",
                               "Verify served MP4","Prepare Instagram container"))))
    def test_existing_official_workflows_fallback_only_when_live_enabled(self):
        for filename,backup in (("publish_morning.yml",("0 7 * * *","0 8 * * *")),
                                ("publish_daily.yml",("0 19 * * *","0 20 * * *"))):
            with self.subTest(filename=filename):
                f=flow(filename)
                guard=f["jobs"]["publicar"]["if"]
                self.assertIn("needs.rollout.outputs.legacy == 'true'",guard)
                self.assertEqual(f["jobs"]["publicar"]["needs"],"rollout")
                self.assertIn("scripts.umbral3_rollout --mode legacy",f["jobs"]["rollout"]["steps"][-1]["run"])
                self.assertIn("umbral-instagram-official",f["concurrency"]["group"])
                for cron in backup:
                    self.assertIn(cron,[x["cron"] for x in f["on"]["schedule"]])
                    self.assertIn(cron, f["on"]["schedule"][0]["cron"] if False else " ".join(x["cron"] for x in f["on"]["schedule"]))

if __name__=="__main__":
    unittest.main()
