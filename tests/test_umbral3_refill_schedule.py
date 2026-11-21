"""D+7 private reserve refill must follow editorial preparation across DST."""
import datetime as dt
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo
import yaml

ROOT=Path(__file__).resolve().parents[1]
MADRID=ZoneInfo("Europe/Madrid")

class RefillScheduleTests(unittest.TestCase):
    def test_refill_after_editorial_and_both_official_slots_winter_and_summer(self):
        flow=yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                       Loader=yaml.BaseLoader)
        self.assertEqual(flow["on"]["schedule"],[{"cron":"42 20 * * *"}])
        for date in (dt.date(2026,11,21),dt.date(2027,7,15)):
            with self.subTest(date=date):
                run=dt.datetime(date.year,date.month,date.day,20,42,
                                tzinfo=dt.timezone.utc).astimezone(MADRID)
                self.assertEqual(run.date(),date)
                self.assertGreater((run.hour,run.minute),(21,20))
                self.assertLess((run.hour,run.minute),(24,0))
                self.assertGreater((run.hour,run.minute),(18,20))
    def test_new_refill_selects_v3_without_auto_publication(self):
        """D+7 must select the V3 artifact namespace and retain the release switch."""
        from scripts.umbral3_refill_gate import BACKEND
        self.assertEqual(BACKEND, 'sdxl-lightning-2steps-ov-int8-horror-v3')
        flow = yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                         Loader=yaml.BaseLoader)
        job = flow["jobs"]["daily-refill"]
        self.assertEqual(job["env"]["UMBRAL_HORROR_DIRECTION"], "horror-v3")
        self.assertIn("vars.UMBRAL3_RESERVE_ENABLED == 'true'", job["if"])
        self.assertNotIn("IG_ACCESS_TOKEN", job.get("env", {}))

    def test_private_full_batch_is_reachable_by_kick_file(self):
        flow=yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                       Loader=yaml.BaseLoader)
        self.assertIn("ops/umbral3-lightning-kick.txt",flow["on"]["push"]["paths"])
        self.assertIn("UMBRAL lightning private full",
                      flow["jobs"]["lightning-batch"]["if"])
        self.assertIn("refs/heads/integration/umbral-3",
                      flow["jobs"]["lightning-batch"]["if"])

    def test_private_v3_batch_reuses_archives_and_avoids_meta(self):
        flow=yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                       Loader=yaml.BaseLoader)
        for key in ("lightning-smoke","lightning-batch"):
            job=flow["jobs"][key]
            self.assertEqual(job["env"]["UMBRAL_HORROR_DIRECTION"],"horror-v3")
            self.assertIn("integration/umbral-3",job["if"])
            self.assertEqual(job["permissions"]["contents"],"read")
            self.assertEqual(job["permissions"]["id-token"],"write")
            self.assertNotIn("IG_ACCESS_TOKEN",job.get("env",{}))
            steps=job["steps"]
            gate=next(s for s in steps if s.get("id")=="v3-gate")
            self.assertIn("--index",gate["run"])
            self.assertIn("--anchor 2026-11-21",gate["run"])
            for step in steps:
                if "Install pinned accelerated" in step.get("name","") or "Generate six" in step.get("name","") or "Assemble full Reel" in step.get("name",""):
                    self.assertEqual(step["if"],"steps.v3-gate.outputs.generate == 'true'")
        inv=flow["jobs"]["candidate-inventory"]["steps"][-1]["run"]
        self.assertIn("--backend sdxl-lightning-2steps-ov-int8-horror-v3",inv)

    def test_refill_still_fails_closed_until_visual_gate_and_main_oidc(self):
        flow=yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                       Loader=yaml.BaseLoader)
        gate=flow["jobs"]["daily-refill"]["if"]
        self.assertIn("vars.UMBRAL3_RESERVE_ENABLED == 'true'",gate)
        self.assertIn("refs/heads/main",gate)
        self.assertIn("github.event_name == 'schedule'",gate)
