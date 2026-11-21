"""Read-only fingerprint evidence for the actual owner-reviewed 84-image mixed board.

An explicit owner's approval arrives separately via chat. This command proves
the board identity, fourteen immutable private ZIPs, exact date/slot/story
and 84 scene hashes; it MUST NEVER create approval records or publish media.
"""
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import tempfile
import zipfile

from PIL import Image
from scripts.umbral3_evidence import verify_media_bundle
from scripts.umbral3_hf_candidate_index import find
from scripts.umbral3_hf_storage import HfBucketStore
from scripts.umbral3_reserve import story_key
from scripts.umbral3_reserve_render import catalogs, load_slot
from scripts.umbral3_selective_plan import backend_for, TITLE_AND_SHOTS

ANCHOR=dt.date(2026,11,21)
BOARD_SHA="859be1ef1001f5be6476c87db5c90a47f866a30b19d91a39597bbea748e14b2e"
BOARD="umbral3/private-review/_boards/umbral-2026-11-21-v3-v31-priority-mix-14-scenes-"+BOARD_SHA+".jpg"


def fingerprints(store):
    store._ensure_auth()
    matches=[x for x in store.api.list_bucket_tree(store.bucket,recursive=True,token=store.token)
             if getattr(x,"path",None)==BOARD]
    if len(matches)!=1 or matches[0].size!=1902350:
        raise RuntimeError("Owner-reviewed private board missing/changed")
    with tempfile.TemporaryDirectory(prefix="umbral3-owner-evidence-") as temp:
        target=Path(temp)/"review.jpg"
        store.api.download_bucket_files(store.bucket,files=[(BOARD,target)],token=store.token)
        if (target.stat().st_size!=1902350 or
            hashlib.sha256(target.read_bytes()).hexdigest()!=BOARD_SHA):
            raise RuntimeError("Owner-reviewed board SHA256 mismatch")
        with Image.open(target) as image:
            if image.format!="JPEG" or image.size!=(2664,3032):
                raise RuntimeError("Owner-reviewed board format mismatch")
            image.verify()
    catalog=catalogs()
    entries=[]
    for index in range(14):
        story,day,slot=load_slot(index,ANCHOR,catalog)
        if story["title"]!=TITLE_AND_SHOTS[index][0]:
            raise RuntimeError("Editorial title changed after visual review")
        backend=backend_for(index)
        pointer=find(store,day,slot,backend)
        if not pointer or pointer["story_sha256"]!=story_key(story):
            raise RuntimeError("Missing or stale private reviewed candidate")
        bundle=store.get(pointer["bundle_sha256"]+".zip")
        if (bundle is None or len(bundle)!=pointer["bundle_bytes"] or
            hashlib.sha256(bundle).hexdigest()!=pointer["bundle_sha256"]):
            raise RuntimeError("Reviewed candidate ZIP SHA mismatch")
        verify_media_bundle(bundle)
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            summary=json.loads(archive.read("summary.json"))
            if (summary.get("date")!=day or summary.get("slot")!=slot
                or summary.get("visual_backend")!=backend
                or summary.get("story_sha256")!=pointer["story_sha256"]
                or summary.get("ready_to_publish") is not False):
                raise RuntimeError("Reviewed story metadata mismatch")
            hashes={}
            for scene in range(6):
                name=f"scene_{scene:02}.png"
                hashes[name]=hashlib.sha256(archive.read(name)).hexdigest()
        entries.append({"index":index,"date":day,"slot":slot,
                        "title":story["title"],"backend":backend,
                        "story_sha256":pointer["story_sha256"],
                        "bundle_sha256":pointer["bundle_sha256"],
                        "scene_sha256":hashes})
    if len(entries)!=14 or sum(len(e["scene_sha256"]) for e in entries)!=84:
        raise RuntimeError("Incomplete owner-reviewed image evidence")
    return {"board_sha256":BOARD_SHA,"images":84,"stories":14,
            "review_scope":"owner-approved-images-only",
            "candidates_remain_unapproved_in_private_storage":True,
            "entries":entries}


if __name__=="__main__":
    print("UMBRAL3_OWNER_REVIEW_FINGERPRINTS="+json.dumps(
        fingerprints(HfBucketStore.from_oidc()),sort_keys=True),flush=True)
