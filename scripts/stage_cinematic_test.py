"""Download only the explicitly reviewed successful episode-6 render."""
import datetime as dt
import json
from pathlib import Path
import shutil

from scripts.thumbnail import make_thumbnail
import subprocess
from zoneinfo import ZoneInfo
from stage_daily_reel import github_get, validate_cover, validate_mp4

config = json.loads(Path('ops/cinematic-publish.json').read_text())
run_id = int(config['reviewed_run_id'])
run = github_get(f'repos/fedry23/umbral-automation/actions/runs/{run_id}')
if (run['conclusion'] != 'success' or run['head_branch'] != 'main'
        or run['path'] != '.github/workflows/cinematic_test.yml'):
    raise RuntimeError('No es un render de prueba verificado')
subprocess.run(['gh','run','download',str(run_id),'--name','umbral-cinematic-6','--dir','reviewed'],check=True)
root=Path('reviewed')
story=json.loads((root/'story_used.json').read_text())
if story.get('episode_number') != 6 or story.get('title') != 'La luz del rellano':
    raise RuntimeError('Episodio incorrecto')
day=dt.datetime.now(ZoneInfo('Europe/Madrid')).date().isoformat()
if story['date'] != day or config['authorized_date'] != day:
    raise RuntimeError('Prueba caducada: requiere revisar fecha, no publicar automaticamente')
mp4=root/('umbral_'+day.replace('-','')+'.mp4')
validate_mp4(mp4)
# Recreate the approved episode's cover from its establishing shot without
# rerendering the reviewed video or altering its voice, music or captions.
scene_images = [root / f'scene_{i:02d}.png' for i in range(6)]
make_thumbnail(story, scene_images, root/'cover.jpg')
validate_cover(root/'cover.jpg')
Path('staged').mkdir(exist_ok=True)
for p in [mp4,root/'cover.jpg',root/'story_used.json',root/'caption.txt']:
    shutil.copy2(p,Path('staged')/p.name)
