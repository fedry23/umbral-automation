"""Original UMBRAL horror score: audible, melodic, copyright-safe, CPU-only."""
from pathlib import Path
import numpy as np
import soundfile as sf

RATE = 24000


def generate_ambient_score(duration, cues, out, seed=7300):
    """Original minor-key drones, strings, music-box notes and cinematic pulses.

    Keeps a recognisable melody beneath the narrator, avoids copyrighted samples.
    """
    if duration <= 0:
        raise ValueError('La música necesita una duración positiva')
    n = round(duration * RATE)
    t = np.arange(n, dtype=np.float64) / RATE
    rng = np.random.default_rng(seed)
    score = np.zeros(n, dtype=np.float64)

    # Distant ominous strings, two bass pitches beating against each other.
    score += 0.41 * np.sin(2 * np.pi * 55.0 * t
                           + 0.3 * np.sin(2 * np.pi * 0.12 * t))
    score += 0.20 * np.sin(2 * np.pi * 56.2 * t) * (
        0.75 + 0.25 * np.sin(2 * np.pi * 0.027 * t))
    score += 0.09 * np.sin(2 * np.pi * 110.0 * t)

    # A progression of invented minor/diminished harmonies, smoothly fading.
    chords = [(110.0, 130.81, 164.81), (87.31, 103.83, 138.59),
              (73.42, 87.31, 116.54), (82.41, 98.0, 123.47)]
    for j in range(int(np.ceil(duration / 16.0)) + 1):
        left, right = j * 16.0, min(duration, (j + 1) * 16.0 + 2.0)
        if left >= duration:
            break
        a, b = int(left * RATE), min(n, int(right * RATE))
        tt = t[a:b] - left
        envelope = np.clip(tt / 2.5, 0, 1) * np.clip(
            (right - left - tt) / 2.5, 0, 1)
        for k, f in enumerate(chords[j % len(chords)]):
            score[a:b] += envelope * (0.16 - 0.025 * k) * (
                np.sin(2 * np.pi * f * t[a:b] + k * 0.5)
                + 0.16 * np.sin(2 * np.pi * 2 * f * t[a:b]))

    # Audible, unsettling original music-box / distant piano motif with echo.
    motif = [392.0, 349.23, 415.30, 293.66, 311.13, 261.63, 349.23, 246.94]
    for j, when in enumerate(np.arange(1.5, duration, 3.9)):
        for delay, echo_gain in [(0.0, 1.0), (0.38, 0.30), (0.83, 0.12)]:
            start = when + delay
            if start >= duration:
                continue
            a = round(start * RATE)
            b = min(n, a + int(2.9 * RATE))
            tt = np.arange(b - a, dtype=np.float64) / RATE
            envelope = (1 - np.exp(-tt / 0.016)) * np.exp(-tt / 1.15)
            f = motif[j % len(motif)]
            bell = (np.sin(2 * np.pi * f * tt)
                    + 0.38 * np.sin(2 * np.pi * 2.01 * f * tt)
                    + 0.14 * np.sin(2 * np.pi * 3.03 * f * tt))
            score[a:b] += 0.32 * echo_gain * envelope * bell

    # Soft distant cinematic pulses and filtered room noise.
    for when in np.arange(6.0, duration, 7.3):
        a = int(when * RATE)
        b = min(n, a + int(1.15 * RATE))
        tt = np.arange(b - a, dtype=np.float64) / RATE
        score[a:b] += (0.19 + 0.12 * when / duration) * np.exp(-tt * 6) * (
            np.sin(2 * np.pi * (47 - 8 * tt) * tt)
            + 0.28 * np.sin(2 * np.pi * 94 * tt))
    raw = rng.normal(size=n).astype(np.float32)
    window = 53
    csum = np.cumsum(np.pad(raw, (window, 0)), dtype=np.float64)
    filtered = (csum[window:] - csum[:-window]) / window
    score += 0.29 * filtered * np.sin(2 * np.pi * 0.045 * t) ** 2
    score *= 0.83 + 0.28 * t / max(duration, 1.0)

    # Duck the score under speech, smoothly restoring it between phrases.
    gain = np.full(n, 0.9, dtype=np.float32)
    for start, end, _ in cues:
        a = max(0, round((start - 0.09) * RATE))
        b = min(n, round((end + 0.16) * RATE))
        gain[a:b] = 0.71
    block = 240
    sampled = gain[::block]
    smoothed = np.convolve(
        sampled, np.ones(25, dtype=np.float32) / 25, mode='same')
    gain = np.interp(np.arange(n), np.arange(len(smoothed)) * block,
                     smoothed).astype(np.float32)
    fade = np.minimum(1.0, t / 1.6) * np.minimum(
        1.0, np.maximum(0.0, duration - t) / 2.0)
    score *= fade * gain

    # Target -29.5 dBFS RMS, audible on phone speakers under -26.5 dB speech.
    rms = float(np.sqrt(np.mean(score ** 2)))
    if rms < 1e-7:
        raise RuntimeError('La pista musical está en silencio')
    score *= 10 ** (-29.5 / 20) / rms
    peak = float(np.max(np.abs(score)))
    if peak > 0.32:
        score *= 0.32 / peak
    dest = Path(out) / 'music.wav'
    sf.write(dest, score.astype(np.float32), RATE)
    return dest
