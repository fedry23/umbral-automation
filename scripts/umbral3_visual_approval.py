"""Fail-closed, owner-reviewed visual approval bound to six exact private scene SHAs.

No AI score, valid media file, or mutable local 'visual_approved' boolean
is proof that the scenes were reviewed. Only an explicit GitHub-tracked
owner approval for a precise civil slot and scene bytes can allow a
live finalization. In particular, a private test can never approve itself.
"""
import datetime as dt
import json
from pathlib import Path
import re

SHA=re.compile(r"[0-9a-f]{64}")
OWNER="fedry23"
BUCKET="Fedry23/umbral-private"
EXPECTED={f"scene_{i:02}.png" for i in range(6)}
FIELDS={"version","status","date","slot","reviewer","reviewed_at",
        "private_bucket","story_sha256","scene_sha256","notes"}

def require_visual_approval(root, day, slot, story_sha, assets):
    if (slot not in ("09","21") or dt.date.fromisoformat(day).isoformat()!=day
            or not isinstance(story_sha,str) or not SHA.fullmatch(story_sha)
            or not isinstance(assets,dict) or set(assets)!=EXPECTED):
        raise ValueError("Invalid visual approval target")
    root=Path(root)
    name=day+("_09" if slot=="09" else "")+".json"
    path=root/"docs"/"visual_approvals"/name
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("Owner visual approval missing; live publication blocked")
    if not 0 < path.stat().st_size <= 12_000:
        raise ValueError("Invalid visual approval size")
    try:
        row=json.loads(path.read_text(encoding="utf-8"))
    except (ValueError,UnicodeError):
        raise RuntimeError("Unreadable owner visual approval; publication blocked") from None
    if (not isinstance(row,dict) or set(row)!=FIELDS
            or row["version"]!=1 or row["status"]!="approved"
            or row["date"]!=day or row["slot"]!=slot
            or row["reviewer"]!=OWNER or row["private_bucket"]!=BUCKET
            or row["story_sha256"]!=story_sha
            or not isinstance(row["notes"],str)
            or not 20<=len(row["notes"].strip())<=1000):
        raise RuntimeError("Owner visual approval does not match slot, story or reviewer")
    expected={}
    for key in sorted(EXPECTED):
        asset=assets[key]
        if (not isinstance(asset,dict) or not isinstance(asset.get("sha256"),str)
                or not SHA.fullmatch(asset["sha256"])):
            raise ValueError("Malformed restored scene SHA")
        expected[key]=asset["sha256"]
    if row["scene_sha256"]!=expected:
        raise RuntimeError("Owner approval was for different visual scene bytes")
    try:
        timestamp=dt.datetime.fromisoformat(row["reviewed_at"].replace("Z","+00:00"))
    except (TypeError,ValueError,AttributeError):
        raise RuntimeError("Missing owner visual review timestamp") from None
    if (timestamp.utcoffset() is None or
            timestamp.astimezone(dt.timezone.utc) > dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=5)):
        raise RuntimeError("Owner review timestamp is invalid or in the future")
    return True
