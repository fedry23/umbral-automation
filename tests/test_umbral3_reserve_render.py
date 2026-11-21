"""Regression contracts for fourteen independently numbered private candidates."""
import datetime as dt
import unittest
from unittest.mock import patch
from scripts.umbral3_reserve_render import load_slot, catalogs
from scripts.umbral3_hf_persist_candidate import FILENAME

class CandidateSelectionTests(unittest.TestCase):
    def test_all_fourteen_slots_are_valid_without_preallocating_numbers(self):
        entries=catalogs()
        anchor=dt.date(2026,11,21)
        pairs=[]
        for index in range(14):
            story,day,slot=load_slot(index,anchor,entries)
            self.assertTrue(story["storyboard"]["shots"])
            self.assertEqual(len(story["scenes"]),6)
            self.assertEqual(slot,"09" if index%2==0 else "21")
            self.assertEqual(day,(anchor+dt.timedelta(days=index//2)).isoformat())
            self.assertNotIn("episode_number",story)
            pairs.append((day,slot,story["title"]))
        self.assertEqual(len(set(pairs)),14)
    def test_invalid_indices_are_rejected(self):
        for value in (-1,14,True,"0",None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                load_slot(value,dt.date(2026,11,21),catalogs())
    def test_wrong_day_and_duplicate_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"missing"):
            load_slot(0,dt.date(2028,1,1),catalogs())
        data=catalogs()
        data["09"].append(dict(data["09"][-1]))
        with self.assertRaisesRegex(ValueError,"(Ambiguous|Duplicate)"):
            load_slot(12,dt.date(2026,11,21),data)
    def test_archive_filename_is_not_a_path_or_official_name(self):
        for name in ("candidate-2026-11-21-09.mp4",
                     "candidate-2026-11-27-21.mp4"):
            self.assertIsNotNone(FILENAME.fullmatch(name))
        for name in ("../candidate-2026-11-21-09.mp4",
                     "umbral_20261121_09.mp4",
                     "candidate-2026-11-21-09.mkv",
                     "candidate-2026-11-21-12.mp4"):
            self.assertIsNone(FILENAME.fullmatch(name))
