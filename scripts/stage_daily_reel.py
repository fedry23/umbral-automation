#!/usr/bin/env python3
"""Recover and validate today's generated Reel from an authenticated GitHub Action."""
import datetime as dt
import io
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import urllib.parse
import zipfile
from zoneinfo import ZoneInfo

REPO = "fedry23/umbral-automation"
WORKFLOW = "UMBRAL - Generación para revisión"
OUT = Path("staged")


def local_day(now=None):
    return (now or dt.datetime.now(ZoneInfo("Europe/Madrid"))).date().isoformat()


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward our GitHub Actions token to artifact CDN redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if (new_req is not None
                and urllib.parse.urlsplit(req.full_url).netloc
                != urllib.parse.urlsplit(newurl).netloc):
            new_req.remove_header("Authorization")
        return new_req


def github_get(path, binary=False):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Falta GITHUB_TOKEN con permiso actions:read")
    req = urllib.request.Request(
        "https://api.github.com/" + path.lstrip("/"),
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "UMBRAL-daily-publisher"})
    with urllib.request.build_opener(SafeRedirect()).open(req, timeout=65) as res:
        data = res.read()
    return data if binary else json.loads(data)


def select_run(runs, date):
    candidates = []
    for run in runs:
        if (run.get("name") == WORKFLOW
                and run.get("event") in ("schedule", "push")
                and run.get("head_branch") == "main"
                and run.get("status") == "completed"
                and run.get("conclusion") == "success"):
            started = dt.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            if started.astimezone(ZoneInfo("Europe/Madrid")).date().isoformat() == date:
                candidates.append(run)
    return max(candidates, key=lambda r: r["created_at"]) if candidates else None


def verify_story(story, caption, date):
    if story.get("date") != date or story.get("publish_date") != date:
        raise ValueError("El Reel generado NO pertenece al día de hoy")
    if not (140 <= len(story.get("narration", "").split()) <= 170):
        raise ValueError("Relato fuera de la longitud esperada")
    if not story.get("title") or len(story.get("scenes", [])) != 6:
        raise ValueError("Relato o escenas incompletas")
    episode = story.get("episode_number")
    if type(episode) is not int or episode < 1:
        raise ValueError("Número de episodio ausente o inválido")
    if not all(isinstance(scene, str) and scene.strip() for scene in story["scenes"]):
        raise ValueError("Hay escenas vacías o inválidas")
    if not caption.strip() or story.get("caption", "").strip() not in caption:
        raise ValueError("Descripción no coincide con el relato")
    return True


def validate_mp4(path):
    info = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format",
         "-of", "json", str(path)], text=True))
    video = next(x for x in info["streams"] if x["codec_type"] == "video")
    audio = next(x for x in info["streams"] if x["codec_type"] == "audio")
    duration = float(info["format"]["duration"])
    if (video.get("codec_name") != "h264" or audio.get("codec_name") != "aac"
            or (video.get("width"), video.get("height")) != (720, 1280)
            or not 15 <= duration <= 180):
        raise ValueError("Formato audiovisual no válido para UMBRAL")
    if path.stat().st_size < 100000:
        raise ValueError("Vídeo sospechosamente pequeño")
    return duration


def validate_cover(path):
    if not (10_000 <= path.stat().st_size <= 8_000_000):
        raise ValueError('La portada JPEG no cumple el tamaño requerido')
    data = path.read_bytes()
    if not (data.startswith(b'\xff\xd8') and data.endswith(b'\xff\xd9')):
        raise ValueError('Portada no es un JPEG válido')
    info = json.loads(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(path)],
        text=True))
    pic = next((v for v in info['streams'] if v.get('codec_type') == 'video'), None)
    if pic is None or pic.get('codec_name') != 'mjpeg' or (
            pic.get('width'), pic.get('height')) != (1080, 1920):
        raise ValueError('Portada debe ser JPEG 1080x1920')
    return True


def extract_run_zip(raw, date):
    OUT.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        # Reject ambiguous or oversized artifacts before decompressing anything.
        if len(names) != len(set(names)) or len(names) > 100:
            raise ValueError("Artefacto ZIP con entradas duplicadas o excesivas")
        if any(info.file_size > 250_000_000 for info in z.infolist()):
            raise ValueError("Archivo del artefacto demasiado grande")
        if sum(info.file_size for info in z.infolist()) > 350_000_000:
            raise ValueError("Artefacto descomprimido supera el límite")
        mp4s = [n for n in names if n.endswith(".mp4") and "/" not in n]
        if len(mp4s) != 1:
            raise ValueError("Se esperaba exactamente un MP4 en el artefacto")
        expected = "umbral_" + date.replace("-", "") + ".mp4"
        if mp4s[0] != expected:
            raise ValueError("Nombre de MP4 diferente a la fecha de hoy")
        for key in [expected, "story_used.json", "caption.txt", "music.wav",
                    "cover.jpg", "intro_card.png", "outro_card.png",
                    "branding_timing.json"]:
            if key not in names:
                raise ValueError("Archivo ausente del artefacto: " + key)
        story = json.loads(z.read("story_used.json"))
        caption = z.read("caption.txt").decode("utf-8")
        verify_story(story, caption, date)
        # Reject stale renders from earlier runs on the same date.
        scheduled = json.loads(Path("stories.json").read_text(encoding="utf-8"))
        scheduled_stories = [s for s in scheduled if s.get("publish_date") == date]
        if len(scheduled_stories) != 1 or any(
            story.get(key) != scheduled_stories[0].get(key)
            for key in ("title", "episode_number", "narration")
        ):
            raise ValueError("Artefacto obsoleto: no coincide con episodio oficial vigente")
        if z.getinfo("music.wav").file_size < 20000:
            raise ValueError("La música original está vacía")
        for filename in [expected, "story_used.json", "caption.txt",
                         "cover.jpg", "branding_timing.json"]:
            (OUT / filename).write_bytes(z.read(filename))
    validate_cover(OUT / "cover.jpg")
    marks = json.loads((OUT / "branding_timing.json").read_text(encoding="utf-8"))
    if not (0 < marks.get("intro_end", 0) < marks.get("outro_start", 0)
            < marks.get("duration", 0)):
        raise ValueError('Marcas temporales intro/outro incompatibles')
    duration = validate_mp4(OUT / expected)
    return {"title": story["title"], "duration": round(duration, 2),
            "file": str(OUT / expected), "date": date}


def main():
    date = local_day()
    if (Path("docs/published") / (date + ".json")).exists():
        print("UMBRAL: ya hay un recibo para esta fecha, no se publica dos veces")
        (OUT / "already_published").parent.mkdir(exist_ok=True)
        (OUT / "already_published").write_text(date)
        return
    data = github_get(f"repos/{REPO}/actions/workflows/reel.yml/runs?per_page=30")
    run = select_run(data.get("workflow_runs", []), date)
    if not run:
        raise RuntimeError("No hay una generación programada correcta para hoy; no se reutilizan vídeos")
    art = github_get(f"repos/{REPO}/actions/runs/{run['id']}/artifacts")
    matches = [a for a in art.get("artifacts", []) if a.get("name") == "umbral-reel" and not a.get("expired")]
    if len(matches) != 1:
        raise RuntimeError("No existe el artefacto único esperado del Reel diario")
    blob = github_get(f"repos/{REPO}/actions/artifacts/{matches[0]['id']}/zip", binary=True)
    result = extract_run_zip(blob, date)
    print("Reel verificado:", result["title"], result["duration"], "s; run", run["id"])


if __name__ == "__main__":
    main()
