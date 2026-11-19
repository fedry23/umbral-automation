import unittest
from scripts.umbral3_private_render import load_fixture

class PrivateFixtureTests(unittest.TestCase):
    def test_isolated_numbers_and_no_dates(self):
        for i in range(3):
            s = load_fixture(i)
            self.assertEqual(s['episode_number'], 9001+i)
            self.assertNotIn('publish_date', s)
    def test_invalid_selection(self):
        for i in (-1,3,True,'0'):
            with self.assertRaises(ValueError):
                load_fixture(i)
