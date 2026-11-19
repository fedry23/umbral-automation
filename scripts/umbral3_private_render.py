"""Run a single isolated fixture with actual models and fail-closed media checks."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import render
from scripts.storyboard import validate_storyboard

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/umbral3_stories.json'

def load_fixture(index):
    if type(index) is not int or index not in (0, 1, 2):
        raise ValueError('Unknown fixture')
    stories = json.loads(FIXTURE.read_text(encoding='utf-8'))
    story = stories[index]
    if 'publish_date' in story or story.get('episode_number') != 9001 + index:
        raise ValueError('Fixture could collide with official publication')
    validate_storyboard(story)
    if not 140 <= len(story['narration'].split()) <= 170:
        raise ValueError('Invalid fixture duration contract')
    return story

def run_fixture(index):
    # Do not accept credentials, official output paths, or a production slot.
    if any(os.environ.get(k) for k in ('IG_ACCESS_TOKEN', 'IG_PUBLISH_ENABLED', 'UMBRAL_META_PUBLISH_ENABLED')):
        raise RuntimeError('Meta environment must be absent')
    story = load_fixture(index)
    with tempfile.TemporaryDirectory(prefix='umbral3-fixture-') as tmp:
        out = Path(tmp)
        start = time.monotonic()
        video = render.render_story_media(story, out, dt.date(2000, 1, 1),
                                          f'private-fixture-{index + 1}.mp4')
        if video.parent != out or video.name != f'private-fixture-{index + 1}.mp4':
            raise ValueError('Unexpected output path')
        from PIL import Image
        for name in ('cover.jpg', 'scene_contact_sheet.jpg', *(f'scene_{i:02}.png' for i in range(6))):
            with Image.open(out / name) as image:
                if name == 'cover.jpg' and (image.size != (1080, 1920) or image.format != 'JPEG'):
                    raise ValueError('Invalid cover')
                image.verify()
        for path in (video, out/'voice.wav', out/'music.wav'):
            subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(path),'-f','null','-'], check=True)
        if 'Dialogue:' not in (out/'subtitles.ass').read_text(encoding='utf-8'):
            raise ValueError('No subtitle events')
        timeline = json.loads((out/'shot_timeline.json').read_text(encoding='utf-8'))
        report = json.loads((out/'image_quality_report.json').read_text(encoding='utf-8'))
        if len(timeline) != 6 or len(report) != 6:
            raise ValueError('Incomplete shots')
        if any(a['end'] != b['start'] for a,b in zip(timeline,timeline[1:])):
            raise ValueError('Discontinuous timeline')
        # Only non-sensitive metrics leave the runner; never print media bytes.
        summary = {'fixture': index + 1, 'media_decoded': True,
                   'video_bytes': video.stat().st_size,
                   'elapsed_seconds': round(time.monotonic()-start, 2),
                   'timings': json.loads((out/'timings.json').read_text()),
                   'image_qa': report,
                   'shot_durations': [round(s['end']-s['start'],2) for s in timeline],
                   'visual_review': 'not_performed'}
        print('UMBRAL3_PRIVATE_RESULT=' + json.dumps(summary, ensure_ascii=False), flush=True)
        return summary

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=int, required=True, choices=(0,1,2))
    run_fixture(parser.parse_args().index)
