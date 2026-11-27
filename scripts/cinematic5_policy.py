"""Shared, lightweight Cinematic 5 scheduling policy (no rendering or network)."""
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = Path("cinematic5/scheduled.json")
POLICY = Path("cinematic5/policy.json")


def enabled(root=ROOT):
    try:
        data = json.loads((Path(root)/POLICY).read_text(encoding="utf-8"))
        return data == {"version":1,"enabled":True}
    except (OSError,ValueError,TypeError):
        return False


def indexed_cut(day,slot,root=ROOT):
    if slot not in ("09","21") or dt.date.fromisoformat(day).isoformat()!=day:
        raise ValueError("Invalid civil slot")
    data=json.loads((Path(root)/INDEX).read_text(encoding="utf-8"))
    if not isinstance(data,dict):
        raise ValueError("Invalid cinematic index")
    return data.get(f"{day}_{slot}")


def selected(day,slot,root=ROOT):
    """Select the existing publisher only for an explicitly scheduled matching cut."""
    if not enabled(root):
        return False
    try:
        cut=indexed_cut(day,slot,root)
        if not isinstance(cut,dict) or cut.get("format")!="cinematic-5":
            return False
        path=Path(root)/("stories_morning.json" if slot=="09" else "stories.json")
        matches=[s for s in json.loads(path.read_text(encoding="utf-8")) if s.get("publish_date")==day]
        return len(matches)==1 and cut.get("title")==matches[0].get("title")
    except (OSError,ValueError,TypeError,AttributeError,KeyError):
        return False
