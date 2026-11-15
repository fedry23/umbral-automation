#!/usr/bin/env python3
"""UMBRAL: renders an original-script horror reel with free local tools.

Requires: ffmpeg/ffprobe, piper-tts, Pillow, and a downloadable Spanish Piper voice.
No Instagram credentials, subscription, or external text generation required.
"""
import datetime as dt
import json
import math
import os
import random
import re
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = Path(__file__).resolve().parent
OUT = BASE / 'output'
WIDTH, HEIGHT = 720, 1280
DATE = dt.date.fromisoformat(os.getenv('UMBRAL_DATE', dt.datetime.now(dt.timezone.utc).date().isoformat()))


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def font(size: int, bold=False):
    path = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(path, size)


def wrap_words(draw, phrase, fnt, max_width):
    out, current = [], ''
    for word in phrase.split():
        candidate = (current + ' ' + word).strip()
        if current and draw.textbbox((0, 0), candidate, font=fnt)[2] > max_width:
            out.append(current)
            current = word
        else:
            current = candidate
    if current:
        out.append(current)
    return out


def blocks(text, count=5):
    sentences = re.split(r'(?<=[.!?…])\s+(?=[A-ZÁÉÍÓÚÜÑ«¿¡])', text.strip())
    groups = ['' for _ in range(count)]
    total = sum(len(s.split()) for s in sentences)
    i, words = 0, 0
    for s in sentences:
        if i < count - 1 and words >= (i + 1) * total / count:
            i += 1
        groups[i] = (groups[i] + ' ' + s).strip()
        words += len(s.split())
    return [g for g in groups if g]


def make_slide(text, index, date_tag, dest, intro=False):
    rng = random.Random(int(date_tag.replace('-', '')) * 100 + index)
    im = Image.new('RGB', (WIDTH, HEIGHT), '#06070a')
    px = im.load()
    glow_x, glow_y = (500 + index * 37) % WIDTH, 380 + (index % 3) * 140
    for y in range(HEIGHT):
        for x in range(WIDTH):
            d = ((x - glow_x) / 500) ** 2 + ((y - glow_y) / 570) ** 2
            glow = max(0, 1 - d) ** 2
            grain = rng.randint(-3, 3)
            red = max(0, min(255, int(7 + 61 * glow + grain)))
            grn = max(0, min(255, int(8 + 4 * glow + grain)))
            blu = max(0, min(255, int(12 + 3 * glow + grain)))
            px[x, y] = (red, grn, blu)
    draw = ImageDraw.Draw(im)
    draw.rectangle((45, 70, 52, 1210), fill=(143, 19, 32))
    draw.text((84, 96), 'U M B R A L', font=font(31, True), fill='#dc3449')
    draw.text((85, 1182), '@umbral.terror', font=font(22), fill='#8c8e97')
    draw.text((594, 1182), f'{index:02}', font=font(22), fill='#8c8e97')
    max_w = 535
    fsize = 58 if intro else 40
    while True:
        f = font(fsize, bold=intro)
        lines = []
        for paragraph in text.split('\n'):
            lines.extend(wrap_words(draw, paragraph, f, max_w) if paragraph else [''])
        line_h = int(fsize * 1.43)
        if (len(lines) * line_h < 720 and len(lines) <= (8 if intro else 15)) or fsize <= 26:
            break
        fsize -= 2
    y = (HEIGHT - len(lines) * line_h) // 2
    for line in lines:
        draw.text((86, y), line, font=f, fill='#f2edf0', stroke_width=0)
        y += line_h
    im.save(dest, optimize=True)


def render():
    stories = json.loads((BASE / 'stories.json').read_text(encoding='utf-8'))
    if not stories:
        raise RuntimeError('stories.json is empty')
    # Deterministic daily choice, avoiding consecutive repeats until the library cycles.
    start_date = dt.date(2026, 11, 15)
    position = (DATE - start_date).days % len(stories)
    story = stories[position]
    print(f'Date: {DATE}; story {position + 1}/{len(stories)}: {story["title"]}', flush=True)
    OUT.mkdir(exist_ok=True)
    voice_wav = OUT / 'voice.wav'
    # Fully offline, no cloud API, male variant of Spanish eSpeak NG.
    run('espeak-ng', '-v', 'es+m3', '-s', '142', '-w', str(voice_wav), story['narration'])
    info = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nokey=1:noprint_wrappers=1', str(voice_wav)], text=True)
    voice_length = float(info.strip())
    body = blocks(story['narration'], count=5)
    page_texts = [story['title'].upper() + '\n\n' + story['hook']] + body
    for i, page in enumerate(page_texts, 1):
        make_slide(page, i, DATE.isoformat(), OUT / f'slide_{i:02}.png', intro=(i == 1))
    intro_len = 1.8
    available = max(voice_length, 4)
    lengths = [intro_len] + [available * len(s.split()) / max(1, sum(len(t.split()) for t in body)) for s in body]
    concat = []
    for i, sec in enumerate(lengths, 1):
        concat.extend([f"file 'slide_{i:02}.png'", f'duration {sec:.5f}'])
    concat.append(f"file 'slide_{len(page_texts):02}.png'")
    (OUT / 'slides.txt').write_text('\n'.join(concat) + '\n', encoding='utf-8')
    outfile = OUT / ('umbral_' + DATE.strftime('%Y%m%d') + '.mp4')
    filter_graph = (
        "[0:v]fps=24,scale=720:1280,"
        "zoompan=z='min(zoom+0.00012,1.04)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=720x1280:fps=24,"
        "noise=alls=3:allf=t+u,format=yuv420p[v];"
        "[1:a]adelay=1800:all=1,apad=pad_dur=0.4,volume=1.05[voice];"
        "[2:a]lowpass=f=230,volume=0.05[wind];"
        "[voice][wind]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.94[a]"
    )
    run('ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-safe', '0', '-f', 'concat', '-i', str(OUT / 'slides.txt'),
        '-i', str(voice_wav),
        '-f', 'lavfi', '-i', 'anoisesrc=color=brown:amplitude=0.08:sample_rate=22050',
        '-filter_complex', filter_graph,
        '-map', '[v]', '-map', '[a]', '-r', '24', '-c:v', 'libx264', '-preset', 'veryfast',
        '-crf', '25', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart', '-shortest', str(outfile))
    (OUT / 'caption.txt').write_text(story['caption'] + '\n\n#UmbralTerror #RelatosDeTerror #MicroTerror #HistoriasDeMiedo #ReelsDeTerror\n', encoding='utf-8')
    (OUT / 'story_used.json').write_text(json.dumps({'date': DATE.isoformat(), **story}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Rendered {outfile.name} ({voice_length:.1f}s voice, {outfile.stat().st_size // 1024} KiB)', flush=True)



if __name__ == '__main__':
    render()
