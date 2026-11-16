#!/usr/bin/env python3
"""Render local de UMBRAL. No contiene llamadas a redes sociales."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import time

BASE = Path(__file__).resolve().parent
OUT = BASE / 'output'
WIDTH, HEIGHT = 720, 1280
RATE = 24000


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def subtitle_lines(text):
    from PIL import ImageFont
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 38)
    words = text.split()
    if font.getlength(text) <= 550:
        return [text]
    options = [(' '.join(words[:i]), ' '.join(words[i:])) for i in range(1, len(words))]
    if not options:
        raise ValueError('Palabra demasiado larga para el subtítulo')
    lines = min(options, key=lambda pair: max(font.getlength(line) for line in pair))
    if max(font.getlength(line) for line in lines) > 550:
        raise ValueError('Subtítulo demasiado largo')
    return list(lines)


def phrases(text):
    """Unidades cortas que caben en dos líneas, medidas con la fuente real."""
    result = []
    for sentence in re.split(r'(?<=[.!?…;,:])\s+', text.strip()):
        current = []
        for word in sentence.split():
            candidate = ' '.join(current + [word])
            try:
                subtitle_lines(candidate)
                fits = len(current) < 7
            except ValueError:
                fits = False
            if current and not fits:
                result.append(' '.join(current))
                current = []
            current.append(word)
        if current:
            result.append(' '.join(current))
    return result


def generate_voice(text, out):
    import torch
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    speed = float(os.getenv('UMBRAL_SPEED', '0.86'))
    if not 0.5 <= speed <= 1.2:
        raise ValueError('UMBRAL_SPEED debe estar entre 0.5 y 1.2')
    pipeline = KPipeline(lang_code='e', repo_id='hexgrad/Kokoro-82M', device='cpu')
    parts, cues, cursor = [], [], 0
    units = phrases(text)
    for index, phrase in enumerate(units, 1):
        chunks = [audio.cpu().numpy() for _, _, audio in pipeline(
            phrase, voice='em_alex', speed=speed) if audio is not None]
        if not chunks:
            raise RuntimeError('Kokoro no ha generado audio')
        audio = np.concatenate(chunks)
        cues.append((cursor / RATE, (cursor + len(audio)) / RATE, phrase))
        parts.append(audio)
        cursor += len(audio)
        pause = int(RATE * (0.65 if phrase[-1] in '.!?…' else
                            0.3 if phrase[-1] in ',;:' else 0.06))
        parts.append(np.zeros(pause, dtype=np.float32))
        cursor += pause
        print(f'Voz: {index}/{len(units)} fragmentos', flush=True)
    sf.write(out / 'voice.wav', np.concatenate(parts), RATE)
    return cues, cursor / RATE


def ass_time(seconds):
    ticks = round(seconds * 100)
    return f'{ticks // 360000}:{ticks // 6000 % 60:02}:{ticks // 100 % 60:02}.{ticks % 100:02}'


def write_subtitles(cues, dest):
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,38,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,1,0,0,0,100,100,0,0,1,3,1,2,65,95,235,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = []
    for start, end, text in cues:
        # No se permiten comandos ASS procedentes del relato.
        text = text.replace('\\', '').replace('{', '').replace('}', '')
        text = r'\N'.join(subtitle_lines(text))
        events.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{text}')
    dest.write_text(header + '\n'.join(events) + '\n', encoding='utf-8')


def generate_images(story, out):
    import torch
    from diffusers import AutoPipelineForText2Image
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    pipe = AutoPipelineForText2Image.from_pretrained(
        'stabilityai/sd-turbo', torch_dtype=torch.float32)
    pipe.enable_attention_slicing()
    paths = []
    for i, scene in enumerate(story['scenes']):
        prompt = ('Cinematic realistic psychological horror film still, vertical composition, '
                  '35mm photography, dim practical lighting, detailed environment, no lettering. ' + scene)
        image = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=0.0,
                     height=896, width=512,
                     generator=torch.Generator('cpu').manual_seed(7300 + i)).images[0]
        path = out / f'scene_{i:02}.png'
        image.save(path)
        print(f'Imagen: {i + 1}/{len(story["scenes"])}', flush=True)
        paths.append(path)
    return paths


def encode(out, images, duration, outfile):
    if not images:
        raise ValueError('Se necesitan imágenes para renderizar')
    # Rutas relativas controladas; subprocess nunca utiliza shell.
    lines = []
    for image in images:
        if image.parent.resolve() != out.resolve() or "'" in image.name:
            raise ValueError('Las escenas deben estar en output')
        lines.extend([f"file '{image.name}'", f'duration {duration / len(images):.6f}'])
    lines.append(f"file '{images[-1].name}'")
    (out / 'scenes.txt').write_text('\n'.join(lines) + '\n')
    run('ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat',
        '-safe', '1', '-i', 'scenes.txt', '-i', 'voice.wav',
        '-vf', 'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=24,ass=subtitles.ass',
        '-map', '0:v:0', '-map', '1:a:0', '-t', f'{duration:.6f}',
        '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-crf', '23',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart', outfile.name, cwd=out)
    validate_video(outfile, duration)


def validate_video(path, expected):
    info = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in info['streams'] if s['codec_type'] == 'audio')
    assert (video['width'], video['height']) == (WIDTH, HEIGHT)
    assert video['codec_name'] == 'h264' and audio['codec_name'] == 'aac'
    assert abs(float(info['format']['duration']) - expected) < 0.3
    run('ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-')


def load_stories():
    stories = json.loads((BASE / 'stories.json').read_text(encoding='utf-8'))
    if not stories:
        raise ValueError('No hay relatos')
    for story in stories:
        if not 140 <= len(story['narration'].split()) <= 170:
            raise ValueError(f"Longitud incorrecta: {story['title']}")
        if len(story['scenes']) < 3:
            raise ValueError('Se requieren al menos tres escenas')
    return stories


def render():
    date = dt.date.fromisoformat(os.getenv('UMBRAL_DATE', dt.datetime.now(dt.timezone.utc).date().isoformat()))
    stories = load_stories()
    daily = next((s for s in stories if s.get('publish_date') == date.isoformat()), None)
    if os.getenv('UMBRAL_REQUIRE_DATED_STORY') == '1' and daily is None:
        raise ValueError('Falta un relato original fechado para ' + date.isoformat())
    story = daily if daily is not None else stories[(date - dt.date(2026, 11, 15)).days % len(stories)]
    OUT.mkdir(exist_ok=True)
    started = time.monotonic()
    cues, duration = generate_voice(story['narration'], OUT)
    voiced = time.monotonic()
    write_subtitles(cues, OUT / 'subtitles.ass')
    images = generate_images(story, OUT)
    illustrated = time.monotonic()
    outfile = OUT / f'umbral_{date:%Y%m%d}.mp4'
    encode(OUT, images, duration, outfile)
    timings = {'voice_seconds': voiced - started, 'images_seconds': illustrated - voiced,
               'encoding_seconds': time.monotonic() - illustrated,
               'total_seconds': time.monotonic() - started}
    (OUT / 'timings.json').write_text(json.dumps(timings, indent=2))
    print(json.dumps(timings), flush=True)
    (OUT / 'story_used.json').write_text(json.dumps({'date': str(date), **story}, ensure_ascii=False, indent=2))
    (OUT / 'caption.txt').write_text(story['caption'] + '\n#UmbralTerror #RelatosDeTerror\n', encoding='utf-8')
    print(f'Vídeo verificado: {outfile} ({duration:.2f}s)')


if __name__ == '__main__':
    render()
