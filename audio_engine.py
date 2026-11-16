"""UMBRAL: natural narration and original, copyright-safe dark-ambient scoring."""
import os
import re
import json
from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 24000


def speech_units(text):
    """Narrate whole sentences to preserve prosody; split only exceptionally long ones."""
    text = re.sub(r'([.!?…][»”"]?)\s+', r'\1\n', text.strip())
    result = []
    for sentence in (s.strip() for s in text.split('\n') if s.strip()):
        if len(sentence.split()) <= 32:
            result.append(sentence)
            continue
        chunks = re.split(r'(?<=[,;:])\s+', sentence)
        current = []
        for chunk in chunks:
            if current and len(' '.join(current + [chunk]).split()) > 25:
                result.append(' '.join(current))
                current = []
            current.append(chunk)
        if current:
            result.append(' '.join(current))
    return result


def text_cues(unit, audio, start_s, split_phrases):
    """Estimate subtitle positions within a fully narrated sentence.
    
    Kokoro has no word-level forced alignment: use syllable/length estimates
    and detect voiced start/end. The audio is never split for captions.
    """
    phrases = split_phrases(unit)
    if not phrases:
        return []
    n = len(audio)
    if not n:
        raise ValueError('Audio de voz vacío')
    voiced_start, voiced_end = 0, n
    hop = 240
    count = n // hop
    if count > 8:
        rms = np.sqrt(np.mean(audio[:count * hop].reshape(count, hop).astype(np.float64) ** 2, axis=1))
        threshold = max(0.003, float(rms.max()) * 0.075)
        active = np.flatnonzero(rms >= threshold)
        if active.size > 3:
            voiced_start = max(0, int(active[0]) * hop - 240)
            voiced_end = min(n, (int(active[-1]) + 1) * hop + 240)
    weights = np.array([sum(max(2, len(w.strip('.,;:!?¿¡«»"')) + 1)
                            for w in p.split()) for p in phrases], dtype=float)
    boundaries = np.r_[0.0, np.cumsum(weights / max(weights.sum(), 1.0))]
    return [(start_s + (voiced_start + (voiced_end - voiced_start) * boundaries[i]) / RATE,
             start_s + (voiced_start + (voiced_end - voiced_start) * boundaries[i + 1]) / RATE,
             phrase) for i, phrase in enumerate(phrases)]


def generate_narration(text, out, split_phrases, pipeline=None):
    """Synthesise one whole sentence per TTS request and retain short natural pauses."""
    import torch
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    if pipeline is None:
        from kokoro import KPipeline
        pipeline = KPipeline(lang_code='e', repo_id='hexgrad/Kokoro-82M', device='cpu')
    speed = float(os.getenv('UMBRAL_SPEED', '1.08'))
    if not 0.75 <= speed <= 1.25:
        raise ValueError('Velocidad de voz fuera del rango permitido')
    parts, cues, cursor = [], [], 0
    units = speech_units(text)
    for i, unit in enumerate(units):
        generated = [sample.cpu().numpy() for _, _, sample in pipeline(
            unit, voice='em_alex', speed=speed) if sample is not None]
        if not generated:
            raise RuntimeError('Kokoro no ha generado audio para una frase')
        audio = np.concatenate(generated).astype(np.float32)
        cues.extend(text_cues(unit, audio, cursor / RATE, split_phrases))
        parts.append(audio)
        cursor += audio.size
        # Speech carries its own punctuation; never pause at caption boundaries.
        pause_s = 0.25 if unit.rstrip('»”"').endswith(('.', '!', '?', '…')) else 0.09
        if i == len(units) - 1:
            pause_s = 0.35
        silence = np.zeros(round(RATE * pause_s), dtype=np.float32)
        parts.append(silence)
        cursor += silence.size
        print(f'Voz natural: {i + 1}/{len(units)} frases', flush=True)
    if not parts:
        raise ValueError('Texto narrado vacío')
    sf.write(Path(out) / 'voice.wav', np.concatenate(parts), RATE)
    return cues, cursor / RATE


def generate_ambient_score(duration, cues, out, seed=7300):
    """Original evolving ominous score; automatically ducks during narration."""
    if duration <= 0:
        raise ValueError('La música necesita una duración positiva')
    n = int(round(RATE * duration))
    t = np.arange(n, dtype=np.float32) / RATE
    rng = np.random.default_rng(seed)
    slow = 0.6 + 0.4 * np.sin(2 * np.pi * t / 31.0 - 1.3) ** 2
    bass = (0.045 * np.sin(2 * np.pi * 55.0 * t + 0.23 * np.sin(2 * np.pi * 0.11 * t))
            + 0.020 * np.sin(2 * np.pi * 58.27 * t + 0.14 * np.sin(2 * np.pi * 0.065 * t)))
    harmony = np.zeros(n, dtype=np.float32)
    for i, note in enumerate([110.0, 130.81, 164.81, 146.83, 130.81, 98.0]):
        envelope = np.maximum(0, np.sin(np.pi * (t / 20.0 - i / 2.7))) ** 4
        harmony += (0.018 * envelope * np.sin(2 * np.pi * note * t + i * 1.2)).astype(np.float32)
    raw = rng.standard_normal(n).astype(np.float32)
    width = 401
    integral = np.cumsum(np.pad(raw, (width, 0)), dtype=np.float64)
    noise = ((integral[width:] - integral[:-width]) / width).astype(np.float32)
    phase = np.mod(t, 6.5)
    pulse = (0.017 * np.exp(-phase * 4.0) * np.sin(2 * np.pi * 47.0 * t)).astype(np.float32)
    music = (bass * slow + harmony + noise * 0.032 + pulse).astype(np.float32)
    gain = np.full(n, 0.62, dtype=np.float32)
    for start, end, _ in cues:
        gain[max(0, int((start - .16) * RATE)):min(n, int((end + .22) * RATE))] = 0.37
    small_gain = np.convolve(gain[::120], np.ones(19, dtype=np.float32) / 19, 'same')
    gain = np.interp(np.arange(n, dtype=np.float32),
                     np.arange(small_gain.size) * 120, small_gain).astype(np.float32)
    fade = np.minimum(1.0, t / 2.2) * np.minimum(1.0, np.maximum(0.0, duration - t) / 2.2)
    music *= gain * fade.astype(np.float32)
    dest = Path(out) / 'music.wav'
    sf.write(dest, music, RATE)
    return dest


def generate_branded_narration(intro, story, outro, out, split_phrases, pipeline=None):
    """Intro/outro lowered by ~3 semitones; story waveform is NOT pitch-shifted.

    A single Kokoro pipeline is reused for all three segments to keep CPU cost down.
    Each segment is synthesised as normal Spanish speech; FFmpeg only processes
    the opening and closing sections. Cue offsets are adjusted to actual samples.
    """
    import subprocess
    import tempfile

    if pipeline is None:
        import torch
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        from kokoro import KPipeline
        pipeline = KPipeline(lang_code='e', repo_id='hexgrad/Kokoro-82M', device='cpu')

    # 20000/24000 = 0.8333, equivalent to approximately -3.2 semitones.
    # atempo counters the speed change so the opening and close remain brisk.
    deep_filter = "asetrate=20000,aresample=24000,atempo=1.2"
    blocks, cues, cursor = [], [], 0
    timing = {}
    with tempfile.TemporaryDirectory(prefix="umbral-voice-") as tmp:
        for key, text in (("intro", intro), ("story", story), ("outro", outro)):
            segment_start = cursor / RATE
            segment = Path(tmp) / key
            segment.mkdir()
            part_cues, original_duration = generate_narration(
                text, segment, split_phrases, pipeline=pipeline)
            src = segment / 'voice.wav'
            final_path = src
            if key != "story":
                final_path = segment / 'lowered.wav'
                subprocess.run([
                    'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-i', str(src), '-af', deep_filter,
                    '-ar', str(RATE), '-ac', '1', str(final_path)
                ], check=True)
            audio, sample_rate = sf.read(final_path, dtype='float32')
            if sample_rate != RATE or audio.ndim != 1 or audio.size == 0:
                raise ValueError('Audio de marca incompatible')
            new_duration = audio.size / RATE
            ratio = new_duration / original_duration
            cues.extend((cursor / RATE + a * ratio,
                         cursor / RATE + b * ratio, phrase)
                        for a, b, phrase in part_cues)
            blocks.append(audio)
            cursor += audio.size
            voice_end = cursor / RATE
            if key != "outro":
                pause = np.zeros(round(RATE * (0.50 if key == "intro" else 0.75)),
                                 dtype=np.float32)
                blocks.append(pause)
                cursor += pause.size
            timing[key] = {'start': segment_start,
                           'voice_end': voice_end,
                           'end': cursor / RATE}
    Path(out).mkdir(parents=True, exist_ok=True)
    sf.write(Path(out) / 'voice.wav', np.concatenate(blocks), RATE)
    boundaries = {'intro_end': timing['intro']['end'],
                  'outro_start': timing['outro']['start'],
                  'duration': cursor / RATE,
                  'sections': timing}
    if not (0 < boundaries['intro_end'] < boundaries['outro_start']
            < boundaries['duration']):
        raise ValueError('Marcadores intro, relato y outro incompatibles')
    (Path(out) / 'branding_timing.json').write_text(
        json.dumps(boundaries, indent=2), encoding='utf-8')
    return cues, cursor / RATE
