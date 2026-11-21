"""Reversible live/legacy producer selection and seven-day owner review window."""
import datetime as dt
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.umbral3_rollout import eligible, route_legacy, permit_private_refill, read_config

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Europe/Madrid")


class RolloutTests(unittest.TestCase):
    def now(self, day):
        return dt.datetime.fromisoformat(day + "T07:00:00").replace(tzinfo=TZ)

    def test_exact_owner_approved_media_eligible_only_for_today(self):
        for day, slot in (("2026-11-22", "09"), ("2026-11-22", "21"),
                          ("2026-11-25", "09"), ("2026-11-27", "21")):
            with self.subTest(day=day, slot=slot):
                self.assertTrue(eligible(day,slot,ROOT,self.now(day),override=""))
                self.assertFalse(eligible(day,slot,ROOT,self.now("2026-11-21"),override=""))
                self.assertFalse(eligible(day,slot,ROOT,self.now(day),override="false"))

    def test_no_unreviewed_future_or_historical_route(self):
        for day in ("2026-11-21", "2026-11-28", "2026-11-29"):
            with self.subTest(day=day):
                self.assertFalse(eligible(day,"09",ROOT,self.now(day),override=""))
                self.assertTrue(route_legacy(day,"09","schedule","17 5 * * *",ROOT,self.now(day),override=""))

    def test_legacy_skips_approved_primary_but_keeps_both_backups(self):
        for slot, primary, backup in (
            ("09", "17 5 * * *",("0 7 * * *","0 8 * * *")),
            ("21", "17 17 * * *",("0 19 * * *","0 20 * * *")),
        ):
            day="2026-11-22"
            with self.subTest(slot=slot):
                self.assertFalse(route_legacy(day,slot,"schedule",primary,ROOT,self.now(day),override=""))
                self.assertFalse(route_legacy(day,slot,"push","",ROOT,self.now(day),override=""))
                for cron in backup:
                    self.assertTrue(route_legacy(day,slot,"schedule",cron,ROOT,self.now(day),override=""))

    def test_legacy_primary_recovers_if_release_file_is_missing_or_bad(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "Missing trusted"):
                read_config(tmp)
            self.assertFalse(eligible("2026-11-22","09",tmp,self.now("2026-11-22"),override=""))
            self.assertTrue(route_legacy("2026-11-22","09","schedule","17 5 * * *",
                                         tmp,self.now("2026-11-22"),override=""))

    def test_emergency_stop_restores_legacy_but_never_enables_v31(self):
        day="2026-11-23"
        self.assertFalse(eligible(day,"21",ROOT,self.now(day),override="false"))
        self.assertTrue(route_legacy(day,"21","schedule","17 17 * * *",ROOT,self.now(day),override="false"))
        self.assertFalse(permit_private_refill(ROOT,override="false"))
        self.assertTrue(permit_private_refill(ROOT,override=""))

    def test_config_has_explicit_owner_and_bounded_rollout(self):
        row=read_config(ROOT)
        self.assertEqual(row["owner"],"fedry23")
        self.assertEqual(row["first_date"],"2026-11-22")
        self.assertEqual(row["last_date"],"2026-11-27")
        self.assertEqual(row["future_unreviewed_policy"],"legacy-fallback")

    def test_corrupt_or_disabled_rollout_never_suppresses_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"docs"
            p.mkdir()
            target=p/"umbral3-production-rollout.json"
            row=read_config(ROOT)
            row["enabled"]=False
            target.write_text(json.dumps(row),encoding="utf-8")
            self.assertFalse(eligible("2026-11-22","09",tmp,self.now("2026-11-22"),override=""))
            row["enabled"]=True
            row["owner"]="unknown"
            target.write_text(json.dumps(row),encoding="utf-8")
            self.assertFalse(eligible("2026-11-22","09",tmp,self.now("2026-11-22"),override=""))

if __name__ == "__main__":
    unittest.main()
