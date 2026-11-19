import json
import unittest
from pathlib import Path
import render
from audio_engine import speech_units
from scripts.storyboard import validate_storyboard, shot_boundaries
ROOT = Path(__file__).resolve().parents[1]

class Umbral3EditorialFixtures(unittest.TestCase):
    def test_storyboards_and_real_subtitle_segmentation(self):
        stories = json.loads((ROOT / 'tests/fixtures/umbral3_stories.json').read_text(encoding='utf-8'))
        self.assertEqual(len(stories), 3)
        self.assertEqual(len({s['title'] for s in stories}), 3)
        for story in stories:
            with self.subTest(title=story['title']):
                self.assertNotIn('publish_date', story)
                self.assertTrue(140 <= len(story['narration'].split()) <= 170)
                shots = validate_storyboard(story)
                self.assertEqual(len(shots), 6)
                self.assertEqual(render.visual_shots(story), story['scenes'])
                phrases = [p for unit in speech_units(story['narration']) for p in render.phrases(unit)]
                cues = [(2+i*1.1, 3+i*1.1, p) for i,p in enumerate(phrases)]
                boundaries = shot_boundaries(shots, cues, {'intro_end':2, 'outro_start':3+len(phrases)*1.1})
                self.assertEqual(len(boundaries), 7)
                self.assertTrue(all(a < b for a,b in zip(boundaries, boundaries[1:])))

    def test_fixtures_not_in_official_catalogs(self):
        fixtures = json.loads((ROOT / 'tests/fixtures/umbral3_stories.json').read_text(encoding='utf-8'))
        for path in ('stories.json','stories_morning.json','stories.archive.json'):
            catalog = json.loads((ROOT/path).read_text(encoding='utf-8'))
            self.assertFalse({s['title'] for s in fixtures} & {s['title'] for s in catalog})
