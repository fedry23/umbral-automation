"""Fail-closed gate for a manual replacement of the latest Reel.

No DELETE or media_publish operation is implemented here.
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from check_delete_token import get, ACCOUNT

REPORT = Path("docs/audit/latest-reel-preflight.json")
STORY = Path("stories/replacement_latest_2026-11-17.json")

def main():
    report = json.loads(REPORT.read_text())
    story = json.loads(STORY.read_text())
    if len(story["scenes"]) != 6 or not 140 <= len(story["narration"].split()) <= 170:
        raise RuntimeError("Replacement creative does not pass content validation")
    if report.get("replacement_ready") is not True:
        raise RuntimeError("STOP: replacement video not rendered and validated; no deletion authorized")
    if not os.environ.get("IG_DELETE_ACCESS_TOKEN"):
        raise RuntimeError("STOP: missing independent delete credential")
    media = get("/" + ACCOUNT + "/media?fields=id,timestamp,media_product_type&limit=100",
                os.environ["IG_DELETE_ACCESS_TOKEN"])
    reels = [m for m in media.get("data",[]) if m.get("media_product_type") == "REELS"]
    if not reels:
        raise RuntimeError("STOP: no Reels returned")
    newest = max(reels,key=lambda x:datetime.fromisoformat(x["timestamp"].replace("Z","+00:00")))
    if newest["id"] != report["latest_reel_id"]:
        raise RuntimeError("STOP: latest Reel changed since inventory")
    print("Replacement gate passed (read-only); no deletion executed.")

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print("::error::" + str(exc))
        sys.exit(1)
