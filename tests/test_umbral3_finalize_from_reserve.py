"""Late-bound reels use verified images and confirmed dynamic numbering only."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from scripts.umbral3_reserve import _assets,story_key
from scripts.umbral3_finalize_from_reserve import finalize

REPO=Path(__file__).resolve().parents[1]

class FinalizationTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.media=self.root/"staged"
        self.media.mkdir()
        (self.root/"docs"/"published").mkdir(parents=True)
        fixture=json.loads((REPO/"tests/fixtures/umbral3_stories.json").read_text())[0]
        self.story={**fixture,"publish_date":"2027-03-28"}
        (self.root/"stories_morning.json").write_text(json.dumps([self.story]))
        (self.root/"stories.json").write_text("[]")
        for i in range(6):
            Image.new("RGB",(256,384),(i*10+10,i*17+5,90)).save(
                self.media/f"scene_{i:02}.png")
        self.record={"version":1,"kind":"umbral3-scene-handoff","date":"2027-03-28",
                     "slot":"09","story_sha256":story_key(self.story),
                     "assets":_assets(self.media,6),"visual_approved":False}
        (self.media/"visuals_manifest.json").write_text(json.dumps(self.record))
    def fake(self,story,out,date,filename,**kwargs):
        self.assertEqual(story["episode_number"],11)
        self.assertEqual(kwargs["reserve_slot"],"09")
        self.assertEqual(kwargs["prepared_images"],self.record)
        (out/filename).write_bytes(b"x"*100001)
        (out/"story_used.json").write_text(json.dumps(story))
        return out/filename
    def test_private_finalize_renumbers_without_regenerating_images(self):
        with patch("render.render_story_media",side_effect=self.fake),patch(
            "scripts.umbral3_finalize_from_reserve.subprocess.run"
        ) as mocked:
            result=finalize("2027-03-28","09",self.media,root=self.root,private_test=True)
        self.assertEqual(result["episode_number"],11)
        self.assertFalse(result["ready_to_publish"])
        self.assertEqual(result["video_bytes"],100001)
        mocked.assert_called_once()
    def test_live_finalization_refuses_unapproved_private_assets(self):
        with self.assertRaises(RuntimeError):
            finalize("2027-03-28","09",self.media,root=self.root)
    def test_existing_receipt_blocks_republication(self):
        (self.root/"docs"/"published"/"2027-03-28_09.json").write_text('{"date":"2027-03-28"}')
        with self.assertRaisesRegex(RuntimeError,"publication receipt"):
            finalize("2027-03-28","09",self.media,root=self.root,private_test=True)
    def test_edited_frame_blocks_finalization(self):
        (self.media/"scene_01.png").write_bytes(b"corrupt")
        with self.assertRaises((ValueError,OSError)):
            finalize("2027-03-28","09",self.media,root=self.root,private_test=True)
    def test_stale_episode_number_blocks(self):
        with self.assertRaisesRegex(ValueError,"Official episode number moved"):
            finalize("2027-03-28","09",self.media,number=15,root=self.root,private_test=True)
