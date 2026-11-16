#!/usr/bin/env python3
"""UMBRAL Instagram official API: one daily Reel, at 21:00 Europe/Madrid.

Requires the owner's own Instagram content-publishing token in GitHub Secrets.
Never prints credentials and never retries an ambiguous publish operation.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

GRAPH = "https://graph.facebook.com/" + os.getenv("GRAPH_API_VERSION", "v25.0")
TZ = ZoneInfo("Europe/Madrid")
ACCOUNT = "17841465578937909"
OUT = Path("staged")


def now_local():
    return dt.datetime.now(TZ)


def target_time(day):
    return dt.datetime.combine(dt.date.fromisoformat(day), dt.time(21, 0), tzinfo=TZ)


def test_release_allowed(day):
    """A distinct, owner-approved public test; not the regular daily Reel."""
    return (day == "2026-11-16"
            and now_local().date().isoformat() == day
            and os.getenv("UMBRAL_TEST_MODE") == "2026-11-16-episode-4")


def daily_marker(day):
    if test_release_allowed(day):
        return "🩸 UMBRAL · PRUEBA 4 · " + day
    return "🩸 UMBRAL · " + day


def one_time_late_allowed(day):
    """Explicit owner-approved 16 Nov exception; no effect on future dates."""
    return (test_release_allowed(day)
            or (os.getenv("UMBRAL_ONE_TIME_LATE_DATE") == "2026-11-16"
                and day == "2026-11-16"
                and now_local().date().isoformat() == "2026-11-16"))


def full_caption(text, day):
    text = text.strip()
    marker = daily_marker(day)
    if marker in text:
        return text
    return (text + "\n\n" + marker)[:2200]


def api(method, path, params=None):
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("Falta el secreto IG_ACCESS_TOKEN para publicar")
    body = dict(params or {})
    body["access_token"] = token
    endpoint = GRAPH.rstrip("/") + "/" + path.lstrip("/")
    if method == "GET":
        endpoint += "?" + urllib.parse.urlencode(body)
        req = urllib.request.Request(endpoint, method="GET")
    else:
        req = urllib.request.Request(
            endpoint, data=urllib.parse.urlencode(body).encode("utf-8"),
            method=method)
    try:
        with urllib.request.urlopen(req, timeout=65) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read()).get("error", {})
            code = err.get("code", exc.code)
            msg = err.get("message", "No details")
        except Exception:
            code, msg = exc.code, "HTTP error"
        raise RuntimeError(f"Instagram Graph API {method} error {code}: {msg}") from None


def already_published(day):
    """Search owned recent media; prevent duplicate retries after timeouts."""
    data = api("GET", f"{ACCOUNT}/media",
               {"fields": "id,caption,permalink,timestamp", "limit": 100})
    for item in data.get("data", []):
        if daily_marker(day) in item.get("caption", ""):
            return item
    return None


def read_story(day):
    story = json.loads((OUT / "story_used.json").read_text(encoding="utf-8"))
    caption = (OUT / "caption.txt").read_text(encoding="utf-8")
    if story.get("date") != day or story.get("publish_date") != day:
        raise ValueError("No se puede publicar: no coincide la fecha del relato")
    if not story.get("caption", "").strip() in caption:
        raise ValueError("La descripción no corresponde al relato verificado")
    return story, caption


def prepare(day, video_url):
    if now_local().date().isoformat() != day:
        raise ValueError("La fecha programada no es la fecha local de hoy")
    if now_local() >= target_time(day) and not one_time_late_allowed(day):
        raise RuntimeError("La preparación empezó demasiado tarde; no publicar fuera de hora")
    if not video_url.startswith("https://"):
        raise ValueError("Instagram requiere una URL HTTPS pública")
    story, caption = read_story(day)
    previous = already_published(day)
    if previous:
        status = {"status": "already_published", "media_id": previous["id"], "date": day}
        (OUT / "prepared.json").write_text(json.dumps(status))
        print("Un Reel del mismo día ya existe; omitiendo preparación")
        return
    res = api("POST", f"{ACCOUNT}/media",
              {"media_type": "REELS", "video_url": video_url,
               "caption": full_caption(caption, day), "share_to_feed": "true"})
    container = res["id"]
    print("Contenedor creado, esperando procesado")
    # Meta can need several minutes; never publish unfinished media.
    deadline = (now_local() + dt.timedelta(minutes=35)
                if one_time_late_allowed(day)
                else min(target_time(day) - dt.timedelta(seconds=25),
                         now_local() + dt.timedelta(minutes=35)))
    while now_local() < deadline:
        status = api("GET", container, {"fields": "status_code,status"})
        code = status.get("status_code")
        if code == "FINISHED":
            result = {"status": "prepared", "container": container,
                      "date": day, "title": story["title"]}
            (OUT / "prepared.json").write_text(json.dumps(result))
            print("Contenedor terminado; listo para las 21:00")
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError("Instagram rechazó el contenedor: " + str(code) + "; detalle=" + str(status.get("status", "sin detalle"))[:400])
        time.sleep(15)
    raise RuntimeError("Meta no terminó de procesar el Reel antes de las 21:00")


def wait_until_target(day):
    target = target_time(day)
    if now_local() > target + dt.timedelta(seconds=20):
        raise RuntimeError("El horario de las 21:00 ya pasó; no publicar tarde")
    while True:
        remaining = (target - now_local()).total_seconds()
        if remaining <= 0:
            break
        time.sleep(min(remaining, 30.0))
    if now_local() > target + dt.timedelta(seconds=20):
        raise RuntimeError("Demasiado tarde para publicar; revisar la ejecución")


def publish(day):
    data = json.loads((OUT / "prepared.json").read_text())
    if data["date"] != day:
        raise ValueError("La fecha del contenedor no coincide")
    if data["status"] == "already_published":
        print("Ya publicado; no duplicar")
        return
    if data["status"] != "prepared":
        raise ValueError("No existe contenedor terminado")
    if not one_time_late_allowed(day):
        wait_until_target(day)
    previous = already_published(day)
    if previous:
        print("Encontrado Reel del día en Instagram; no se duplica")
        media_id = previous["id"]
    else:
        # Perform ONE publish request. If the network drops, inspect media before retrying.
        try:
            result = api("POST", f"{ACCOUNT}/media_publish",
                         {"creation_id": data["container"]})
            media_id = result["id"]
        except Exception:
            found = already_published(day)
            if not found:
                raise RuntimeError("Publicación ambigua: revisar Instagram; NO reintentar automáticamente") from None
            media_id = found["id"]
    output = {"date": day, "title": data.get("title", ""),
              "instagram_media_id": media_id,
              "published_at": now_local().isoformat()}
    (OUT / "published.json").write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print("Publicación Instagram confirmada. ID:", media_id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "publish"])
    parser.add_argument("--date", required=True)
    parser.add_argument("--video-url")
    args = parser.parse_args()
    if args.command == "prepare":
        if not args.video_url:
            parser.error("--video-url es obligatorio")
        prepare(args.date, args.video_url)
    else:
        publish(args.date)


if __name__ == "__main__":
    main()
