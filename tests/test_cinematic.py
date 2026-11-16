import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import soundfile as sf
from PIL import Image
import render
from scripts.brand_animation import frame
from scripts import publish_daily as publisher

class CinematicTests(unittest.TestCase):
    def test_environment_moves_and_closes(self):
        story={'title':'La luz del rellano','episode_number':6}
        a=np.asarray(frame(story,'intro',1,4),dtype=float)
        b=np.asarray(frame(story,'intro',2,4),dtype=float)
        self.assertGreater(np.mean(abs(a-b)),1)
        early=np.asarray(frame(story,'outro',1,4),dtype=float)
        end=np.asarray(frame(story,'outro',3.99,4),dtype=float)
        self.assertLess(end.mean(),early.mean()*.1)

    def test_real_branded_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            images=[]
            for name in ['scene_00.png','intro_card.png','outro_card.png']:
                p=out/name
                Image.new('RGB',(512,896),(45,15,15)).save(p)
                if name.startswith('scene'): images.append(p)
            (out/'brand_story.json').write_text(json.dumps({'title':'Prueba','episode_number':6}))
            sf.write(out/'voice.wav',np.zeros(16*24000),24000)
            sf.write(out/'music.wav',np.zeros(16*24000),24000)
            render.write_subtitles([(2,3,'Prueba')],out/'subtitles.ass')
            render.encode(out,images,16,out/'test.mp4',{'intro_end':2,'outro_start':14,'duration':16})
            self.assertGreater((out/'test.mp4').stat().st_size,10000)

    def test_ambiguous_intent_blocks_second_post(self):
        import datetime as dt
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            (out/'prepared.json').write_text(json.dumps({'status':'prepared','date':'2026-11-16','container':'123'}))
            intent=out/'intent.json';intent.write_text('{}')
            with patch.object(publisher,'OUT',out),patch.object(publisher,'already_published',return_value=None),patch.object(publisher,'intent_path',return_value=intent),patch.object(publisher,'one_time_late_allowed',return_value=True),patch.object(publisher,'api') as api:
                with self.assertRaises(RuntimeError): publisher.publish('2026-11-16')
                api.assert_not_called()
