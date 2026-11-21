"""Regression for owner-selected V3 visual repair: never rewrite good scenes."""
import datetime as dt
import unittest

from scripts.umbral3_selective_plan import (
    OLD_BACKEND, NEW_BACKEND, PRIORITY, TITLE_AND_SHOTS, selection, backend_for,
)


class SelectivePlanTests(unittest.TestCase):
    def test_every_story_is_explicitly_curated_and_byte_reuse_is_possible(self):
        self.assertEqual(set(TITLE_AND_SHOTS), set(range(14)))
        self.assertEqual(len(PRIORITY), 7)
        for index in range(14):
            story,day,slot,indices=selection(index,dt.date(2026,11,21))
            self.assertEqual(story["title"],TITLE_AND_SHOTS[index][0])
            self.assertEqual(day,(dt.date(2026,11,21)+dt.timedelta(days=index//2)).isoformat())
            self.assertEqual(slot,"09" if index%2==0 else "21")
            self.assertEqual(len(indices),len(set(indices)))
            self.assertTrue(indices)
            if index != 12:
                self.assertLess(len(indices),6)
            self.assertEqual(backend_for(index,priority_only=True),
                             NEW_BACKEND if index in PRIORITY else OLD_BACKEND)

    def test_reject_wrong_input_and_unreviewed_story(self):
        for bad in (-1,14,"0",True):
            with self.assertRaises(ValueError):
                selection(bad,dt.date(2026,11,21))
        with self.assertRaises(ValueError):
            selection(0,dt.date(2026,11,22))
