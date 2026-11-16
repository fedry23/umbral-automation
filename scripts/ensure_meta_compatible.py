#!/usr/bin/env python3
"""Validate an actual MP4 file against the conservative Meta Instagram Reels profile.

If the only issue is audio sample rate/channels, fix the existing audio with
FFmpeg without re-encoding the H.264 video. Fail closed for unexpected video.
"""
import json
from pathlib import Path
import subprocess
import sys


def probe(path):
    return json.loads(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format',
         '-of', 'json', str(path)], text=True))


def verify(path, allow_audio_fix=True):
    path = Path(path)
    if not path.is_file():
        raise ValueError('No existe el MP4 del Reel')
    info = probe(path)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    audio = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
    if not video or not audio:
        raise ValueError('Meta requiere pista de vídeo y de audio')
    if video.get('codec_name') != 'h264' or video.get('pix_fmt') != 'yuv420p':
        raise ValueError('Meta requiere vídeo H.264 yuv420p')
    if (video.get('width'), video.get('height')) != (720, 1280):
        raise ValueError('Resolución inesperada; se exige 720×1280 (9:16)')
    n, d = map(int, video.get('avg_frame_rate', '0/1').split('/'))
    if not d or not 23 <= n / d <= 60:
        raise ValueError('Los Reels deben tener 23–60 fps')
    seconds = float(info['format'].get('duration', 0))
    if not 3 <= seconds <= 180:
        raise ValueError('Duración del Reel fuera del rango operativo 3–180 segundos')
    if path.stat().st_size > 300 * 1024 * 1024:
        raise ValueError('Vídeo demasiado grande (>300 MiB)')
    if audio.get('codec_name') != 'aac':
        raise ValueError('Meta requiere audio AAC')
    need_fix = audio.get('sample_rate') != '48000' or audio.get('channels') not in (1, 2)
    if need_fix:
        if not allow_audio_fix:
            raise ValueError('AAC incorrecto: debe tener 48 kHz y 1 o 2 canales')
        tmp = path.with_name(path.stem + '_meta_fixed.mp4')
        try:
            subprocess.run([
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                '-i', str(path), '-map', '0:v:0', '-map', '0:a:0',
                '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000',
                '-ac', '2', '-b:a', '128k', '-movflags', '+faststart',
                str(tmp)], check=True)
            verify(tmp, allow_audio_fix=False)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
    print('META_COMPATIBLE: H.264 720×1280 yuv420p, AAC 48 kHz, FPS válido y MP4 comprobado')
    return True


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Uso: ensure_meta_compatible.py VIDEO.mp4')
    verify(sys.argv[1])
