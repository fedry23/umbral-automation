#!/usr/bin/env python3
"""Wait for exact daily public video on GitHub Pages; ensure bytes match."""
import datetime as dt
import hashlib
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo


def stream_digest(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(chunk)
    return digest.digest()


def file_digest(path):
    with path.open('rb') as stream:
        return stream_digest(stream)


def check_remote(path, url, local_hash=None):
    local_hash = local_hash if local_hash is not None else file_digest(path)
    request = urllib.request.Request(
        url, headers={"User-Agent": "UMBRAL-Pages-publisher"})
    try:
        with urllib.request.urlopen(request, timeout=55) as f:
            if f.headers.get("Content-Type", "").lower().startswith("text/html"):
                return False
            remote_hash = stream_digest(f)
        return remote_hash == local_hash
    except (urllib.error.URLError, TimeoutError):
        return False


def main():
    date = dt.datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    path = Path(os.getenv("UMBRAL_VIDEO_FILE", "docs/reels/" + date + ".mp4"))
    if not path.is_file() or path.suffix.lower() != ".mp4":
        raise RuntimeError("Falta el vídeo MP4 previsto en GitHub Pages")
    url = os.getenv("UMBRAL_VIDEO_URL",
                    "https://fedry23.github.io/umbral-automation/reels/" + date + ".mp4")
    if not url.startswith("https://fedry23.github.io/umbral-automation/reels/"):
        raise ValueError("URL del Reel fuera del sitio oficial de GitHub Pages")
    cover_required = os.getenv("UMBRAL_COVER_REQUIRED") == "1"
    cover_path = Path(os.getenv("UMBRAL_COVER_FILE",
                             "docs/reels/" + date + ".jpg"))
    cover_url = os.getenv("UMBRAL_COVER_URL",
                        "https://fedry23.github.io/umbral-automation/reels/"
                        + date + ".jpg")
    if cover_required:
        if not cover_path.is_file():
            raise RuntimeError("Falta portada del día; no se publica sin cover")
        if not cover_url.startswith("https://fedry23.github.io/umbral-automation/reels/"):
            raise ValueError("La portada debe estar en GitHub Pages oficial")
    video_hash = file_digest(path)
    cover_hash = file_digest(cover_path) if cover_required else None
    video_ready, cover_ready = False, not cover_required
    for _ in range(60):
        if not video_ready:
            video_ready = check_remote(path, url, video_hash)
        if not cover_ready:
            cover_ready = check_remote(cover_path, cover_url, cover_hash)
        if video_ready and cover_ready:
            print("GitHub Pages listo; SHA256 del vídeo"
                  + (" y portada" if cover_required else "") + " comprobado")
            Path("staged").mkdir(exist_ok=True)
            (Path("staged") / "public_video_url.txt").write_text(url)
            if cover_required:
                (Path("staged") / "public_cover_url.txt").write_text(cover_url)
            return
        time.sleep(12)
    raise RuntimeError("GitHub Pages no ofreció los archivos exactos (MP4/JPEG); no publicar")


if __name__ == "__main__":
    main()
