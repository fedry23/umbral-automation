"""Read-only seven-day private video candidate reserve inventory.

A verified MP4 is not visually approved. This inventory reports stored,
missing and potentially corrupt candidates; it NEVER marks them publishable.
No token, private image pixels or hidden URLs go into logs.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import zipfile
from pathlib import Path

from scripts.umbral3_hf_storage import HfBucketStore
from scripts.umbral3_hf_candidate_index import find
from scripts.umbral3_reserve_render import catalogs,load_slot
from scripts.umbral3_reserve import story_key
from scripts.umbral3_evidence import verify_media_bundle

BACKEND="sdxl-lightning-2steps-ov-int8"

def audit(store,anchor,backend=BACKEND):
    entries=catalogs()
    result={"backend":backend,"anchor":anchor.isoformat(),"expected":14,
            "stored_complete":0,"missing":[],"corrupt":[],"total_bytes":0,
            "visual_approved":0,"ready_reels":0,"private":True}
    for index in range(14):
        story,day,slot=load_slot(index,anchor,entries)
        p=find(store,day,slot,backend)
        if p is None:
            result["missing"].append({"date":day,"slot":slot})
            continue
        try:
            if p["story_sha256"]!=story_key(story):
                raise ValueError("Stale editorial story in candidate index")
            blob=store.get(p["bundle_sha256"]+".zip")
            if blob is None or len(blob)!=p["bundle_bytes"] or hashlib.sha256(blob).hexdigest()!=p["bundle_sha256"]:
                raise ValueError("Candidate bytes or SHA mismatch")
            media=verify_media_bundle(blob)
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                summary=json.loads(archive.read("summary.json"))
                videos=[n for n in archive.namelist() if n.endswith(".mp4")]
                if (len(videos)!=1 or videos[0]!=f"candidate-{day}-{slot}.mp4"
                    or summary.get("candidate") is not True
                    or summary.get("media_decoded") is not True
                    or summary.get("date")!=day or summary.get("slot")!=slot
                    or summary.get("story_sha256")!=p["story_sha256"]
                    or summary.get("visual_backend")!=backend
                    or summary.get("ready_to_publish") is not False
                    or summary.get("visual_review")!="not_performed"
                    or media["assets"]<21):
                    raise ValueError("Candidate media/metadata or image count invalid")
            result["stored_complete"]+=1
            result["total_bytes"]+=len(blob)
        except (ValueError,KeyError,TypeError,zipfile.BadZipFile,OverflowError):
            result["corrupt"].append({"date":day,"slot":slot})
    if result["corrupt"]:
        raise RuntimeError("Private candidate reserve has corrupt or mismatched files")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--anchor",default="2026-11-21")
    args=p.parse_args()
    print("UMBRAL3_CANDIDATE_INVENTORY="+json.dumps(
        audit(HfBucketStore.from_oidc(),dt.date.fromisoformat(args.anchor)),
        sort_keys=True),flush=True)
