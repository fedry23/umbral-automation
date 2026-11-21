"""Regression against photorealistic but unrelated, non-horror v3 frames."""
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

from scripts.umbral3_horror_direction import BEATS
from scripts.umbral3_horror_v3 import directed_prompts_v3
from scripts.umbral3_horror_v31 import VERSION, directed_prompts_v31

ROOT=Path(__file__).resolve().parents[1]


class Tokenizer:
    model_max_length=160
    def __call__(self,text,truncation=False):
        if truncation:
            raise AssertionError("Never truncate supernatural beats")
        return SimpleNamespace(input_ids=re.findall(r"[a-zA-Z0-9]+|[^\\w\\s]",text))


class HorrorV31Tests(unittest.TestCase):
    def stories(self):
        return [
            story
            for filename in ("stories_morning.json","stories.json")
            for story in json.loads((ROOT/filename).read_text(encoding="utf-8"))
        ]

    def test_existing_curated_stories_keep_actual_horror_events_and_actions(self):
        self.assertEqual(VERSION,"horror-v3-1")
        stories=self.stories()
        for story in stories:
            if story["title"] not in BEATS or story["title"] == "El banco de la parada":
                continue
            with self.subTest(title=story["title"]):
                prompts=directed_prompts_v31(story,Tokenizer())
                self.assertEqual(len(prompts),6)
                self.assertEqual(len(set(prompts)),6)
                for prompt,beat,shot in zip(
                    prompts,BEATS[story["title"]],story["storyboard"]["shots"]
                ):
                    self.assertIn(beat,prompt)
                    self.assertIn(shot["action"],prompt)
                    self.assertIn("horror",prompt)
                    self.assertIn("No text",prompt)
                    self.assertNotIn("ready_to_publish",prompt)

    def test_owner_approved_bus_stop_six_prompts_are_untouched(self):
        story=next(s for s in self.stories() if s["title"]=="El banco de la parada")
        self.assertEqual(directed_prompts_v31(story,Tokenizer()),
                         directed_prompts_v3(story,Tokenizer()))

    def test_tight_context_fails_closed_instead_of_dropping_anomaly(self):
        story=next(s for s in self.stories() if s["title"]=="La pintura fresca")
        tok=Tokenizer()
        tok.model_max_length=8
        with self.assertRaisesRegex(ValueError,"cannot retain"):
            directed_prompts_v31(story,tok)

    def test_uncurated_story_not_declared_horror_ready(self):
        story=next(s for s in self.stories() if s["title"]=="La cinta amarilla")
        with self.assertRaisesRegex(ValueError,"Uncurated supernatural beats"):
            directed_prompts_v31(story,Tokenizer())

    def test_short_clip_context_keeps_story_horror_when_possible(self):
        story=next(s for s in self.stories() if s["title"]=="La pintura fresca")
        tok=Tokenizer()
        tok.model_max_length=77
        prompts=directed_prompts_v31(story,tok)
        self.assertEqual(len(prompts),6)
        self.assertIn(BEATS[story["title"]][0],prompts[0])
