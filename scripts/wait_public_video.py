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


def check_remote(path, url):
    local_hash = hashlib.sha256(path.read_bytes()).digest()
    request = urllib.request.Request(
        url, headers={"User-Agent": "UMBRAL-Pages-publisher"})
    try:
        with urllib.request.urlopen(request, timeout=55) as f:
            if f.headers.get("Content-Type", "").lower().startswith("text/html"):
                return False
            remote_hash = hashlib.sha256(f.read()).digest()
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
    for _ in range(60):
        if check_remote(path, url):
            print("GitHub Pages listo; identidad SHA256 del vídeo comprobada")
            (Path("staged") / "public_video_url.txt").write_text(url)
            return
        time.sleep(12)
    raise RuntimeError("GitHub Pages no ofreció la copia exacta del vídeo; no publicar")


if __name__ == "__main__":
    main()
