"""Read-only Meta reconciliation, with durable GitHub receipt writes.

This module has no POST path. Ambiguity always stops subsequent publishing.
"""
import datetime as dt
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

try:
    from .episode_state import OFFICIAL_KEY, inventory
    from . import publish_daily
except ImportError:
    from episode_state import OFFICIAL_KEY, inventory
    import publish_daily

def load(path):
    row = json.loads(path.read_text())
    if not isinstance(row, dict):
        raise ValueError(f"Invalid record: {path}")
    return row

def unresolved(root):
    pending = root / "docs/pending"
    published = root / "docs/published"
    keys = {p.stem for directory in (pending, published) for p in directory.glob("*.json")
            if OFFICIAL_KEY.fullmatch(p.stem)}
    result = []
    for key in sorted(keys):
        p, q = pending / (key + ".json"), published / (key + ".json")
        old = load(q) if q.exists() else {}
        if old.get("verification") == "published_media_read_back":
            continue
        if key == "2026-11-16" and old.get("instagram_media_id") == "18096307043444916" and "verification" not in old:
            continue
        intent = load(p) if p.exists() else {}
        result.append((key, intent, old))
    return result

def reconcile_one(key, intent, old, media_rows, fetch_media):
    day = key[:10]
    slot = "09" if key.endswith("_09") else "21"
    number = intent.get("episode_number", old.get("episode_number"))
    if type(number) is not int or number < 1:
        raise ValueError("Attempt lacks a durable official episode number")
    if intent and (intent.get("date") != day or intent.get("slot") != slot):
        raise ValueError("Intent date/slot mismatch")
    if old and (old.get("date") != day or old.get("episode_number") != number):
        raise ValueError("Receipt and intent disagree")
    marker = "🩸 UMBRAL · OFICIAL · " + day + (" · MAÑANA" if slot == "09" else "") + " · EPISODIO " + str(number)
    matches = [m for m in media_rows if m.get("media_product_type") == "REELS"
               and marker in (m.get("caption") or "").splitlines()]
    if len(matches) != 1:
        raise RuntimeError("Could not identify exactly one published Reel; do not retry POST")
    media_id = matches[0].get("id")
    if not isinstance(media_id, str) or not media_id or (old.get("instagram_media_id") and old["instagram_media_id"] != media_id):
        raise ValueError("Media ID mismatch")
    media = fetch_media(media_id)
    if (media.get("id") != media_id or media.get("media_product_type") != "REELS" or
            not media.get("permalink") or marker not in (media.get("caption") or "").splitlines()):
        raise RuntimeError("Meta read-back verification failed")
    timestamp = dt.datetime.fromisoformat(media["timestamp"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.astimezone(ZoneInfo("Europe/Madrid")).date().isoformat() != day:
        raise ValueError("Published timestamp does not match the intended day")
    receipt = {**old, "date": day, "slot": slot, "title": old.get("title") or intent.get("title"),
               "episode_number": number, "instagram_media_id": media_id,
               "published_at": media["timestamp"], "permalink": media["permalink"],
               "verification": "published_media_read_back",
               "reconciliation": "unique_official_marker_and_media_read_back"}
    # No claim about historical cover matching without its pixels.
    for name in ("technical_profile", "duration_seconds"):
        if name in intent and name not in receipt:
            receipt[name] = intent[name]
    if intent.get("cover_url") and "cover_url_sent" not in receipt:
        receipt["cover_url_sent"] = intent["cover_url"]
    return receipt

def main():
    root = Path(".")
    subprocess.run(["git", "pull", "--ff-only", "origin", "main"], check=True)
    items = unresolved(root)
    if not items:
        inventory(root)
        print("No unresolved official publication attempts")
        return
    publish_daily.token_preflight()
    media = publish_daily.owned_media()
    changes = []
    def read_back(media_id):
        return publish_daily.api("GET", media_id, {"fields": "id,caption,permalink,media_product_type,timestamp"})
    # Calculate everything first; never write a guessed or partial receipt.
    for key, intent, old in items:
        row = reconcile_one(key, intent, old, media, read_back)
        changes.append((root / "docs/published" / (key + ".json"), row))
    for path, row in changes:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(row, ensure_ascii=False, indent=2))
        tmp.replace(path)
    inventory(root)
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "add", *[str(p) for p, _ in changes]], check=True)
    subprocess.run(["git", "commit", "-m", "UMBRAL: reconcile confirmed Instagram publication(s)"], check=True)
    subprocess.run(["git", "push", "origin", "HEAD:main"], check=True)
    print("Reconciled official receipts:", len(changes))

if __name__ == "__main__":
    main()
