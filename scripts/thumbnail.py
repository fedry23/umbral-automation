#!/usr/bin/env python3
"""UMBRAL: original, consistently branded, Instagram-ready Reel cover.

Composites an already generated scene from this episode; no paid services,
third-party images, external network calls or additional AI inference.
Keeps essential wording inside Instagram's square centre-grid crop.
"""
from pathlib import Path
import math
import textwrap
import unicodedata

from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, HEIGHT = 1080, 1920
MAX_BYTES = 8_000_000
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _font(bold, size):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def _lines(draw, text, font, maximum, max_lines=3):
    """Word-wrap without cutting words and reject headings that cannot fit."""
    words = text.strip().split()
    if not words:
        raise ValueError("El título de UMBRAL está vacío")
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= maximum:
            current = candidate
        else:
            if not current:
                return None
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines if len(lines) <= max_lines else None


def _center_text(draw, y, text, font, fill, spacing=4, stroke_width=0):
    bounds = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    w = bounds[2] - bounds[0]
    draw.text((WIDTH // 2 - w // 2, y), text, font=font, fill=fill,
              stroke_width=stroke_width, stroke_fill=(9, 8, 13), spacing=spacing)


def make_thumbnail(story, images, destination):
    """Build 1080×1920 JPEG. Returns absolute file Path after validation."""
    episode = story.get("episode_number")
    title = str(story.get("title", "")).strip()
    if not isinstance(episode, int) or isinstance(episode, bool) or episode < 1:
        raise ValueError("Número de episodio obligatorio en la portada")
    if not title or len(title) > 85:
        raise ValueError("Título inválido para una miniatura legible")
    files = [Path(p) for p in images]
    if not files or not all(f.is_file() for f in files):
        raise ValueError("Faltan imágenes de la historia para crear la portada")

    # Prefer a central action shot for regular episodes. Editors can choose
    # a stronger scene explicitly (e.g. episode 6 needs the first shot).
    index = story.get('cover_scene_index', len(files) // 2)
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(files):
        raise ValueError('cover_scene_index fuera de rango')
    source = files[index]
    with Image.open(source) as base:
        bg = ImageOps.fit(base.convert("RGB"), (WIDTH, HEIGHT),
                          method=Image.Resampling.LANCZOS,
                          centering=(0.5, 0.5))

    # Dark translucent gradient: important typography remains high contrast.
    opacity = Image.new("L", (1, HEIGHT))
    values = []
    for y in range(HEIGHT):
        focus = math.exp(-((y - 975) / 600) ** 2)
        values.append(min(225, round(65 + 95 * focus + 15 * (y / HEIGHT))))
    opacity.putdata(values)
    opacity = opacity.resize((WIDTH, HEIGHT))
    darkness = Image.new("RGB", (WIDTH, HEIGHT), (8, 6, 13))
    image = Image.composite(darkness, bg, opacity)
    d = ImageDraw.Draw(image)

    # All important text sits in the centre square (y=420..1500).
    # Thus the same cover works in 9:16 Reels and cropped profile grid.
    cx = WIDTH // 2
    d.rounded_rectangle((cx - 65, 545, cx + 65, 550), radius=3, fill=(188, 24, 44))
    _center_text(d, 575, "UMBRAL", _font(True, 90), (245, 237, 236), stroke_width=1)
    _center_text(d, 697, f"HISTORIA N.º {episode:02d}", _font(True, 36), (233, 108, 119))

    title_lines = None
    font = None
    for sz in range(91, 50, -3):
        f = _font(True, sz)
        result = _lines(d, title.upper(), f, WIDTH - 145, max_lines=3)
        if result:
            title_lines, font = result, f
            break
    if title_lines is None:
        raise ValueError("Título demasiado largo para la miniatura")

    advance = font.size + 20
    start = 945 - (len(title_lines) * advance) // 2
    for i, line in enumerate(title_lines):
        _center_text(d, start + i * advance, line, font, (255, 253, 249),
                     stroke_width=2)
    d.line((350, 1185, 730, 1185), fill=(170, 43, 57), width=3)
    _center_text(d, 1215, "NO MIRES ATRÁS", _font(False, 30), (218, 201, 204))
    # Atmospheric footer (outside central crop; title remains unaffected).
    _center_text(d, 1710, "@UMBRAL.TERROR", _font(True, 29), (193, 184, 189))

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="JPEG", quality=89, optimize=True,
               progressive=False, subsampling=0)
    with Image.open(destination) as check:
        if (check.format != "JPEG" or check.mode != "RGB"
                or check.size != (WIDTH, HEIGHT)):
            raise RuntimeError("La miniatura no cumple JPEG RGB 1080x1920")
        check.verify()
    if destination.stat().st_size > MAX_BYTES:
        raise ValueError("Miniatura demasiado grande para Instagram")
    print(f"PORTADA_UMBRAL_OK: historia {episode}, {title}, {destination}", flush=True)
    return destination
