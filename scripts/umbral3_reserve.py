"""UMBRAL 3: a number-independent, content-addressed visual reserve contract.

A manifest is not a publication receipt or an approval of artistic quality.
Caller must provide trusted editorial story and recipe, hold a shared lock
for remote persistence and verify again after retrieval.
"""
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.storyboard import validate_storyboard

MADRID = ZoneInfo("Europe/Madrid")
MAX_IMAGE = 25_000_000
MAX_TOTAL = 150_000_000
HEX = re.compile(r"[0-9a-f]{64}")

def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()

def slots(now, days=7):
    """Return the next fourteen future scheduled slots in local civil time."""
    if not isinstance(now, dt.datetime) or now.utcoffset() is None:
        raise ValueError("Timezone-aware clock required")
    if type(days) is not int or not 1 <= days <= 7:
        raise ValueError("Reserve horizon must be 1–7 days")
    now = now.astimezone(MADRID)
    result = []
    for offset in range(days + 1):
        day = now.date() + dt.timedelta(days=offset)
        for hour in (9, 21):
            local = dt.datetime.combine(day, dt.time(hour), MADRID)
            if local > now:
                result.append({"date": day.isoformat(), "slot": f"{hour:02}",
                               "scheduled_utc": local.astimezone(dt.timezone.utc).isoformat()})
    return result[:2 * days]

def story_key(story):
    """Ignore only official numbering and render-local metadata, not visual inputs."""
    validate_storyboard(story)
    if not isinstance(story.get("title"), str) or not story["title"].strip():
        raise ValueError("Missing story title")
    if not isinstance(story.get("caption"), str) or not story["caption"].strip():
        raise ValueError("Missing caption")
    if not 140 <= len(story["narration"].split()) <= 170:
        raise ValueError("Invalid story length")
    return _digest({k:v for k,v in story.items() if k not in
                    ("episode_number", "date", "publish_date")})

def _slot(day, slot):
    date = dt.date.fromisoformat(day)
    if date.isoformat() != day or slot not in ("09", "21"):
        raise ValueError("Invalid civil slot")
    return dt.datetime.combine(date, dt.time(int(slot)), MADRID).astimezone(dt.timezone.utc).isoformat()

def _assets(folder, count):
    """Read exact regular PNG files, bounded size, no symlinks; hash bytes."""
    from PIL import Image
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Invalid reserve directory")
    assets, total = {}, 0
    expected = [f"scene_{i:02}.png" for i in range(count)]
    if sorted(p.name for p in folder.glob("scene_*.png")) != expected:
        raise ValueError("Incomplete or unexpected shot set")
    for name in expected:
        path = folder / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Invalid reserve asset")
        size = path.stat().st_size
        if not 0 < size <= MAX_IMAGE or total + size > MAX_TOTAL:
            raise ValueError("Reserve asset too large")
        total += size
        with Image.open(path) as im:
            w,h = im.size
            if im.format != "PNG" or not 256 <= w <= 2048 or not 256 <= h <= 2048 or h <= w:
                raise ValueError("Invalid portrait image")
            im.verify()
        with Image.open(path) as im:
            im.load()
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for block in iter(lambda: f.read(1024*1024), b""):
                digest.update(block)
        assets[name] = {"bytes": size, "sha256": digest.hexdigest(), "width": w, "height": h}
    if len({a["sha256"] for a in assets.values()}) != count:
        raise ValueError("Identical reserve images")
    return assets

def manifest(story, day, slot, recipe, folder):
    """Bind validated shots to a slot, exact editorial content and renderer recipe."""
    if not isinstance(recipe, dict) or not recipe:
        raise ValueError("Missing renderer recipe")
    if story.get("publish_date", day) != day:
        raise ValueError("Story belongs to another date")
    return {"version": 1, "date": day, "slot": slot,
            "scheduled_utc": _slot(day, slot), "story_sha256": story_key(story),
            "recipe_sha256": _digest(recipe), "assets": _assets(folder, len(story["scenes"])),
            "state": "visual_assets_prepared", "visual_approved": False}

def verify(record, story, day, slot, recipe, folder):
    """Fail closed on corruption, stale recipe/story, date mismatch or missing assets."""
    if not isinstance(record, dict) or record != manifest(story, day, slot, recipe, folder):
        raise ValueError("Reserve manifest mismatch")
    return True
