"""Future editorial continuity cannot contain unused visual identity anchors."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
class FutureStoryboardReferenceTests(unittest.TestCase):
    def test_future_dated_stories_use_every_continuity_anchor(self):
        found=0
        for file in ("stories_morning.json","stories.json"):
            for story in json.loads((ROOT/file).read_text(encoding="utf-8")):
                if story.get("publish_date","") < "2026-11-28":
                    continue
                board=story.get("storyboard")
                if not isinstance(board,dict):
                    self.fail(f"Missing future storyboard: {story.get('title')}")
                anchors=board.get("continuity",{})
                shots=board.get("shots",[])
                self.assertEqual(len(shots),6)
                self.assertTrue(anchors)
                used=set()
                for shot in shots:
                    used.update(shot.get("references",[]))
                self.assertEqual(used,set(anchors),f"Unused/missing identity anchor: {story.get('title')}")
                found+=1
        self.assertGreaterEqual(found,2)
