"""Read-only official episode allocation from durable publication receipts.

A render is speculative. Only a confirmed official receipt advances the number.
The publishing caller must hold the shared lock and refresh state before POST.
"""
import datetime as dt
import json
import re
from pathlib import Path

OFFICIAL_KEY = re.compile(r"\d{4}-\d{2}-\d{2}(?:_09)?")

def receipt_key(day, slot):
    if not isinstance(day, str) or dt.date.fromisoformat(day).isoformat() != day:
        raise ValueError("Invalid publication date")
    if slot not in ("09", "21"):
        raise ValueError("Invalid publication slot")
    return day + ("_09" if slot == "09" else "")

def _read(path):
    row = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(row, dict):
        raise ValueError(f"Invalid receipt: {path}")
    return row

def inventory(root=Path("."), baseline=10):
    root = Path(root)
    if type(baseline) is not int or baseline < 0:
        raise ValueError("Invalid migration baseline")
    published, pending = root / "docs/published", root / "docs/pending"
    numbers, ids, receipts = set(), set(), {}
    for path in sorted(published.glob("*.json")):
        if not OFFICIAL_KEY.fullmatch(path.stem):
            continue  # Historical tests are not part of the official sequence.
        row = _read(path)
        # Immutable pre-migration receipt verified against the Windsor snapshot.
        # It blocks the historical day but does not supply a numbered episode.
        if (path.stem == "2026-11-16" and row.get("date") == "2026-11-16"
                and row.get("instagram_media_id") == "18096307043444916"
                and row.get("title") == "La costura" and "episode_number" not in row
                and "verification" not in row):
            receipts[path.stem] = row
            ids.add(row["instagram_media_id"])
            continue
        number, media_id = row.get("episode_number"), row.get("instagram_media_id")
        if row.get("verification") != "published_media_read_back":
            raise ValueError(f"Unverified receipt: {path}")
        if not isinstance(media_id, str) or not media_id.strip() or not row.get("permalink"):
            raise ValueError(f"Incomplete receipt: {path}")
        if path.stem != receipt_key(row.get("date"), "09" if path.stem.endswith("_09") else "21"):
            raise ValueError(f"Receipt date mismatch: {path}")
        if type(number) is not int or number < 1 or number in numbers or media_id in ids:
            raise ValueError(f"Invalid or duplicate episode/media: {path}")
        numbers.add(number)
        ids.add(media_id)
        receipts[path.stem] = row
    for path in pending.glob("*.json"):
        if OFFICIAL_KEY.fullmatch(path.stem) and path.stem not in receipts:
            raise ValueError(f"Unresolved publication: {path}")
    return max([baseline, *numbers]), receipts

def next_episode(root=Path("."), baseline=10):
    return inventory(root, baseline)[0] + 1

def planned_episode(day, slot, root=Path("."), *, anticipate_morning=False):
    """Same-slot retries reuse confirmed IDs; evening pre-render may speculate."""
    key = receipt_key(day, slot)
    last, receipts = inventory(root)
    if key in receipts:
        if "episode_number" not in receipts[key]:
            raise ValueError("Historical unnumbered slot is closed")
        return receipts[key]["episode_number"]
    if slot == "09" and receipt_key(day, "21") in receipts:
        raise ValueError("Morning slot closed by confirmed evening publication")
    speculative = anticipate_morning and slot == "21" and receipt_key(day, "09") not in receipts
    return last + 1 + int(speculative)

def validate_episode(day, slot, number, root=Path(".")):
    if type(number) is not int or number != planned_episode(day, slot, root):
        raise ValueError("Stale episode number; regenerate before publishing")
    return number
