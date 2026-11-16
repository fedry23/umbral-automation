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

    def test_narration_uses_complete_sentences_not_caption_chunks(self):
        import numpy as np
        import soundfile as sf
        import torch
        from audio_engine import generate_ambient_score, speech_units
        calls = []

        class Pipeline:
            def __init__(self, **kwargs):
                pass

            def __call__(self, text, **kwargs):
                calls.append((text, kwargs))
                yield text, None, torch.ones(24000) * 0.04

        text = ('Una puerta apareció en el pasillo y nadie supo explicar por qué estaba allí. '
                'Alguien empezó a llamar desde el otro lado.')
        self.assertEqual(len(speech_units(text)), 2)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with patch.dict(sys.modules, {'kokoro': types.SimpleNamespace(KPipeline=Pipeline)}):
                with patch.dict('os.environ', {'UMBRAL_SPEED': '1.08'}):
                    cues, duration = render.generate_voice(text, out)
            audio, rate = sf.read(out / 'voice.wav')
            self.assertEqual(rate, 24000)
            self.assertEqual(len(calls), 2)  # 2 sentences, not every 7 caption words
            self.assertTrue(all(s == {'voice': 'em_alex', 'speed': 1.08} for _, s in calls))
            self.assertEqual(' '.join(c[2] for c in cues), text)
            self.assertAlmostEqual(duration, 2.6, places=2)
            self.assertTrue(all(0 <= a < b <= duration for a, b, _ in cues))
            self.assertTrue(all(cues[i][1] <= cues[i+1][0] for i in range(len(cues)-1)))
            generate_ambient_score(duration, cues, out)
            music, music_rate = sf.read(out / 'music.wav')
            self.assertEqual(music_rate, 24000)
            self.assertEqual(len(audio), len(music))
            self.assertGreater(float(np.max(abs(music))), 0.002)
            self.assertLess(float(np.max(abs(music))), 0.09)


    def test_new_reels_have_six_scenes(self):
        stories = render.load_stories()
        dated = [s for s in stories if s.get('publish_date') == '2026-11-17']
        self.assertEqual(len(dated), 1)
        self.assertEqual(len(dated[0]['scenes']), 6)

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
            from audio_engine import generate_ambient_score
            generate_ambient_score(3, [(0.1, 2.4, 'Prueba de voz')], out)
            render.encode(out, paths, 3, out / 'test.mp4')
            self.assertGreater((out / 'test.mp4').stat().st_size, 10000)


if __name__ == '__main__':
    unittest.main()
