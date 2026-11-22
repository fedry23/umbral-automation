"""Horror V2 requires frightening story-specific visual events, not dark stock images."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from scripts.umbral3_horror_direction import BEATS, VERSION, directed_prompts

ROOT=Path(__file__).resolve().parents[1]

class ApproxTokenizer:
    model_max_length=99
    def __call__(self,text,truncation=False):
        self_last = text
        # Conservative offline estimate; real inference validates exact CLIP BPE.
        import re
        return SimpleNamespace(input_ids=re.findall(r"[a-zA-Z0-9]+|[^\w\s]",text))

class TightTokenizer(ApproxTokenizer):
    model_max_length=8

class HorrorDirectionTests(unittest.TestCase):
    def setUp(self):
        self.stories=[]
        for path in ("stories_morning.json","stories.json"):
            self.stories.extend(
                x for x in json.loads((ROOT/path).read_text(encoding="utf-8"))
                if "2026-11-21"<=x.get("publish_date","")<="2026-11-27")
    def test_all_fourteen_stories_have_six_unique_tension_beats(self):
        self.assertEqual(len(self.stories),14)
        self.assertEqual(VERSION,"horror-v2")
        self.assertTrue({x["title"] for x in self.stories}.issubset(set(BEATS)))
        self.assertIn("La cinta amarilla",BEATS)
        self.assertEqual(len(BEATS["La cinta amarilla"]),6)
        for story in self.stories:
            with self.subTest(title=story["title"]):
                prompts=directed_prompts(story,ApproxTokenizer())
                self.assertEqual(len(prompts),6)
                self.assertEqual(len(set(prompts)),6)
                for i,p in enumerate(prompts):
                    self.assertIn(BEATS[story["title"]][i],p)
                    self.assertIn("Photoreal psychological horror",p)
                    self.assertIn("No words, no watermark",p)
                    self.assertNotIn("cut and paste",p)
    def test_supernatural_content_not_merely_horror_adjective(self):
        examples={
            "El banco de la parada":("submerged underwater","trapped passengers","STILL SITTING"),
            "Las huellas de sal":("SALT crystals","behind the broom","WHITE SALT footprints"),
            "El último doblaje":("shadow stays motionless","hand is rigid","spin endlessly"),
            "El ascensor de servicio":("decades younger","ring itself has vanished","child-height"),
        }
        for title,phrases in examples.items():
            beats=" | ".join(BEATS[title])
            for phrase in phrases:
                with self.subTest(title=title,phrase=phrase):
                    self.assertIn(phrase,beats)
    def test_refuses_uncurated_and_impossible_context(self):
        story=next(s for s in self.stories if s["title"]=="El banco de la parada")
        with self.assertRaisesRegex(ValueError,"No curated"):
            directed_prompts({**story,"title":"Unreviewed future story"},ApproxTokenizer())
        with self.assertRaisesRegex(ValueError,"exceeds actual tokenizer"):
            directed_prompts(story,TightTokenizer())
    def test_original_story_is_not_mutated_or_approved(self):
        story=next(s for s in self.stories if s["title"]=="El banco de la parada")
        before=json.dumps(story,sort_keys=True)
        directed_prompts(story,ApproxTokenizer())
        self.assertEqual(json.dumps(story,sort_keys=True),before)
        self.assertNotIn("visual_approved",story)
