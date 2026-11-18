import tempfile
import unittest
from pathlib import Path
from PIL import Image
from scripts.technical_learning import VARIANTS, DEFAULT_PARAMETERS, profile_for, parameters_for, evaluate
import render
import audio_engine
from unittest.mock import patch
import numpy as np
import soundfile as sf

DAY="2026-11-19"

def profile(experiment, mode):
    return profile_for(DAY, "09", {"schema":1,"experiment":experiment,"mode":mode})

class AVProfiles(unittest.TestCase):
    def test_only_one_parameter_changes(self):
        for experiment, (name, changes) in VARIANTS.items():
            a=parameters_for(profile(experiment, "hold"))
            b=parameters_for(profile(experiment, "promoted"))
            self.assertEqual(a, DEFAULT_PARAMETERS)
            self.assertEqual({k:v for k,v in b.items() if v != a[k]}, changes)
            self.assertEqual(profile(experiment,"promoted")["arm"],name)

    def test_invalid_settings_rejected(self):
        good=profile("voice-speed-v1","promoted")
        for bad in ({**good, "story_speed": 8}, {**good,"command":"shell"},
                    {**good, "experiment":[]}, {**good,"arm":"unknown"}):
            with self.assertRaises(ValueError):
                parameters_for(bad)

    def test_assignment_and_evaluation_for_all_variants(self):
        for experiment in VARIANTS:
            name=VARIANTS[experiment][0]
            policy={"schema":1,"experiment":experiment,"mode":"experiment"}
            for slot in ("09","21"):
                arms=[profile_for(f"2026-11-{d:02d}",slot,policy)["arm"] for d in range(1,21)]
                self.assertEqual(arms.count(name),4)
            self.assertEqual(evaluate([],experiment)["decision"],"hold")
            rows=[{"media_id":f"{slot}-{arm}-{i}","slot":slot,"arm":arm,
                   "experiment":experiment,"quality_passed":True,"editorial_arm":"fixed",
                   "reach":100,"skip":.3 if arm==name else .5,"watch_seconds":20,
                   "age_hours":168,"duration_seconds":60}
                  for slot in ("09","21") for arm in ("control",name) for i in range(5)]
            self.assertEqual(evaluate(rows,experiment)["decision"],"eligible_for_promotion")

    def test_subtitle_contour(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"subtitles.ass"
            render.write_subtitles([(0,1,"Texto")],p,outline=4)
            self.assertIn(",1,4,1,2,85,95,280,1",p.read_text())
            with self.assertRaises(ValueError):
                render.write_subtitles([],p,outline=20)

    def test_color_grade_dimensions_and_control(self):
        im=Image.new("RGB",(32,64),(120,140,160))
        self.assertIs(render.apply_visual_tone(im,"original"),im)
        cool=render.apply_visual_tone(im,"cool-film")
        self.assertEqual(cool.size,im.size)
        self.assertNotEqual(cool.getpixel((0,0)),im.getpixel((0,0)))
        with self.assertRaises(ValueError):
            render.apply_visual_tone(im,"arbitrary")

    def test_story_only_speed(self):
        calls=[]
        def fake(text,out,split_phrases,pipeline=None,speed_override=None):
            calls.append(speed_override)
            t=np.arange(audio_engine.RATE)/audio_engine.RATE
            sf.write(Path(out)/"voice.wav",.2*np.sin(2*np.pi*180*t),audio_engine.RATE)
            return [(0.05,.9,text)],1.0
        with tempfile.TemporaryDirectory() as folder, patch.object(audio_engine,"generate_narration",fake):
            audio_engine.generate_branded_narration("Intro","Relato","Final",Path(folder),
                lambda t:[t],pipeline=object(),story_speed=1.04)
        self.assertEqual(calls,[None,1.04,None])
