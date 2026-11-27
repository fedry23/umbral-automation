import json
import unittest
from pathlib import Path
from copy import deepcopy
from scripts.cinematic5 import validate, validate_timing

ROOT=Path(__file__).resolve().parents[1]
STORIES=json.loads((ROOT/"cinematic5"/"pilots.json").read_text())

class Cinematic5Test(unittest.TestCase):
    def test_pilots(self):
        for story in STORIES:
            with self.subTest(story=story["title"]):
                self.assertEqual(len(validate(story)),5)
    def test_no_production_date(self):
        s=deepcopy(STORIES[0]); s["publish_date"]="2026-11-28"
        with self.assertRaises(ValueError): validate(s)
    def test_hook_first(self):
        s=deepcopy(STORIES[0]); s["hook"]="Otro gancho."
        with self.assertRaises(ValueError): validate(s)
    def test_missing_metadata(self):
        s=deepcopy(STORIES[0]); del s["storyboard"]["shots"][0]["lighting"]
        with self.assertRaises(ValueError): validate(s)
    def test_timing(self):
        validate_timing([(0.1,2,"hook")],30)
        for cues, duration in [([(1,2,"hook")],30), ([(0,2,"hook")],70), ([],30), ([(0,40,"hook")],30)]:
            with self.assertRaises(ValueError): validate_timing(cues,duration)
    def test_internal_markers(self):
        s=deepcopy(STORIES[0]); s["caption"]="PRUEBA de producción"
        with self.assertRaises(ValueError): validate(s)
