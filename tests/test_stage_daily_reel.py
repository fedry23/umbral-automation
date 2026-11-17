"""Regression: the dated MP4 name must not be replaced by the story lookup list."""
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import stage_daily_reel as stage


class StageDailyReelTests(unittest.TestCase):
    def test_duplicate_zip_entry_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr("same.txt", b"one")
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr("same.txt", b"two")
            with patch.object(stage, "OUT", Path(tmp)):
                with self.assertRaisesRegex(ValueError, "duplicadas"):
                    stage.extract_run_zip(stream.getvalue(), "2026-11-17")

    def test_oversized_zip_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr("large.mp4", b"abc")
            raw = bytearray(stream.getvalue())
            # ZIP central-directory uncompressed size field.
            index = raw.index(bytes((80, 75, 1, 2)))
            raw[index + 24:index + 28] = (250_000_001).to_bytes(4, "little")
            with patch.object(stage, "OUT", Path(tmp)):
                with self.assertRaisesRegex(ValueError, "grande"):
                    stage.extract_run_zip(bytes(raw), "2026-11-17")

    def test_extract_preserves_mp4_filename_after_story_validation(self):
        day = "2026-11-17"
        name = "umbral_20261117.mp4"
        story = {
            "date": day, "publish_date": day, "title": "Test",
            "episode_number": 1, "narration": "palabra " * 150,
            "scenes": ["escena"] * 6, "caption": "Texto",
        }
        files = {
            name: b"video-placeholder",
            "story_used.json": json.dumps(story).encode(),
            "caption.txt": b"Texto",
            "music.wav": b"0" * 20001,
            "cover.jpg": b"jpeg-placeholder",
            "intro_card.png": b"png",
            "outro_card.png": b"png",
            "branding_timing.json": json.dumps(
                {"intro_end": 1, "outro_start": 20, "duration": 30}).encode(),
        }
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for filename, data in files.items():
                archive.writestr(filename, data)
        with tempfile.TemporaryDirectory() as tmp:
            original = os.getcwd()
            try:
                os.chdir(tmp)
                Path("stories.json").write_text(json.dumps([story]), encoding="utf-8")
                with (patch.object(stage, "OUT", Path("staged")),
                     patch.object(stage, "validate_cover", return_value=True),
                     patch.object(stage, "validate_mp4", return_value=30.0)):
                    result = stage.extract_run_zip(stream.getvalue(), day)
                self.assertEqual(result["file"], "staged/" + name)
                self.assertEqual(Path(result["file"]).read_bytes(), b"video-placeholder")
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
