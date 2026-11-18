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
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 34)
    words = text.split()
    if font.getlength(text) <= 480:
        return [text]
    options = [(' '.join(words[:i]), ' '.join(words[i:])) for i in range(1, len(words))]
    if not options:
        raise ValueError('Palabra demasiado larga para el subtítulo')
    lines = min(options, key=lambda pair: max(font.getlength(line) for line in pair))
    if max(font.getlength(line) for line in lines) > 480:
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
Style: Default,DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,1,0,0,0,100,100,0,0,1,3,1,2,85,95,280,1
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


def scene_image_prompt(scene):
    """Favor a coherent photographic scene rather than surreal artifacts."""
    if not isinstance(scene, str) or not scene.strip():
        raise ValueError("La escena visual no puede estar vacía")
    scene = ' '.join(scene.split())
    if len(scene) > 850:
        raise ValueError("La descripción de escena es demasiado larga")
    # Put the scene first: SD-Turbo's text encoder truncates long prompts.
    # Keep the camera direction short so the actual scene remains visible.
    return (
        scene + " Realistic live-action film photograph, one clear focal "
        "subject, natural anatomy, plausible lighting, coherent architecture, "
        "35mm cinematic horror, no text, no collage."
    )



# Curated object-led shots avoid the recurring SD-Turbo failures with people,
# hands, complex multi-character actions and electrical equipment manipulation.
CURATED_VISUAL_SHOTS = {
    'El turno que faltaba': [
        'Empty Spanish factory at night, one attendance terminal glowing on a desk in a small industrial control room, cold fluorescent lighting, cinematic photographic still, no people, no hands, no text.',
        'A single old industrial metal lathe inside an empty Spanish factory workshop at night, long shadows, straight realistic machinery, cinematic photographic still, no people, no hands, no text.',
        'An empty factory locker room, one metal locker door slightly open, a small vintage time clock beside the exit, grounded photographic suspense, no people, no hands, no text.',
        'Close-up of one security surveillance monitor on a factory office desk showing an empty locker-room corridor, realistic screen reflections, dim surroundings, no people, no hands, no text.',
        'An empty security booth at a Spanish factory gate at night, an old telephone resting beside a rain-streaked window, deserted parking area, cinematic photographic still, no people, no hands, no text.',
        'Close-up of one factory attendance terminal glowing deep red beside an abandoned navy work jacket hanging on a chair, empty dark corridor behind, photographic horror still, no people, no hands, no text.',
    ],
    'El contador inverso': [
        'A small basement electricity meter room in an old Spanish apartment building, a single vintage mechanical electricity meter on a concrete wall, straight-on architectural photograph, no people, no hands, no lettering.',
        'An empty third-floor apartment doorway opening onto a modest Spanish living room, a single pendant lamp above an empty armchair, realistic interior photograph, no people, no hands, no lettering.',
        'Close-up of one old mechanical electricity meter mounted on a concrete wall under a fluorescent light, simple realistic utility-room still life, no people, no hands, no lettering.',
        'An empty armchair in a modest Spanish living room, shattered glass from a fallen ceiling lamp on the floor beside the chair, realistic interior photograph, no people, no hands, no lettering.',
        'An empty second-floor apartment corridor with a wall intercom beside a doorway, a thin stream of water visible through the open doorway, realistic architectural photograph, no people, no hands, no lettering.',
        'An empty basement electricity meter room, several vintage meters on a wall, fine dust drifting from a cracked concrete ceiling, cinematic realistic architectural photograph, no people, no hands, no lettering.',
    ],
}


def visual_shots(story):
    curated = CURATED_VISUAL_SHOTS.get(story.get('title'))
    if curated is not None:
        if len(curated) != len(story['scenes']):
            raise ValueError('Las escenas visuales revisadas no coinciden con el relato')
        return curated
    return story['scenes']


def generate_images(story, out):
    from PIL import Image
    import torch
    from diffusers import AutoPipelineForText2Image
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    # The higher-quality backend is opt-in until CPU runtime is measured.
    # Keep the known-working production model as the safe default.
    backend = os.getenv('UMBRAL_IMAGE_BACKEND', 'turbo')
    models = {
        'turbo': 'stabilityai/sd-turbo',
        'sd15': 'stable-diffusion-v1-5/stable-diffusion-v1-5',
    }
    if backend not in models:
        raise ValueError('Modelo de imagen desconocido')
    pipe = AutoPipelineForText2Image.from_pretrained(
        models[backend], torch_dtype=torch.float32)
    # On CPU, attention slicing serializes work and often makes inference slower.
    # Leave it off unless explicitly requested for a memory-constrained runner.
    if os.getenv('UMBRAL_LOW_MEMORY', '0') == '1':
        pipe.enable_attention_slicing()
    import time
    # Quality-first: keep full portrait resolution and four diffusion steps.
    # Fast profile remains available only for explicit diagnostics.
    profile = os.getenv('UMBRAL_IMAGE_PROFILE', 'quality')
    if profile not in ('fast', 'quality'):
        raise ValueError('Perfil de imágenes desconocido')
    if backend == 'sd15':
        # SD 1.5 uses classifier-free guidance and a non-distilled scheduler.
        # This option is intentionally not enabled in the daily workflow.
        steps, height, width, guidance = 25, 768, 512, 7.0
    else:
        steps, height, width = (1, 640, 384) if profile == 'fast' else (4, 896, 512)
        guidance = 0.0
    print(f'UMBRAL_IMAGE_BACKEND={backend} profile={profile} '
          f'steps={steps} size={width}x{height}', flush=True)
    from image_quality import assess_image
    paths, report = [], []
    total_start = time.monotonic()
    max_attempts = int(os.getenv('UMBRAL_IMAGE_ATTEMPTS', '3'))
    if not 1 <= max_attempts <= 5:
        raise ValueError('Número de intentos de imagen fuera de rango')
    for i, scene in enumerate(visual_shots(story)):
        scene_start = time.monotonic()
        prompt = scene_image_prompt(scene)
        best_image, best_score, best_reasons = None, float('-inf'), []
        attempts = []
        for attempt in range(max_attempts):
            seed = int(story.get('image_seed_base', 7300)) + i + attempt * 1009
            image = pipe(prompt=prompt, num_inference_steps=steps, guidance_scale=guidance,
                         height=height, width=width,
                         generator=torch.Generator('cpu').manual_seed(seed)).images[0]
            if paths:
                with Image.open(paths[-1]) as prev:
                    score, reasons = assess_image(image, prev)
            else:
                score, reasons = assess_image(image)
            attempts.append({'seed': seed, 'score': score, 'reasons': reasons})
            if score > best_score:
                best_image, best_score, best_reasons = image, score, reasons
            if not reasons:
                break
            print(f'Imagen {i + 1}: intento {attempt + 1} rechazado '
                  f'({", ".join(reasons)}); regenerando', flush=True)
        if best_reasons:
            # Do not silently publish an objectively defective frame.
            raise RuntimeError(f'Imagen {i + 1} sin candidato válido tras '
                               f'{max_attempts} intentos: {best_reasons}')
        path = out / f'scene_{i:02}.png'
        best_image.save(path)
        report.append({'scene': i + 1, 'attempts': attempts,
                       'accepted_score': best_score})
        print(f'Imagen: {i + 1}/{len(story["scenes"])} '
              f'({time.monotonic() - scene_start:.1f}s; '
              f'{len(attempts)} intento(s))', flush=True)
        paths.append(path)
    (out / 'image_quality_report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'UMBRAL_IMAGE_TOTAL_SECONDS={time.monotonic() - total_start:.1f}', flush=True)
    return paths



def scene_boundaries_from_cues(cues, branding, count):
    """Align scene transitions to narrated story cues, not arbitrary video time."""
    if count < 1:
        raise ValueError('No hay escenas')
    start, end = float(branding['intro_end']), float(branding['outro_start'])
    story_cues = [(float(a), float(b), text) for a, b, text in cues
                  if a >= start - 0.02 and b <= end + 0.02 and text.strip()]
    if not story_cues:
        return [start + (end - start) * i / count for i in range(count + 1)]
    weights = [max(1, len(text.split())) for _, _, text in story_cues]
    total = sum(weights)
    boundaries = [start]
    for index in range(1, count):
        target = total * index / count
        running = 0
        chosen = None
        for (a, b, _), weight in zip(story_cues, weights):
            if running + weight >= target:
                fraction = (target - running) / weight
                chosen = a + (b - a) * fraction
                break
            running += weight
        boundaries.append(max(boundaries[-1] + 0.001, min(end - 0.001, chosen if chosen is not None else end)))
    return boundaries + [end]


def encode(out, images, duration, outfile, branding=None, cues=None, music_gain=1.0):
    if type(music_gain) not in (int, float) or music_gain not in (1.0, 0.85):
        raise ValueError('Perfil de mezcla no autorizado')
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
        bounds = (scene_boundaries_from_cues(cues, branding, len(images))
                  if cues else [intro_end + (outro_start - intro_end) * i / len(images)
                                for i in range(len(images) + 1)])
        timeline = ([(intro, intro_end)]
                    + [(img, bounds[i + 1] - bounds[i]) for i, img in enumerate(images)]
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
    af = (f"[1:a]volume=1[voice];[2:a]volume={music_gain:g}[music];"
          "[voice][music]amix=inputs=2:duration=first:normalize=0,"
          "alimiter=limit=0.92[mixed]")
    run('ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat',
        '-safe', '1', '-i', 'scenes.txt', '-i', 'voice.wav',
        '-i', 'music.wav', *animated_inputs,
        '-filter_complex', vf + ';' + af,
        '-map', '[v]', '-map', '[mixed]', '-t', f'{duration:.6f}',
        '-c:v', 'libx264', '-threads', '2', '-preset', os.getenv('UMBRAL_ENCODE_PRESET', 'superfast'), '-crf', '22',
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
        if not isinstance(story.get('narration'), str) or not story['narration'].strip():
            raise ValueError('Narración vacía o inválida: ' + str(story.get('title')))
        if ' '.join(story['narration'].split()) != story['narration']:
            raise ValueError('La narración contiene saltos o espacios no normalizados: ' + str(story.get('title')))
        if not isinstance(story.get('scenes'), list) or not all(isinstance(s, str) and s.strip() for s in story['scenes']):
            raise ValueError('Escenas vacías o inválidas: ' + str(story.get('title')))
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
            if (episode is None and os.getenv('UMBRAL_DYNAMIC_EPISODES') != '1') or len(story['scenes']) != 6:
                raise ValueError('Un episodio diario necesita número fijo y seis escenas')
        if story.get('test_date') and story.get('publish_date'):
            raise ValueError('Un episodio de prueba no debe ocupar una fecha diaria')
    return stories


def render():
    date = dt.date.fromisoformat(os.getenv('UMBRAL_DATE', dt.datetime.now(ZoneInfo('Europe/Madrid')).date().isoformat()))
    morning = os.getenv('UMBRAL_SLOT') == '09'
    stories = load_stories()
    if morning:
        morning_file = BASE / 'stories_morning.json'
        stories = json.loads(morning_file.read_text(encoding='utf-8'))
        if not isinstance(stories, list):
            raise ValueError('Archivo de historias matinales inválido')
    daily = next((s for s in stories if s.get('publish_date') == date.isoformat()), None)
    test_title = os.getenv('UMBRAL_STORY_TITLE', '')
    replacement_file = os.getenv('UMBRAL_REPLACEMENT_STORY_FILE', '')
    if replacement_file:
        if replacement_file != 'stories/replacement_latest_2026-11-17.json' or test_title:
            raise ValueError('Ruta de sustitución no autorizada')
        story = json.loads((BASE / replacement_file).read_text(encoding='utf-8'))
        story = {**story, 'episode_number': 8}
        if story.get('publish_date') or len(story.get('scenes', [])) != 6 or not 140 <= len(story.get('narration','').split()) <= 170:
            raise ValueError('Relato de sustitución inválido')
    elif test_title:
        # Test autorizado de una sola vez; no puede reemplazar el Reel diario.
        authorized_tests = {
            'cinematic-episode-6': ('La luz del rellano', 6),
            'cinematic-episode-7': ('El maniquí del escaparate', 7),
        }
        expected = authorized_tests.get(os.getenv('UMBRAL_TEST_MODE'))
        if expected is None or test_title != expected[0]:
            raise ValueError('Selección de relato de prueba no autorizada')
        test_story = next((s for s in stories if s['title'] == test_title), None)
        if test_story is None or test_story.get('episode_number') != expected[1]:
            raise ValueError('Relato de prueba no disponible o fecha incorrecta')
        # A test gets a dated output ONLY in the artifact, not in the production queue.
        story = {**test_story, 'publish_date': date.isoformat()}
    else:
        if os.getenv('UMBRAL_REQUIRE_DATED_STORY') == '1' and daily is None:
            raise ValueError('Falta un relato original fechado para ' + date.isoformat())
        story = daily if daily is not None else stories[(date - dt.date(2026, 11, 15)).days % len(stories)]
    active_profile = None
    if (os.getenv('UMBRAL_DYNAMIC_EPISODES') == '1' and daily is not None
            and not test_title and not replacement_file):
        from scripts.episode_state import planned_episode
        story = {**story, 'episode_number': planned_episode(
            date.isoformat(), '09' if morning else '21', BASE,
            anticipate_morning=os.getenv('UMBRAL_ANTICIPATE_MORNING') == '1')}
        from scripts.technical_learning import load_profile
        active_profile = load_profile(date.isoformat(), '09' if morning else '21', BASE)
        story['technical_profile'] = active_profile
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
    # Lightweight visual QA: a single contact sheet makes it easy to inspect
    # all six generated scenes without downloading large intermediate PNGs.
    from PIL import Image, ImageOps, ImageDraw
    thumb_w, thumb_h, gap = 192, 320, 12
    sheet = Image.new('RGB', (3 * thumb_w + 4 * gap, 2 * thumb_h + 3 * gap), '#111111')
    for idx, scene_path in enumerate(images[:6]):
        with Image.open(scene_path) as src:
            tile = ImageOps.fit(src.convert('RGB'), (thumb_w, thumb_h))
        x = gap + (idx % 3) * (thumb_w + gap)
        y = gap + (idx // 3) * (thumb_h + gap)
        sheet.paste(tile, (x, y))
    sheet.save(OUT / 'scene_contact_sheet.jpg', quality=85, optimize=True)
    # Cover is a distinct downloadable JPEG. Brand cards are original
    # graphics; they NEVER reuse any generated story scene.
    from scripts.thumbnail import make_thumbnail
    from scripts.brand_cards import make_brand_cards
    make_thumbnail(story, images, OUT / 'cover.jpg')
    make_brand_cards(story, OUT)
    (OUT / 'brand_story.json').write_text(json.dumps(story, ensure_ascii=False))
    timing = json.loads((OUT / 'branding_timing.json').read_text(encoding='utf-8'))
    illustrated = time.monotonic()
    outfile = OUT / f'umbral_{date:%Y%m%d}{"_09" if morning else ""}.mp4'
    if active_profile is None:
        encode(OUT, images, duration, outfile, branding=timing, cues=cues)
    else:
        encode(OUT, images, duration, outfile, branding=timing, cues=cues,
               music_gain=active_profile['music_gain'])
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
