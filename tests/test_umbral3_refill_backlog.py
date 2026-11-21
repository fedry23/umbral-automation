"""Backfill broken private reserve days before preparing a newer D+7 tail.

No model, Meta, public media, OIDC or network is required in these tests.
"""
import datetime as dt
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
import yaml

from scripts.umbral3_refill_gate import recover_backlog

ROOT = Path(__file__).resolve().parents[1]
TODAY = dt.date(2026, 11, 21)


class RefillBacklogTests(unittest.TestCase):
    def checker(self, missing_targets=()):
        visited=[]
        def fake(store, past, slot, all_stories=None):
            target=past+dt.timedelta(days=7)
            visited.append((target,slot))
            missing=target in missing_targets
            return {"date":target.isoformat(),"anchor":target.isoformat(),
                    "slot":slot,"index":0 if slot=="09" else 1,
                    "generate":missing,"ready_to_publish":False,
                    "stored_full_candidate":not missing}
        return visited,fake

    def test_first_failed_backlog_date_is_selected_before_new_tail(self):
        visited,fake=self.checker({dt.date(2026,11,24),dt.date(2026,11,28)})
        with patch("scripts.umbral3_refill_gate.check",side_effect=fake):
            row=recover_backlog(Mock(),TODAY,"09")
        self.assertEqual(row["date"],"2026-11-24")
        self.assertTrue(row["generate"])
        self.assertTrue(row["recovered_backlog"])
        self.assertEqual(row["checked_future_dates"],3)
        self.assertEqual([d.isoformat() for d,s in visited],
                         ["2026-11-22","2026-11-23","2026-11-24"])
        self.assertFalse(row["ready_to_publish"])

    def test_if_no_holes_only_the_new_d7_tail_is_generated(self):
        visited,fake=self.checker({dt.date(2026,11,28)})
        with patch("scripts.umbral3_refill_gate.check",side_effect=fake):
            row=recover_backlog(Mock(),TODAY,"21")
        self.assertEqual(row["date"],"2026-11-28")
        self.assertEqual(row["index"],1)
        self.assertEqual(row["checked_future_dates"],7)
        self.assertFalse(row["recovered_backlog"])
        self.assertTrue(row["generate"])
        self.assertEqual(len(visited),7)

    def test_fully_indexed_next_seven_days_never_renders(self):
        visited,fake=self.checker()
        with patch("scripts.umbral3_refill_gate.check",side_effect=fake):
            row=recover_backlog(Mock(),TODAY,"09")
        self.assertFalse(row["generate"])
        self.assertFalse(row["ready_to_publish"])
        self.assertTrue(row["all_slots_complete"])
        self.assertEqual(row["checked_future_dates"],7)
        self.assertEqual(len(visited),7)

    def test_corruption_fails_closed_without_moving_to_later_slot(self):
        visited=[]
        def corrupt(store,past,slot,all_stories=None):
            visited.append(past)
            raise RuntimeError("Corrupt existing ZIP")
        with patch("scripts.umbral3_refill_gate.check",side_effect=corrupt):
            with self.assertRaisesRegex(RuntimeError,"Corrupt existing"):
                recover_backlog(Mock(),TODAY,"09")
        self.assertEqual(len(visited),1)

    def test_invalid_dates_and_slots_rejected(self):
        for invalid in (None, "2026-11-21", dt.datetime(2026,11,21),True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                recover_backlog(Mock(),invalid,"09")
        with self.assertRaises(ValueError):
            recover_backlog(Mock(),TODAY,"18")

    def test_recovering_main_workflow_uses_exact_post_generation_verification(self):
        flow=yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                       Loader=yaml.BaseLoader)
        job=flow["jobs"]["daily-refill"]
        self.assertIn("refs/heads/main",job["if"])
        self.assertIn("vars.UMBRAL3_RESERVE_ENABLED == 'true'",job["if"])
        self.assertEqual(job["permissions"],{"contents":"read","id-token":"write"})
        steps=job["steps"]
        gate=next(s for s in steps if s.get("id")=="gate")["run"]
        self.assertIn("--recover-backlog --slot",gate)
        self.assertNotIn("IG_ACCESS_TOKEN",job.get("env",{}))
        exact=next(s for s in steps if s.get("name","").startswith("Verify the EXACT"))
        self.assertIn("--index",exact["run"])
        self.assertIn("steps.gate.outputs.index",exact["run"])
        self.assertIn("steps.gate.outputs.anchor",exact["run"])
        self.assertNotIn("--recover-backlog",exact["run"])
