#!/usr/bin/env python3
"""Render local de UMBRAL. No contiene llamadas a redes sociales."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import time
from zoneinfo import ZoneInfo

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
    from audio_engine import generate_narration
    return generate_narration(text, out, phrases)


OUTRO_PHRASE = 'Has cruzado el umbral. Y ahora... no mires atrás.'


def episode_intro(story):
    number = story.get('episode_number')
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise ValueError('La historia necesita un episode_number fijo y positivo')
    return f"Historia número {number}: {story['title']}."


def generate_branded_voice(story, out):
    from audio_engine import generate_branded_narration
    return generate_branded_narration(
        episode_intro(story), story['narration'], OUTRO_PHRASE, out, phrases)


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


def encode(out, images, duration, outfile, branding=None):
    if not images:
        raise ValueError('Se necesitan imágenes para renderizar')
    # Rutas relativas controladas; subprocess nunca utiliza shell.
    if branding is None:
        # The small technical fixture can still render an unbranded sample.
        timeline = [(image, duration / len(images)) for image in images]
    else:
        intro_end = float(branding['intro_end'])
        outro_start = float(branding['outro_start'])
        total = float(branding['duration'])
        if abs(total - duration) > 0.04:
            raise ValueError('La voz y las tarjetas no tienen la misma duración')
        if not (1 <= intro_end < outro_start - 10 < duration - 1):
            raise ValueError('Duraciones de intro, historia y outro imposibles')
        intro = out / 'intro_card.png'
        outro = out / 'outro_card.png'
        story_each = (outro_start - intro_end) / len(images)
        timeline = ([(intro, intro_end)]
                    + [(img, story_each) for img in images]
                    + [(outro, duration - outro_start)])
    animated_inputs = []
    if branding is not None:
        from scripts.brand_animation import render_brand
        story = json.loads((out / 'brand_story.json').read_text())
        brand_dir = out / 'branding'
        brand_dir.mkdir(exist_ok=True)
        for kind, seconds in [('intro', intro_end), ('outro', duration-outro_start)]:
            clip = render_brand(story, kind, seconds, brand_dir)
            animated_inputs.extend(['-i', str(clip.resolve())])
    lines = []
    for image, seconds in timeline:
        if (image.parent.resolve() != out.resolve() or "'" in image.name
                or seconds <= 0):
            raise ValueError('Tarjeta o escena fuera del directorio de render')
        lines.extend([f"file '{image.name}'", f'duration {seconds:.6f}'])
    lines.append(f"file '{timeline[-1][0].name}'")
    (out / 'scenes.txt').write_text('\n'.join(lines) + '\n')
    # Movimiento lento de cámara Ken Burns y ambiente original sintetizado con FFmpeg.
    # Sin bibliotecas de música, material de terceros ni servicios de pago.
    vf = ("[0:v]scale=720:1280:force_original_aspect_ratio=increase,"
          "crop=720:1280,setsar=1,fps=24,"
          "zoompan=z='min(zoom+0.000055,1.08)':"
          "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          "d=1:s=720x1280:fps=24,ass=subtitles.ass[v]")
    if branding is not None:
        vf = vf.replace('ass=subtitles.ass[v]', 'null[base]')
        vf += (f";[3:v]setpts=PTS-STARTPTS[intro];"
               f"[4:v]setpts=PTS-STARTPTS+{outro_start}/TB[outro];"
               f"[base][intro]overlay=eof_action=pass:enable='lt(t,{intro_end})'[opened];"
               f"[opened][outro]overlay=eof_action=pass:enable='gte(t,{outro_start})',"
               "ass=subtitles.ass[v]")
    af = ("[1:a]volume=1[voice];[2:a]volume=1[music];"
          "[voice][music]amix=inputs=2:duration=first:normalize=0,"
          "alimiter=limit=0.92[mixed]")
    run('ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat',
        '-safe', '1', '-i', 'scenes.txt', '-i', 'voice.wav',
        '-i', 'music.wav', *animated_inputs,
        '-filter_complex', vf + ';' + af,
        '-map', '[v]', '-map', '[mixed]', '-t', f'{duration:.6f}',
        '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-crf', '23',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-ar', '48000',
        '-movflags', '+faststart', outfile.name, cwd=out)
    validate_video(outfile, duration)


def validate_video(path, expected):
    info = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in info['streams'] if s['codec_type'] == 'audio')
    assert (video['width'], video['height']) == (WIDTH, HEIGHT)
    assert video['codec_name'] == 'h264' and audio['codec_name'] == 'aac'
    assert audio.get('sample_rate') == '48000', 'Audio AAC debe salir a 48 kHz para Meta'
    assert audio.get('channels') in (1, 2), 'Meta solo admite 1-2 canales'
    assert video.get('pix_fmt') == 'yuv420p', 'Video debe ser 4:2:0'
    fps_num, fps_den = map(int, video['avg_frame_rate'].split('/'))
    assert fps_den and 23 <= fps_num / fps_den <= 60, 'FPS fuera de rango para Meta'
    assert abs(float(info['format']['duration']) - expected) < 0.3
    run('ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-')


def load_stories():
    stories = json.loads((BASE / 'stories.json').read_text(encoding='utf-8'))
    if not stories:
        raise ValueError('No hay relatos')
    seen_numbers = set()
    seen_dates = set()
    for story in stories:
        if not 140 <= len(story['narration'].split()) <= 170:
            raise ValueError(f"Longitud incorrecta: {story['title']}")
        if not 3 <= len(story['scenes']) <= 8:
            raise ValueError('Se requieren de tres a ocho escenas')
        episode = story.get('episode_number')
        if episode is not None:
            if not isinstance(episode, int) or isinstance(episode, bool) or episode < 1 or episode in seen_numbers:
                raise ValueError('Número de episodio ausente o repetido: ' + str(episode))
            seen_numbers.add(episode)
        if story.get('publish_date'):
            day = story['publish_date']
            if day in seen_dates:
                raise ValueError('Dos historias diarias con la misma fecha ' + day)
            seen_dates.add(day)
            if episode is None or len(story['scenes']) != 6:
                raise ValueError('Un episodio diario necesita número fijo y seis escenas')
        if story.get('test_date') and story.get('publish_date'):
            raise ValueError('Un episodio de prueba no debe ocupar una fecha diaria')
    return stories


def render():
    date = dt.date.fromisoformat(os.getenv('UMBRAL_DATE', dt.datetime.now(ZoneInfo('Europe/Madrid')).date().isoformat()))
    stories = load_stories()
    daily = next((s for s in stories if s.get('publish_date') == date.isoformat()), None)
    test_title = os.getenv('UMBRAL_STORY_TITLE', '')
    if test_title:
        # Test autorizado de una sola vez; no puede reemplazar el Reel diario.
        if (os.getenv('UMBRAL_TEST_MODE') != 'cinematic-episode-6'
                or test_title != 'La luz del rellano'):
            raise ValueError('Selección de relato de prueba no autorizada')
        test_story = next((s for s in stories if s['title'] == test_title), None)
        if test_story is None or test_story.get('episode_number') != 6:
            raise ValueError('Relato de prueba no disponible o fecha incorrecta')
        # A test gets a dated output ONLY in the artifact, not in the production queue.
        story = {**test_story, 'publish_date': date.isoformat()}
    else:
        if os.getenv('UMBRAL_REQUIRE_DATED_STORY') == '1' and daily is None:
            raise ValueError('Falta un relato original fechado para ' + date.isoformat())
        story = daily if daily is not None else stories[(date - dt.date(2026, 11, 15)).days % len(stories)]
    if 'episode_number' not in story:
        raise ValueError('La historia seleccionada no tiene número de episodio fijo')
    OUT.mkdir(exist_ok=True)
    started = time.monotonic()
    cues, duration = generate_branded_voice(story, OUT)
    from music_engine import generate_ambient_score
    generate_ambient_score(duration, cues, OUT, seed=7300 + date.toordinal() % 10000)
    voiced = time.monotonic()
    write_subtitles(cues, OUT / 'subtitles.ass')
    images = generate_images(story, OUT)
    # Cover is a distinct downloadable JPEG. Brand cards are original
    # graphics; they NEVER reuse any generated story scene.
    from scripts.thumbnail import make_thumbnail
    from scripts.brand_cards import make_brand_cards
    make_thumbnail(story, images, OUT / 'cover.jpg')
    make_brand_cards(story, OUT)
    (OUT / 'brand_story.json').write_text(json.dumps(story, ensure_ascii=False))
    timing = json.loads((OUT / 'branding_timing.json').read_text(encoding='utf-8'))
    illustrated = time.monotonic()
    outfile = OUT / f'umbral_{date:%Y%m%d}.mp4'
    encode(OUT, images, duration, outfile, branding=timing)
    timings = {'voice_seconds': voiced - started, 'images_seconds': illustrated - voiced,
               'encoding_seconds': time.monotonic() - illustrated,
               'total_seconds': time.monotonic() - started}
    (OUT / 'timings.json').write_text(json.dumps(timings, indent=2))
    print(json.dumps(timings), flush=True)
    (OUT / 'story_used.json').write_text(json.dumps({'date': str(date), **story}, ensure_ascii=False, indent=2))
    (OUT / 'caption.txt').write_text(
        f"Historia {story['episode_number']}: {story['title']}\n"
        + story['caption'] + '\n#UmbralTerror #RelatosDeTerror\n',
        encoding='utf-8')
    print(f'Vídeo verificado: {outfile} ({duration:.2f}s)')


if __name__ == '__main__':
    render()
