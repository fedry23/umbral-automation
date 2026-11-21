import unittest
from unittest.mock import patch
from scripts.umbral3_private_render import load_fixture

class PrivateFixtureTests(unittest.TestCase):
    def test_isolated_numbers_and_no_dates(self):
        for i in range(3):
            s = load_fixture(i)
            self.assertEqual(s['episode_number'], 9001+i)
            self.assertNotIn('publish_date', s)
    def test_full_media_path_is_resolved_before_renderer(self):
        # A scoped pathlib import previously shadowed Path and crashed here.
        class Stopped(Exception):
            pass
        from scripts.umbral3_private_render import run_fixture
        with patch("scripts.umbral3_private_render.render.render_story_media",
                   side_effect=Stopped):
            with self.assertRaises(Stopped):
                run_fixture(0, storage_python="/tmp/placeholder/python")

    def test_invalid_selection(self):
        for i in (-1,3,True,'0'):
            with self.assertRaises(ValueError):
                load_fixture(i)
