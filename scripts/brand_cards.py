#!/usr/bin/env python3
"""UMBRAL: two genuinely separate cinematic brand screens.

Creates dedicated stills for the opening and the ending; never uses any
story illustration for these segments. Deterministic, offline, free.
"""
from functools import lru_cache
from pathlib import Path
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SIZE = (512, 896)
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


@lru_cache(maxsize=64)
def font(size, bold=True):
    return ImageFont.truetype(BOLD if bold else NORMAL, size)


def background(kind, episode):
    w, h = SIZE
    y, x = np.mgrid[:h, :w]
    nx = (x - w / 2) / w
    ny = (y - h / 2) / h
    radial = np.clip(1 - np.sqrt((nx * 1.45) ** 2 + (ny * 1.15) ** 2), 0, 1)
    noise = np.random.default_rng(4900 + episode).normal(0, 2.7, (h, w))
    if kind == 'intro':
        # Burgundy-black stage, with a red glow behind a dark arch.
        glow = np.exp(-((nx / .37) ** 2 + ((ny + .10) / .32) ** 2) * 2)
        r = 9 + 32 * glow + 7 * radial + noise
        g = 8 + 5 * glow + 4 * radial + noise * .35
        b = 15 + 7 * glow + 6 * radial + noise * .45
    else:
        # Slate-blue-black, distinct from the red opening and every story scene.
        beam = np.exp(-((nx / .14) ** 2 + ((ny - .03) / .42) ** 2) * 1.8)
        r = 6 + 8 * beam + 3 * radial + noise * .38
        g = 12 + 18 * beam + 3 * radial + noise * .48
        b = 21 + 36 * beam + 4 * radial + noise * .63
    arr = np.stack([r, g, b], axis=-1)
    return Image.fromarray(np.clip(arr, 0, 255).astype('uint8'), 'RGB')


def centered(draw, text, y, style, color, outline=0):
    w = draw.textbbox((0, 0), text, font=style, stroke_width=outline)[2]
    draw.text((SIZE[0] / 2 - w / 2, y), text, font=style, fill=color,
              stroke_width=outline, stroke_fill=(5, 5, 11))


def fit_title(draw, text, max_width=442, max_lines=3):
    words = text.upper().split()
    for size in range(58, 27, -2):
        style = font(size)
        lines, current = [], ''
        for word in words:
            candidate = (current + ' ' + word).strip()
            if draw.textbbox((0, 0), candidate, font=style)[2] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        if (len(lines) <= max_lines and all(
                draw.textbbox((0, 0), z, font=style)[2] <= max_width
                for z in lines)):
            return style, lines
    raise ValueError('Título demasiado largo para intro de UMBRAL')


def make_brand_cards(story, out):
    episode = story.get('episode_number')
    if not isinstance(episode, int) or isinstance(episode, bool) or episode < 1:
        raise ValueError('Número de episodio inválido para tarjetas de marca')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    red = (212, 41, 58)
    white = (240, 231, 232)

    intro = background('intro', episode)
    d = ImageDraw.Draw(intro)
    # Recognisable red threshold, no image from the episode.
    for i in range(8):
        thick = 4 if i == 0 else 2
        d.arc((105 - i * 3, 185 - i * 3, 407 + i * 3, 600 + i * 2),
              186, 354, fill=(max(45, 168 - i * 17), 20, 35), width=thick)
        d.line((105 - i * 3, 420, 105 - i * 3, 610),
               fill=(max(38, 155 - i * 15), 15, 27), width=thick)
        d.line((407 + i * 3, 420, 407 + i * 3, 610),
               fill=(max(38, 155 - i * 15), 15, 27), width=thick)
    d.rectangle((123, 476, 389, 610), fill=(12, 7, 15))
    centered(d, 'UMBRAL', 97, font(67), white)
    centered(d, 'HISTORIA N.º ' + str(episode).zfill(2), 206,
             font(27), (239, 105, 117))
    title_font, title_lines = fit_title(d, str(story.get('title', '')))
    line_h = title_font.size + 13
    first_y = 470 - (len(title_lines) - 1) * line_h / 2
    for i, line in enumerate(title_lines):
        centered(d, line, first_y + i * line_h, title_font, white, outline=2)
    d.line((172, 720, 340, 720), fill=red, width=4)
    centered(d, 'UN RELATO DE TERROR', 741, font(21, False), (195, 165, 169))
    intro_path = out / 'intro_card.png'
    intro.save(intro_path)

    outro = background('outro', episode)
    d = ImageDraw.Draw(outro)
    # Cold, ajar door with a narrow shaft of light, versus intro's red arch.
    d.polygon([(126, 120), (377, 121), (377, 741), (126, 741)],
              fill=(15, 19, 31), outline=(60, 74, 92), width=4)
    d.polygon([(312, 129), (357, 144), (357, 714), (312, 731)],
              fill=(62, 93, 122))
    d.polygon([(313, 139), (342, 149), (342, 711), (313, 725)],
              fill=(151, 175, 185))
    d.ellipse((274, 443, 289, 458), fill=(179, 184, 192))
    d.rectangle((70, 260, 444, 615), fill=(8, 13, 23))
    centered(d, 'HAS CRUZADO', 319, font(36), white)
    centered(d, 'EL UMBRAL', 370, font(50), white)
    d.line((171, 463, 341, 463), fill=(102, 142, 177), width=3)
    centered(d, 'NO MIRES ATRÁS', 493, font(30), (196, 211, 224))
    centered(d, '@UMBRAL.TERROR', 760, font(20, False), (162, 183, 200))
    outro_path = out / 'outro_card.png'
    outro.save(outro_path)
    for path in (intro_path, outro_path):
        with Image.open(path) as check:
            if check.size != SIZE or check.mode != 'RGB':
                raise RuntimeError('Formato de tarjeta de marca incorrecto')
    print('TARJETAS_UMBRAL_OK: apertura roja y cierre azul independientes', flush=True)
    return intro_path, outro_path
