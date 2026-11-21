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
    def test_refill_still_fails_closed_until_visual_gate_and_main_oidc(self):
        flow=yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                       Loader=yaml.BaseLoader)
        gate=flow["jobs"]["daily-refill"]["if"]
        self.assertIn("vars.UMBRAL3_RESERVE_ENABLED == 'true'",gate)
        self.assertIn("refs/heads/main",gate)
        self.assertIn("github.event_name == 'schedule'",gate)
