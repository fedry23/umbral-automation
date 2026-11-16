#!/usr/bin/env python3
"""Publicar un Reel mediante la API de Instagram (Facebook Login)."""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://graph.facebook.com/v24.0"


def api(method, path, params):
 data = urllib.parse.urlencode(params).encode("utf-8")
 url = BASE + "/" + path.lstrip("/")
    if method == "GET":
 url += "?" + data.decode("utf-8")
 req = urllib.request.Request(
 url, data=data if method == "POST" else None, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        try:
 error = json.load(exc).get("error", {})
 message = error.get("message", "Error desconocido")
 code = error.get("code", exc.code)
        except (ValueError, OSError):
 message, code = "Error desconocido", exc.code
        raise RuntimeError(f"Error de Instagram API {code}: {message}") from None


def main():
    if os.getenv("IG_PUBLISH_DRY_RUN", "true").lower() != "false":
        print("Modo seguro: publicación desactivada.")
        return
 user = os.environ["IG_USER_ID"]
 token = os.environ["IG_ACCESS_TOKEN"]
 url = os.environ["REEL_VIDEO_URL"]
 caption = os.getenv("REEL_CAPTION", "UMBRAL #UmbralTerror")
    if not url.startswith("https://"):
        raise ValueError("El vídeo requiere URL pública HTTPS")
 created = api("POST", f"{user}/media", {
        "media_type": "REELS", "video_url": url,
        "caption": caption, "access_token": token
    })
 creation_id = created["id"]
    print("Contenedor de Reel creado")
    for _ in range(40):
 time.sleep(15)
 status = api("GET", creation_id, {
            "fields": "status_code", "access_token": token
        }).get("status_code")
        print("Estado:", status)
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError("Error procesando vídeo")
    else:
        raise TimeoutError("El vídeo no se procesó a tiempo")
 published = api("POST", f"{user}/media_publish", {
        "creation_id": creation_id, "access_token": token
    })
    print("Reel publicado:", published["id"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Fallo de publicación:", str(exc), file=sys.stderr)
 sys.exit(1)
