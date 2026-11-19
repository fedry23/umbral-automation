import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from scripts import umbral3_reserve as reserve

ROOT = Path(__file__).resolve().parents[1]

class ReserveTests(unittest.TestCase):
    def setUp(self):
        self.story = json.loads((ROOT/'tests/fixtures/umbral3_stories.json').read_text(encoding='utf-8'))[0]
        self.recipe = {'model':'test-model','revision':'fixture','steps':4}
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        for i in range(6):
            Image.new('RGB',(256,384),(i*20,30,50)).save(self.folder/f'scene_{i:02}.png')
    def seal(self):
        return reserve.manifest(self.story,'2027-03-28','09',self.recipe,self.folder)
    def check(self, record, story=None, date='2027-03-28', slot='09', recipe=None):
        return reserve.verify(record,story or self.story,date,slot,recipe or self.recipe,self.folder)
    def test_number_independent(self):
        rec = self.seal()
        self.assertFalse(rec['visual_approved'])
        changed = {**self.story,'episode_number':14,'publish_date':'2027-03-28'}
        self.assertTrue(self.check(rec,changed))
        self.assertEqual(rec['scheduled_utc'],'2027-03-28T07:00:00+00:00')
    def test_stale_story_recipe_slot(self):
        rec = self.seal()
        for kwargs in ({'story':{**self.story,'caption':'changed'}},
                       {'recipe':{**self.recipe,'steps':8}}, {'slot':'21'}, {'date':'2027-03-29'}):
            with self.assertRaises(ValueError):
                self.check(rec,**kwargs)
    def test_corruption_and_duplicates(self):
        rec = self.seal()
        p = self.folder/'scene_00.png'
        Image.new('RGB',(256,384),(99,9,9)).save(p)
        with self.assertRaises(ValueError):
            self.check(rec)
        p.write_bytes((self.folder/'scene_01.png').read_bytes())
        with self.assertRaises(ValueError):
            self.seal()
        p.unlink()
        with self.assertRaises(ValueError):
            self.seal()
    def test_dst_and_horizon(self):
        for date,before,after in ((dt.datetime(2027,3,27,7,tzinfo=dt.timezone.utc),'08:00','07:00'),
                                  (dt.datetime(2027,10,30,6,tzinfo=dt.timezone.utc),'07:00','08:00')):
            result = reserve.slots(date)
            self.assertEqual(len(result),14)
            self.assertIn('T'+before+':00',result[0]['scheduled_utc'])
            self.assertIn('T'+after+':00',result[2]['scheduled_utc'])
            self.assertEqual(len({(r['date'],r['slot']) for r in result}),14)
        with self.assertRaises(ValueError):
            reserve.slots(dt.datetime(2027,1,1))
        with self.assertRaises(ValueError):
            reserve.slots(dt.datetime.now(dt.timezone.utc),8)
