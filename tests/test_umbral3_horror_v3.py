"""Private horror v3 must tell six explicit events instead of stock atmosphere."""
import json
from pathlib import Path
from types import SimpleNamespace
import re
import unittest

from scripts.umbral3_horror_v3 import VERSION, TITLE, PROMPTS, directed_prompts_v3
ROOT=Path(__file__).resolve().parents[1]

class Tokenizer:
    model_max_length=160
    def __call__(self,text,truncation=False):
        return SimpleNamespace(input_ids=re.findall(r"[a-zA-Z0-9]+|[^\w\s]",text))

class V3Tests(unittest.TestCase):
    def setUp(self):
        scenes=json.loads((ROOT/"stories.json").read_text(encoding="utf-8"))
        self.story=next(s for s in scenes if s.get("title")==TITLE)
    def test_six_actions_and_focal_paradox(self):
        prompts=directed_prompts_v3(self.story,Tokenizer())
        self.assertEqual(VERSION,"horror-v3")
        self.assertEqual(len(prompts),6)
        self.assertEqual(len(set(prompts)),6)
        critical=(
            "puddle forms directly beneath",
            "fully FLOODED",
            "TWO SHOES and trouser legs",
            "wet HUMAN SHOE FOOTPRINTS",
            "TERRIFIED TRAPPED PASSENGERS INSIDE",
            "ONLY IN THE WATER REFLECTION",
        )
        for p,phrase in zip(prompts,critical):
            self.assertIn(phrase,p)
            self.assertIn("no text",p)
        self.assertIn("BENCH is EMPTY",prompts[5])
        self.assertIn("MAN SITTING",prompts[5])
    def test_unrelated_story_is_not_styled_or_approved(self):
        with self.assertRaisesRegex(ValueError,"limited"):
            directed_prompts_v3({**self.story,"title":"another story"},Tokenizer())
        self.assertNotIn("visual_approved",self.story)
    def test_tight_tokenizer_fails_without_truncating_anomaly(self):
        tok=Tokenizer()
        tok.model_max_length=8
        with self.assertRaisesRegex(ValueError,"exceeds actual"):
            directed_prompts_v3(self.story,tok)
    def test_review_prompts_avoid_daytime_and_boat_misinterpretation(self):
        text=" ".join(PROMPTS)
        self.assertIn("NIGHT",text)
        self.assertIn("no boats",text)
        self.assertIn("passengers",text.lower())
        self.assertIn("empty",PROMPTS[5].lower())
