"""Quality gate: branded screens are original and distinct; cover is JPEG 9:16."""
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageChops

from scripts.brand_cards import make_brand_cards
from scripts.thumbnail import make_thumbnail
from scripts.stage_daily_reel import validate_cover


class CoverAndCardsTests(unittest.TestCase):
    def test_opening_and_closing_are_distinct_and_dont_use_story_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            scene = []
            for i in range(6):
                p = out / f"scene_{i:02}.png"
                Image.new("RGB", (512, 896), (30 + 5 * i, 35, 40)).save(p)
                scene.append(p)
            story = {"episode_number": 5, "title": "El piso menos dos"}
            intro, outro = make_brand_cards(story, out)
            with Image.open(intro) as start, Image.open(outro) as ending:
                self.assertEqual(start.size, (512, 896))
                self.assertEqual(ending.size, (512, 896))
                self.assertIsNotNone(ImageChops.difference(start, ending).getbbox())
                with Image.open(scene[0]) as image:
                    self.assertIsNotNone(ImageChops.difference(start, image).getbbox())
            cover = make_thumbnail(story, scene, out / "cover.jpg")
            with Image.open(cover) as image:
                self.assertEqual(image.size, (1080, 1920))
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.mode, "RGB")
            self.assertLess(cover.stat().st_size, 8_000_000)
            self.assertTrue(validate_cover(cover))

    def test_cover_prefers_opening_scene_over_uninformative_middle(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            scenes = []
            for i in range(6):
                p = out / f"scene_{i:02}.png"
                Image.new("RGB", (512, 896), (245, 35, 35) if i == 0 else (35, 35, 245)).save(p)
                scenes.append(p)
            story = {"episode_number": 6, "title": "La luz del rellano"}
            path = make_thumbnail(story, scenes, out / "cover.jpg")
            with Image.open(path) as cover:
                red, green, blue = cover.getpixel((80, 80))
                self.assertGreater(red, blue)
            with self.assertRaises(ValueError):
                make_thumbnail({**story, "cover_scene_index": 6}, scenes, out / "bad.jpg")

    def test_number_is_required_and_empty_scene_list_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                make_brand_cards({"title": "Sin número"}, tmp)
            with self.assertRaises(ValueError):
                make_thumbnail({"episode_number": 1, "title": "Prueba"}, [], Path(tmp) / "cover.jpg")

    def test_voice_timing_is_validated_before_render(self):
        import render
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            images = []
            for i in range(3):
                p = out / f"scene_{i}.png"
                Image.new("RGB", (512, 896), "black").save(p)
                images.append(p)
            # Confirm the dedicated-card timeline contract rejects impossible timing.
            with self.assertRaises(ValueError):
                render.encode(out, images, 15, out / "test.mp4",
                              branding={"intro_end": 10, "outro_start": 11, "duration": 15})


if __name__ == "__main__":
    unittest.main()
