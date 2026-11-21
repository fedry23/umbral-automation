"""UMBRAL branding: natural intro/outro, low-pitched central narration."""
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest

import numpy as np
import soundfile as sf

import audio_engine
import render


class BrandingTests(unittest.TestCase):
    def test_fixed_episode_intro(self):
        self.assertEqual(render.episode_intro(
            {'episode_number': 4, 'title': 'La pecera'}),
            'Historia número 4: La pecera.')
        with self.assertRaises(ValueError):
            render.episode_intro({'title': 'No numbered'})

    def test_only_middle_story_has_lower_pitch(self):
        # Independent of the network/TTS: a 180 Hz synthetic voiced sample.
        def fake_narrate(text, out, split_phrases, pipeline=None):
            t = np.arange(audio_engine.RATE) / audio_engine.RATE
            signal = (0.2 * np.sin(2 * np.pi * 180.0 * t)).astype(np.float32)
            sf.write(Path(out) / 'voice.wav', signal, audio_engine.RATE)
            return [(0.05, 0.9, text)], 1.0

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(audio_engine, 'generate_narration', fake_narrate):
                cues, duration = audio_engine.generate_branded_narration(
                    'Intro', 'Relato original', 'Outro', Path(tmp),
                    lambda text: [text], pipeline=object())
            audio, sr = sf.read(Path(tmp) / 'voice.wav', dtype='float32')
            self.assertEqual(sr, audio_engine.RATE)
            self.assertAlmostEqual(duration, len(audio) / sr, places=4)
            self.assertEqual([c[2] for c in cues],
                             ['Intro', 'Relato original', 'Outro'])
            # Intro/outro retain original 180-Hz timbre; only the story
            # receives the old lowered branding treatment.
            def strongest_frequency(segment):
                spec = np.abs(np.fft.rfft(segment))
                return np.fft.rfftfreq(len(segment), 1/sr)[np.argmax(spec)]
            intro_freq = strongest_frequency(audio[:sr])
            story_start = round((cues[1][0] - 0.05) * sr)
            story_freq = strongest_frequency(audio[story_start:story_start+sr])
            outro_start = round((cues[2][0] - 0.05) * sr)
            outro_freq = strongest_frequency(audio[outro_start:outro_start+sr])
            self.assertAlmostEqual(intro_freq, 180, delta=3)
            self.assertAlmostEqual(outro_freq, 180, delta=3)
            self.assertLess(story_freq, intro_freq * 0.90)
            self.assertLess(story_freq, outro_freq * 0.90)
            self.assertAlmostEqual(story_freq, 150, delta=4)


if __name__ == '__main__':
    unittest.main()
