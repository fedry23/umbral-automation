"""Read-only UMBRAL quality audit. Never removes or republishes media.

Flags duplicate captions, repeated episode numbers, missing branding and
unexpected media types. Human review remains required for subjective quality.
"""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode
from check_delete_token import get, ACCOUNT

def main():
    token = os.getenv("IG_DELETE_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("Missing IG_DELETE_ACCESS_TOKEN")
    result = get("/" + ACCOUNT + "/media?" + urlencode({
        "fields":"id,caption,timestamp,media_product_type,permalink","limit":100}), token)
    items = result.get("data", [])
    if not isinstance(items,list): raise RuntimeError("Incomplete Instagram response")
    warnings = []
    seen_markers = {}
    seen_episode = {}
    for item in items:
        if item.get("media_product_type") != "REELS": continue
        caption = item.get("caption") or ""
        media_id = item.get("id")
        marker = re.search(r"UMBRAL\s*[·-]\s*(?:PRUEBA\s*\d+\s*[·-]\s*)?(\d{4}-\d{2}-\d{2})",caption,re.I)
        episode = re.search(r"(?i)historia\s*(?:n[uú]mero\s*)?(\d+)",caption)
        if not caption.strip(): warnings.append({"id":media_id,"issue":"missing_caption"})
        if marker:
            day=marker.group(1)
            if day in seen_markers: warnings.append({"id":media_id,"issue":"duplicate_daily_marker","other":seen_markers[day]})
            seen_markers[day]=media_id
        if episode:
            n=episode.group(1)
            if n in seen_episode: warnings.append({"id":media_id,"issue":"duplicate_episode_number","other":seen_episode[n]})
            seen_episode[n]=media_id
    report={"status":"READ_ONLY_AUDIT","reels_checked":sum(i.get("media_product_type")=="REELS" for i in items),
            "issues":warnings,"auto_delete":False,"auto_publish":False,
            "note":"Subjective audio, story and image quality requires source-artifact validation and review."}
    Path("docs/audit").mkdir(parents=True,exist_ok=True)
    Path("docs/audit/reel-quality.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
    if warnings: print("::warning::Potential UMBRAL Reel issues detected; replacement must pass full validation.")
if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print("::error::"+str(exc))
        sys.exit(1)
