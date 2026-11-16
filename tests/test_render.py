import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

import render


class RenderTests(unittest.TestCase):
    def test_stories(self):
        stories = render.load_stories()
        self.assertGreaterEqual(len(stories), 3)
        for story in stories:
            self.assertEqual(' '.join(render.phrases(story['narration'])), story['narration'])

    def test_subtitles(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'subtitles.ass'
            render.write_subtitles([(0, 2.25, 'La puerta se abrió.'), (3, 4, '{\\b1}Nadie.')], path)
            text = path.read_text()
            self.assertIn('0:00:02.25', text)
            self.assertIn('0:00:03.00', text)
            self.assertNotIn('{\\b1}', text)
            self.assertEqual(text.count('Dialogue:'), 2)

    def test_real_encoding(self):
        # Fixture técnica sin red; el workflow ejecuta después el render neuronal real.
        import numpy as np
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            paths = []
            for i in range(3):
                path = out / f'scene_{i:02}.png'
                rng = np.random.default_rng(i)
                Image.fromarray(rng.integers(0, 180, (512, 512, 3), dtype=np.uint8)).save(path)
                paths.append(path)
            with wave.open(str(out / 'voice.wav'), 'wb') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(24000)
                samples = (np.sin(np.arange(72000) * 2 * np.pi * 180 / 24000) * 4000).astype('<i2')
                f.writeframes(samples.tobytes())
            render.write_subtitles([(0, 1, 'La puerta se abrió.'), (1.3, 2.8, 'Nadie respondió.')], out / 'subtitles.ass')
            render.encode(out, paths, 3, out / 'test.mp4')
            self.assertGreater((out / 'test.mp4').stat().st_size, 10000)


if __name__ == '__main__':
    unittest.main()
