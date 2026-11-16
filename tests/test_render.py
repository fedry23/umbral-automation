import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
import sys
import types

import render


class RenderTests(unittest.TestCase):
    def test_stories(self):
        stories = render.load_stories()
        self.assertGreaterEqual(len(stories), 3)
        for story in stories:
            self.assertEqual(' '.join(render.phrases(story['narration'])), story['narration'])
            from PIL import ImageFont
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 38)
            for phrase in render.phrases(story['narration']):
                lines = render.subtitle_lines(phrase)
                self.assertLessEqual(len(lines), 2)
                self.assertTrue(all(font.getlength(line) <= 550 for line in lines))

    def test_subtitles(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'subtitles.ass'
            render.write_subtitles([(0, 2.25, 'La puerta se abrió.'), (3, 4, '{\\b1}Nadie.')], path)
            text = path.read_text()
            self.assertIn('0:00:02.25', text)
            self.assertIn('0:00:03.00', text)
            self.assertNotIn('{\\b1}', text)
            self.assertEqual(text.count('Dialogue:'), 2)

    def test_voice_timing_and_speed(self):
        import numpy as np
        import soundfile as sf
        import torch
        calls = []

        class Pipeline:
            def __init__(self, **kwargs):
                self.settings = kwargs

            def __call__(self, text, **kwargs):
                calls.append((text, kwargs))
                yield text, None, torch.zeros(24000)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with patch.dict(sys.modules, {'kokoro': types.SimpleNamespace(KPipeline=Pipeline)}):
                with patch.dict('os.environ', {'UMBRAL_SPEED': '0.82'}):
                    cues, duration = render.generate_voice('La puerta crujió. Nadie contestó.', out)
            audio, rate = sf.read(out / 'voice.wav')
            self.assertEqual(rate, 24000)
            self.assertEqual(cues[0], (0.0, 1.0, 'La puerta crujió.'))
            self.assertEqual(cues[1], (1.65, 2.65, 'Nadie contestó.'))
            self.assertAlmostEqual(duration, len(audio) / rate)
            self.assertAlmostEqual(duration, 3.3)
            self.assertTrue(all(c[1] == {'voice': 'em_alex', 'speed': 0.82} for c in calls))

    def test_publication_stays_disabled(self):
        import yaml
        workflow = yaml.load((render.BASE / '.github/workflows/reel.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(workflow['on']['schedule'][0]['cron'], '17 2 * * *')
        self.assertEqual(workflow['permissions']['contents'], 'read')
        steps = workflow['jobs']['generar']['steps']
        blocked = [step for step in steps if step.get('name') in {
            'Preparar vídeo público para Meta', 'Esperar vídeo público en GitHub Pages', 'Publicar en Instagram'}]
        self.assertEqual(len(blocked), 3)
        self.assertTrue(all(step['if'] == '${{ false }}' for step in blocked))
        self.assertTrue((render.BASE / 'publish_reel.py').is_file())

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
