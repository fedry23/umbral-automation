"""Opt-in visual preparation, independent of official counters and Meta."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import render
from scripts.umbral3_storage import DropboxStore, LocalStore, get_or_prepare

ROOT=Path(__file__).resolve().parents[1]
MODELS={'turbo':'stabilityai/sd-turbo','sd15':'stable-diffusion-v1-5/stable-diffusion-v1-5'}

def visual_recipe():
    from huggingface_hub import model_info
    backend=os.getenv('UMBRAL_IMAGE_BACKEND','turbo')
    profile=os.getenv('UMBRAL_IMAGE_PROFILE','quality')
    if backend not in MODELS or profile not in ('fast','quality'):
        raise ValueError('Invalid image recipe')
    model=MODELS[backend]
    revision=model_info(model, timeout=30).sha
    if not revision or len(revision)!=40:
        raise RuntimeError('Cannot pin visual model revision')
    return {'model':model,'revision':revision,'backend':backend,
            'profile':profile,'attempts':os.getenv('UMBRAL_IMAGE_ATTEMPTS','3'),
            'low_memory':os.getenv('UMBRAL_LOW_MEMORY','0'),
            'code':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                    for p in ('render.py','image_quality.py','scripts/storyboard.py',
                              'scripts/technical_learning.py','requirements.txt','requirements-test.txt')}}

def prepare(story,day,slot,store):
    recipe=visual_recipe()
    with tempfile.TemporaryDirectory(prefix='umbral3-prep-') as tmp:
        _,status=get_or_prepare(store,story,day,slot,recipe,Path(tmp),
            lambda s,folder:render.generate_images(s,folder,model_revision=recipe['revision']))
        return status

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--date',required=True)
    p.add_argument('--slot',required=True,choices=('09','21'))
    p.add_argument('--local-store')
    args=p.parse_args()
    catalog=ROOT/('stories_morning.json' if args.slot=='09' else 'stories.json')
    matches=[s for s in json.loads(catalog.read_text()) if s.get('publish_date')==args.date]
    if len(matches)!=1 or 'storyboard' not in matches[0]:
        raise ValueError('Exactly one authored storyboard required for date and slot')
    store=LocalStore(args.local_store) if args.local_store else DropboxStore.from_env()
    print('Visual reserve status:',prepare(matches[0],args.date,args.slot,store))

if __name__=='__main__':
    main()
