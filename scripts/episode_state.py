"""Derive episode state from durable publication receipts; never publish."""
import json
from pathlib import Path

def next_episode(root=Path("."), baseline=10):
    root = Path(root)
    pending = root / "docs/pending"
    published = root / "docs/published"
    numbers = {}
    for path in sorted(published.glob("*.json")):
        row = json.loads(path.read_text())
        if row.get("verification") != "published_media_read_back":
            raise ValueError(f"Unverified receipt: {path}")
        if not row.get("permalink") or not row.get("instagram_media_id"):
            raise ValueError(f"Incomplete receipt: {path}")
        number = row.get("episode_number")
        if type(number) is not int or number < 1:
            raise ValueError(f"Invalid episode: {path}")
        if number in numbers:
            raise ValueError(f"Duplicate episode: {number}")
        numbers[number] = path
    for path in pending.glob("*.json"):
        if not (published / path.name).is_file():
            raise ValueError(f"Unresolved publication: {path}")
    return max([baseline, *numbers]) + 1
