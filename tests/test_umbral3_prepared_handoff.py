"""SHA-256 late-binding handoff rejects stale or corrupt visual input."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from scripts.umbral3_reserve import (
    _assets,story_key,validated_prepared_images,
)

ROOT=Path(__file__).resolve().parents[1]

class PreparedSceneHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.story=json.loads((ROOT/"tests/fixtures/umbral3_stories.json").read_text())[0]
        self.story.pop("technical_profile",None)
        for i in range(6):
            Image.new("RGB",(256,384),(20+i*11,50+i*5,90+i*3)).save(
                self.root/f"scene_{i:02}.png")
        self.record={
            "version":1, "kind":"umbral3-scene-handoff",
            "date":"2027-03-28","slot":"09",
            "story_sha256":story_key(self.story),
            "assets":_assets(self.root,6),
            "visual_approved":False,
        }
    def check(self,record=None,story=None,day="2027-03-28",slot="09"):
        return validated_prepared_images(record or self.record,story or self.story,day,slot,self.root)
    def test_reuse_number_and_audio_profile_independently(self):
        a=self.check()
        b=self.check(story={**self.story, "episode_number":456,
                            "technical_profile":{"experiment":"music-balance-v1","arm":"control","music_gain":1.0}})
        self.assertEqual(a,b)
        self.assertEqual(len(a),6)
    def test_reject_stale_story_civil_slot_and_tamper(self):
        for day,slot in (("2027-03-29","09"),("2027-03-28","21")):
            with self.assertRaisesRegex(ValueError,"another story"):
                self.check(day=day,slot=slot)
        story={**self.story,"title":self.story["title"]+" changed"}
        with self.assertRaisesRegex(ValueError,"another story"):
            self.check(story=story)
        (self.root/"scene_03.png").write_bytes(b"malicious")
        with self.assertRaises((ValueError,OSError)):
            self.check()
    def test_never_accepts_unsigned_metadata(self):
        record=copy.deepcopy(self.record)
        record.pop("assets")
        with self.assertRaises(ValueError):
            self.check(record=record)
        record=copy.deepcopy(self.record)
        record["visual_approved"]="true"
        with self.assertRaises(ValueError):
            self.check(record=record)
