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
SLOT = os.getenv("UMBRAL_SLOT", "21")
if SLOT not in ("09", "21"):
    raise ValueError("UMBRAL_SLOT debe ser 09 o 21")

def receipt_key(day):
    return day + ("_09" if SLOT == "09" else "")



def now_local():
    return dt.datetime.now(TZ)


def target_time(day):
    return dt.datetime.combine(dt.date.fromisoformat(day), dt.time(9 if SLOT == "09" else 21, 0), tzinfo=TZ)


def test_release_allowed(day):
    """A distinct, owner-approved public test; not the regular daily Reel."""
    return (os.getenv("UMBRAL_TEST_MODE") in ("cinematic-episode-6", "cinematic-episode-7")
            and now_local().date().isoformat() == day)



def daily_marker(day):
    if test_release_allowed(day):
        episode = "7" if os.getenv("UMBRAL_TEST_MODE") == "cinematic-episode-7" else "6"
        return "🩸 UMBRAL · PRUEBA " + episode + " · " + day
    return "🩸 UMBRAL · OFICIAL · " + day + (" · MAÑANA" if SLOT == "09" else "")


def one_time_late_allowed(day):
    """Allow an explicitly configured, date-scoped recovery, never globally."""
    configured = os.getenv("UMBRAL_ONE_TIME_LATE_DATE", "")
    return (test_release_allowed(day)
            or (configured in ("2026-11-16", "2026-11-17")
                and configured == day
                and now_local().date().isoformat() == day))


def full_caption(text, day):
    text = text.strip()
    marker = daily_marker(day)
    if not test_release_allowed(day):
        story = json.loads((OUT / "story_used.json").read_text(encoding="utf-8"))
        marker += " · EPISODIO " + str(story["episode_number"])
    if marker in text:
        return text
    return text[:2200-len(marker)-2] + "\n\n" + marker


def api(method, path, params=None):
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("Falta el secreto IG_ACCESS_TOKEN para publicar")
    body = dict(params or {})
    endpoint = GRAPH.rstrip("/") + "/" + path.lstrip("/")
    if method == "GET":
        endpoint += "?" + urllib.parse.urlencode(body)
        req = urllib.request.Request(endpoint, method="GET", headers={"Authorization": "Bearer " + token})
    else:
        req = urllib.request.Request(
            endpoint, data=urllib.parse.urlencode(body).encode("utf-8"),
            method=method, headers={"Authorization": "Bearer " + token})
    attempts = 3 if method == "GET" else 1
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=65) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if method == "GET" and exc.code in (429, 500, 502, 503, 504) and attempt + 1 < attempts:
                exc.close()
                time.sleep(2 ** attempt)
                continue
            try:
                err = json.loads(exc.read()).get("error", {})
                code = err.get("code", exc.code)
                msg = str(err.get("message", "No details")).replace(token, "[REDACTED]")
            except Exception:
                code, msg = exc.code, "HTTP error"
            finally:
                exc.close()
            raise RuntimeError(f"Instagram Graph API {method} error {code}: {msg}") from None
        except (urllib.error.URLError, TimeoutError):
            if method == "GET" and attempt + 1 < attempts:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Instagram Graph API {method}: fallo de red; no se repite la escritura") from None


def owned_media(max_pages=20):
    """Read-only paginated account inventory. Fail closed if incomplete."""
    from urllib.parse import urlsplit, parse_qs
    cursor = None
    seen_cursors = set()
    for _ in range(max_pages):
        params = {"fields": "id,caption,permalink,timestamp,media_type,media_product_type",
                  "limit": 100}
        if cursor:
            params["after"] = cursor
        data = api("GET", f"{ACCOUNT}/media", params)
        if not isinstance(data.get("data"), list):
            raise RuntimeError("Meta devolvió un listado incompleto; no se permite publicar")
        yield from data["data"]
        next_url = data.get("paging", {}).get("next")
        if not next_url:
            return
        parts = urlsplit(next_url)
        if parts.scheme != "https" or parts.hostname != "graph.facebook.com":
            raise RuntimeError("Paginación Meta inesperada")
        values = parse_qs(parts.query).get("after", [])
        if len(values) != 1 or not values[0] or values[0] in seen_cursors:
            raise RuntimeError("Paginación Meta repetida o inválida")
        cursor = values[0]
        seen_cursors.add(cursor)
    raise RuntimeError("Inventario Meta supera límite de páginas; detener por seguridad")


def already_published(day):
    """Only the matching official episode blocks a scheduled publication.

    Tests and legacy day-only markers do not identify the official episode.
    Durable publish intent and receipt remain enforced separately.
    """
    story, _ = read_story(day)
    marker = daily_marker(day)
    if test_release_allowed(day):
        expected = marker
    else:
        expected = marker + " · EPISODIO " + str(story["episode_number"])
    prefix = marker + " · EPISODIO "
    for item in owned_media():
        if item.get("media_product_type") != "REELS":
            continue
        lines = (item.get("caption") or "").splitlines()
        if expected in lines:
            return item
        if not test_release_allowed(day) and any(line.startswith(prefix) for line in lines):
            raise RuntimeError("Official slot already published with a different number; reconcile, do not POST")
    return None


def read_story(day):
    story = json.loads((OUT / "story_used.json").read_text(encoding="utf-8"))
    caption = (OUT / "caption.txt").read_text(encoding="utf-8")
    if story.get("date") != day or story.get("publish_date") != day:
        raise ValueError("No se puede publicar: no coincide la fecha del relato")
    if not story.get("caption", "").strip() or story["caption"].strip() not in caption:
        raise ValueError("La descripción no corresponde al relato verificado")
    return story, caption


def token_preflight():
    who=api("GET",ACCOUNT,{"fields":"id,username"})
    if who.get("username") != "umbral.terror":
        raise RuntimeError("Cuenta Meta incorrecta")
    details=api("GET","debug_token",{"input_token":os.environ["IG_ACCESS_TOKEN"]}).get("data",{})
    if not details.get("is_valid") or "instagram_content_publish" not in details.get("scopes",[]):
        raise RuntimeError("Token invalido o sin permiso de publicacion")
    expiry=details.get("expires_at",0)
    if expiry:
        days=(expiry-now_local().timestamp())/86400
        if days < 1:
            raise RuntimeError("Token caducado o caduca en menos de 24 horas")
        if days < 10:
            print("::warning::Token Meta caduca en menos de diez dias; renovar")
        print("Token validado; caduca UTC",dt.datetime.fromtimestamp(expiry,dt.timezone.utc).isoformat())


def prepare(day, video_url, cover_url=None):
    if now_local().date().isoformat() != day:
        raise ValueError("La fecha programada no es la fecha local de hoy")
    # Reliability-first: a valid, dated Reel may be prepared late on the same day.
    # The caller still verifies story/date, Instagram state and durable intent.
    if now_local().date().isoformat() != day:
        raise RuntimeError("La recuperación solo puede publicar el episodio de hoy")
    if not video_url.startswith("https://"):
        raise ValueError("Instagram requiere una URL HTTPS pública")
    if cover_url:
        from urllib.parse import urlsplit
        parsed = urlsplit(cover_url)
        if (parsed.scheme != "https" or parsed.netloc != "fedry23.github.io"
                or not parsed.path.startswith("/umbral-automation/reels/")
                or not parsed.path.endswith(".jpg")):
            raise ValueError("La portada debe ser un JPEG público de GitHub Pages")
    token_preflight()
    story, caption = read_story(day)
    metadata = render_metadata(day, story)
    previous = already_published(day)
    if previous:
        status = {"status": "already_published", "media_id": previous["id"], "date": day,
                  "title": story["title"], "episode_number": story.get("episode_number"),
                  "cover_url": cover_url, **metadata}
        (OUT / "prepared.json").write_text(json.dumps(status))
        print("Un Reel del mismo día ya existe; omitiendo preparación")
        return
    if intent_path(day).exists():
        raise RuntimeError("Hay un intento persistente sin resolver; verificar Instagram, NO publicar de nuevo")
    check_episode(day, story.get("episode_number"))
    payload = {"media_type": "REELS", "video_url": video_url,
               "caption": full_caption(caption, day), "share_to_feed": "true"}
    if cover_url:
        payload["cover_url"] = cover_url
    res = api("POST", f"{ACCOUNT}/media", payload)
    container = res["id"]
    print("Contenedor creado, esperando procesado")
    # Meta can need several minutes; never publish unfinished media.
    deadline = now_local() + dt.timedelta(minutes=35)
    while now_local() < deadline:
        status = api("GET", container, {"fields": "status_code,status"})
        code = status.get("status_code")
        if code == "FINISHED":
            result = {"status": "prepared", "container": container,
                      "date": day, "title": story["title"], "cover_url": cover_url,
                      "episode_number": story.get("episode_number"), **metadata}
            (OUT / "prepared.json").write_text(json.dumps(result))
            print("Contenedor terminado; listo para las 21:00")
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError("Instagram rechazó el contenedor: " + str(code) + "; detalle=" + str(status.get("status", "sin detalle"))[:400])
        time.sleep(15)
    raise RuntimeError("Meta no terminó de procesar el Reel en 35 minutos")


def wait_until_target(day):
    target = target_time(day)
    if now_local() > target + dt.timedelta(seconds=20):
        raise RuntimeError("La hora objetivo ya pasó; publicación tardía gestionada por el llamador")
    while True:
        remaining = (target - now_local()).total_seconds()
        if remaining <= 0:
            break
        time.sleep(min(remaining, 30.0))
    if now_local() > target + dt.timedelta(seconds=20):
        raise RuntimeError("La hora objetivo ya pasó durante la espera; revisar la ejecución")


def publish(day):
    data = json.loads((OUT / "prepared.json").read_text())
    if data["date"] != day:
        raise ValueError("La fecha del contenedor no coincide")
    if data["status"] == "already_published":
        record_verified(day, data["media_id"], data)
        return
    if data["status"] != "prepared":
        raise ValueError("No existe contenedor terminado")
    previous = already_published(day)
    if previous:
        print("Encontrado Reel del día en Instagram; no se duplica")
        media_id = previous["id"]
    else:
        if intent_path(day).exists():
            raise RuntimeError("Publicación previa incierta: bloqueo persistente, NO reintentar")
        # Never leave a persistent publish intent while merely waiting for the
        # release hour. A delayed/cancelled scheduler must be harmless.
        # The shared publisher lock protects the wait; the durable intent is
        # committed immediately before the irreversible Meta publication call.
        if now_local() < target_time(day):
            wait_until_target(day)
        if now_local().date().isoformat() != day:
            raise RuntimeError("Expired date before POST; do not publish")
        persist_intent(day, data)
        # The initial Meta read happened before the persistent intent. Reconcile
        # once again immediately before the irreversible Meta write, while the
        # shared workflow lock and durable intent are still held.
        # Incomplete/ambiguous Meta reads must fail closed, never cause a POST.
        published_at_release = already_published(day)
        if now_local().date().isoformat() != day:
            raise RuntimeError("Expired date during final Meta reconciliation; do not publish")
        if published_at_release:
            print("Reel detectado en la comprobación final; no se publica otra vez")
            media_id = published_at_release["id"]
        else:
            # Perform ONE publish request. If the network drops, inspect media
            # before retrying; never automatically repeat an uncertain POST.
            try:
                result = api("POST", f"{ACCOUNT}/media_publish",
                             {"creation_id": data["container"]})
                media_id = result["id"]
            except Exception:
                found = already_published(day)
                if not found:
                    raise RuntimeError("Publicación ambigua: revisar Instagram; NO reintentar automáticamente") from None
                media_id = found["id"]
    record_verified(day, media_id, data)


def intent_path(day):
    key = ("test-cinematic-episode-7" if os.getenv("UMBRAL_TEST_MODE") == "cinematic-episode-7"
           else "test-cinematic-episode-6") if test_release_allowed(day) else day
    return Path("docs/pending") / (key + ("_09" if SLOT == "09" else "") + ".json")


def render_metadata(day, story):
    if os.getenv("UMBRAL_DYNAMIC_EPISODES") != "1" or test_release_allowed(day):
        return {}
    try:
        from .technical_learning import load_profile
    except ImportError:
        from technical_learning import load_profile
    profile = load_profile(day, SLOT)
    if story.get("technical_profile") != profile:
        raise ValueError("Stale render profile")
    _, caption = read_story(day)
    if not caption.startswith(f"Historia {story['episode_number']}: {story['title']}\n"):
        raise ValueError("Stale caption number")
    duration = json.loads((OUT / "branding_timing.json").read_text())["duration"]
    import math
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid render duration")
    editorial = story.get("editorial_protocol")
    if editorial is not None and editorial != "fixed-v1":
        raise ValueError("Unknown editorial protocol")
    return {"slot": SLOT, "technical_profile": profile, "duration_seconds": duration,
            "editorial_protocol": editorial}


def check_episode(day, number):
    if os.getenv("UMBRAL_DYNAMIC_EPISODES") == "1" and not test_release_allowed(day):
        try:
            from .episode_state import validate_episode
        except ImportError:
            from episode_state import validate_episode
        validate_episode(day, SLOT, number)


def persist_intent(day, data):
    """Durable before POST: a crashed run cannot silently publish twice."""
    import subprocess
    if os.getenv("UMBRAL_DURABLE_GUARD") != "1":
        raise RuntimeError("Publicación bloqueada: falta activar registro persistente")
    subprocess.run(["git","pull","--rebase","origin","main"], check=True)
    path = intent_path(day)
    if path.exists():
        raise RuntimeError("Existing intent after refresh; do not POST")
    check_episode(day, data.get("episode_number"))
    story, _ = read_story(day)
    if story.get("episode_number") != data.get("episode_number"):
        raise ValueError("Prepared container episode mismatch")
    for key, value in render_metadata(day, story).items():
        if data.get(key) != value:
            raise ValueError("Prepared container metadata mismatch")
    if now_local().date().isoformat() != day:
        raise RuntimeError("Expired publication date")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": day, "container": data["container"],
                               "status": "publish_intent", "episode_number": data.get("episode_number"), "slot": SLOT,
                               "title": data.get("title"), "technical_profile": data.get("technical_profile"),
                               "duration_seconds": data.get("duration_seconds"), "editorial_protocol": data.get("editorial_protocol"),
                               "cover_url": data.get("cover_url")}, indent=2))
    for args in (["git","add",str(path)],
                 ["git","commit","-m","UMBRAL: registrar intento antes de publicar " + day],
                 ["git","push","origin","HEAD:main"]):
        subprocess.run(args,check=True)


def record_verified(day, media_id, data):
    # Save the returned ID immediately, even if subsequent reads fail.
    output = {"date":day,"title":data.get("title",""),
              "episode_number":data.get("episode_number"),
              "instagram_media_id":media_id,"published_at":now_local().isoformat(),
              "verification":"pending","cover_url_sent":data.get("cover_url")}
    for key in ("slot", "technical_profile", "duration_seconds", "editorial_protocol"):
        if key in data:
            output[key] = data[key]
    path = OUT / "published.json"
    path.write_text(json.dumps(output,indent=2,ensure_ascii=False))
    for attempt in range(12):
        media = api("GET",media_id,{"fields":"id,permalink,media_type,media_product_type,thumbnail_url,timestamp"})
        if media.get("permalink") and media.get("media_product_type") == "REELS":
            output.update(permalink=media["permalink"],verification="published_media_read_back")
            if media.get("timestamp"):
                output["published_at"] = media["timestamp"]
            if media.get("thumbnail_url") and (OUT/"cover.jpg").exists():
                output["cover_verification"] = compare_cover(media["thumbnail_url"],OUT/"cover.jpg")
            path.write_text(json.dumps(output,indent=2,ensure_ascii=False))
            print("Publicación verificada:",media_id,media["permalink"])
            if data.get("cover_url") and not output.get("cover_verification",{}).get("matched"):
                raise RuntimeError("Reel publicado; portada NO confirmada. No volver a publicar")
            return
        time.sleep(10)
    raise RuntimeError("ID guardado pero lectura de publicación pendiente; NO repetir POST")


def compare_cover(url, local):
    """Compare normalized pixels; Meta recompresses JPEG, so hashes differ."""
    import io
    import numpy as np
    from PIL import Image, ImageOps
    with urllib.request.urlopen(url,timeout=45) as response:
        raw=response.read(8_000_001)
    (OUT/"instagram_cover.jpg").write_bytes(raw)
    with Image.open(io.BytesIO(raw)) as actual, Image.open(local) as expected:
        actual=actual.convert("RGB")
        expected=ImageOps.fit(expected.convert("RGB"),actual.size)
        a=np.asarray(actual.resize((90,160)),dtype=float)
        b=np.asarray(expected.resize((90,160)),dtype=float)
        error=float(np.mean(np.abs(a-b)))
    return {"matched":error < 18,"mean_pixel_error":round(error,3),
            "method":"center-crop resize mean absolute RGB error <18/255"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "publish"])
    parser.add_argument("--date", required=True)
    parser.add_argument("--video-url")
    parser.add_argument("--cover-url", help="JPEG 9:16 público de portada, si existe")
    args = parser.parse_args()
    if args.command == "prepare":
        if not args.video_url:
            parser.error("--video-url es obligatorio")
        prepare(args.date, args.video_url, cover_url=args.cover_url)
    else:
        publish(args.date)


if __name__ == "__main__":
    main()
