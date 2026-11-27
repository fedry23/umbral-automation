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
    @classmethod
    def setUpClass(cls):
        """Snapshot the 21-Nov review board before 22-Nov live receipts existed.

        Policy tests must never change meaning as real Reels are published.
        Keep immutable reviews and stories; isolate only publication state.
        """
        cls._archive = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._archive.cleanup)
        snapshot = Path(cls._archive.name)
        for filename in ("stories.json", "stories_morning.json"):
            shutil.copy2(ROOT / filename, snapshot / filename)
        docs = snapshot / "docs"
        docs.mkdir()
        for filename in ("umbral3-owner-visual-signoff-2026-11-21.json",
                         "umbral3-production-rollout.json", "umbral3-automatic-qa.json"):
            shutil.copy2(ROOT / "docs" / filename, docs / filename)
        shutil.copytree(ROOT / "docs" / "visual_approvals", docs / "visual_approvals")
        published = docs / "published"
        published.mkdir()
        (docs / "pending").mkdir()
        for receipt in (ROOT / "docs" / "published").glob("*.json"):
            if receipt.stem[:10] <= "2026-11-21":
                shutil.copy2(receipt, published / receipt.name)
        cls.history = snapshot

    def now(self, day):
        return dt.datetime.fromisoformat(day + "T07:00:00").replace(tzinfo=TZ)

    def test_exact_owner_approved_media_eligible_only_for_today(self):
        for day, slot in (("2026-11-22", "09"), ("2026-11-22", "21"),
                          ("2026-11-25", "09"), ("2026-11-27", "21")):
            with self.subTest(day=day, slot=slot):
                self.assertTrue(eligible(day,slot,self.history,self.now(day),override=""))
                self.assertFalse(eligible(day,slot,ROOT,self.now("2026-11-21"),override=""))
                self.assertFalse(eligible(day,slot,ROOT,self.now(day),override="false"))

    def test_future_requires_actual_private_machine_evidence_not_just_owner_consent(self):
        from scripts.umbral3_rollout import read_auto_policy, machine_eligible
        self.assertTrue(read_auto_policy(ROOT,override=""))
        self.assertFalse(read_auto_policy(ROOT,override="false"))
        day="2026-11-28"
        with patch("scripts.umbral3_rollout.cinematic_selected",return_value=False), patch("scripts.umbral3_rollout.machine_eligible",return_value=False):
            self.assertFalse(eligible(day,"09",ROOT,self.now(day),override=""))
        with patch("scripts.umbral3_rollout.cinematic_selected",return_value=False), patch("scripts.umbral3_rollout.machine_eligible",return_value=True):
            self.assertTrue(eligible(day,"09",ROOT,self.now(day),override=""))
        self.assertFalse(machine_eligible(day,"09",ROOT,checker=lambda *_:False,override=""))
        self.assertTrue(machine_eligible(day,"09",ROOT,checker=lambda *_:True,override=""))
        self.assertFalse(machine_eligible(day,"09",ROOT,checker=lambda *_:True,override="false"))

    def test_future_routing_yields_primary_but_legacy_backups_remain_independent(self):
        for day in ("2026-11-28", "2026-11-29"):
            with self.subTest(day=day):
                with patch("scripts.umbral3_rollout.cinematic_selected",return_value=False):
                    self.assertFalse(route_legacy(day,"09","schedule","17 5 * * *",ROOT,self.now(day),override=""))
                self.assertTrue(route_legacy(day,"09","schedule","0 7 * * *",ROOT,self.now(day),override=""))
                self.assertTrue(route_legacy(day,"09","schedule","17 5 * * *",ROOT,self.now(day),override="false"))
                with patch.dict("os.environ",{"UMBRAL3_AUTO_QA_ENABLED":"false"}):
                    self.assertTrue(route_legacy(day,"09","schedule","17 5 * * *",ROOT,self.now(day),override=""))
        self.assertTrue(route_legacy("2026-11-21","09","schedule","17 5 * * *",ROOT,self.now("2026-11-21"),override=""))

    def test_legacy_skips_approved_primary_but_keeps_both_backups(self):
        for slot, primary, backup in (
            ("09", "17 5 * * *",("0 7 * * *","0 8 * * *")),
            ("21", "17 17 * * *",("0 19 * * *","0 20 * * *")),
        ):
            day="2026-11-22"
            with self.subTest(slot=slot):
                self.assertFalse(route_legacy(day,slot,"schedule",primary,self.history,self.now(day),override=""))
                self.assertFalse(route_legacy(day,slot,"push","",self.history,self.now(day),override=""))
                for cron in backup:
                    self.assertTrue(route_legacy(day,slot,"schedule",cron,self.history,self.now(day),override=""))

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
