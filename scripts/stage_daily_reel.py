#!/usr/bin/env python3
"""Recover and validate today's generated Reel from an authenticated GitHub Action."""
import datetime as dt
import io
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import zipfile
from zoneinfo import ZoneInfo

REPO = "fedry23/umbral-automation"
WORKFLOW = "UMBRAL - Generación para revisión"
OUT = Path("staged")


def local_day(now=None):
    return (now or dt.datetime.now(ZoneInfo("Europe/Madrid"))).date().isoformat()


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
    with urllib.request.urlopen(req, timeout=65) as res:
        data = res.read()
    return data if binary else json.loads(data)


def select_run(runs, date):
    candidates = []
    for run in runs:
        if (run.get("name") == WORKFLOW
                and run.get("event") == "schedule"
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
    if not story.get("title") or len(story.get("scenes", [])) < 4:
        raise ValueError("Relato o escenas incompletas")
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


def extract_run_zip(raw, date):
    OUT.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        mp4s = [n for n in names if n.endswith(".mp4") and "/" not in n]
        if len(mp4s) != 1:
            raise ValueError("Se esperaba exactamente un MP4 en el artefacto")
        expected = "umbral_" + date.replace("-", "") + ".mp4"
        if mp4s[0] != expected:
            raise ValueError("Nombre de MP4 diferente a la fecha de hoy")
        for key in [expected, "story_used.json", "caption.txt", "music.wav"]:
            if key not in names:
                raise ValueError("Archivo ausente del artefacto: " + key)
        story = json.loads(z.read("story_used.json"))
        caption = z.read("caption.txt").decode("utf-8")
        verify_story(story, caption, date)
        if z.getinfo("music.wav").file_size < 20000:
            raise ValueError("La música original está vacía")
        for filename in [expected, "story_used.json", "caption.txt"]:
            (OUT / filename).write_bytes(z.read(filename))
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
    data = github_get(f"repos/{REPO}/actions/workflows/reel.yml/runs?event=schedule&per_page=30")
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
