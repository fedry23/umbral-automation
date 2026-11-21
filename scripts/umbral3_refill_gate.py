"""Autonomous D+7 private Reel refill preflight, fail closed.

The scheduled job will exist on main only after a guarded release and a
separate main-branch Hugging Face Trusted Publisher authorization.
No publication rights, no cleanup, no image generation when indexed media
has already passed full SHA-256 verification.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
from zoneinfo import ZoneInfo
import zipfile

from scripts.umbral3_hf_candidate_index import find
from scripts.umbral3_lightning_scenes import PIN
from scripts.umbral3_reserve import story_key
from scripts.umbral3_reserve_render import catalogs,load_slot
from scripts.umbral3_evidence import verify_media_bundle

MADRID=ZoneInfo("Europe/Madrid")
BACKEND="sdxl-lightning-2steps-ov-int8-horror-v3"

def check(store, day, slot, all_stories=None):
    if isinstance(day,dt.datetime) or type(day) is not dt.date or slot not in ("09","21"):
        raise ValueError("Refill requires civil date and supported slot")
    target=day+dt.timedelta(days=7)
    index=0 if slot=="09" else 1
    story,when,civil=load_slot(index,target,all_stories or catalogs())
    digest=story_key(story)
    pointer=find(store,when,civil,BACKEND)
    result={"anchor":when,"slot":civil,"index":index,"date":when,
            "story_sha256":digest,"generated":False,
            "ready_to_publish":False}
    if pointer is None:
        result["generate"]=True
        return result
    if pointer["story_sha256"]!=digest:
        raise RuntimeError("A previously indexed candidate has a stale story")
    if pointer.get("model_revision")!=PIN:
        raise RuntimeError("A previously indexed candidate uses a stale visual model")
    raw=store.get(pointer["bundle_sha256"]+".zip")
    if raw is None or len(raw)!=pointer["bundle_bytes"]:
        raise RuntimeError("A previously indexed candidate is missing")
    if hashlib.sha256(raw).hexdigest()!=pointer["bundle_sha256"]:
        raise RuntimeError("A previously indexed candidate has corrupt bytes")
    verify_media_bundle(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        report=json.loads(z.read("summary.json"))
        if (report.get("candidate") is not True
                or report.get("date")!=when or report.get("slot")!=civil
                or report.get("story_sha256")!=digest
                or report.get("visual_backend")!=BACKEND
                or report.get("ready_to_publish") is not False
                or report.get("visual_review")!="not_performed"
                or f"candidate-{when}-{civil}.mp4" not in z.namelist()):
            raise RuntimeError("Refill found mismatched or potentially publishable candidate")
    result["generate"]=False
    result["stored_full_candidate"]=True
    return result

def assert_generation_budget(store):
    """Reject costly CPU generation BEFORE downloading models when HF space is low.

    A complete ZIP can legally reach LIMIT; reserve extra preview/index space
    and keep the existing 100 MB emergency headroom. No deletes/overwrites.
    """
    from scripts.umbral3_evidence import quota, HEADROOM
    from scripts.umbral3_storage import LIMIT
    expected_free = LIMIT + HEADROOM + 20_000_000
    available = quota(store)["free"]
    if available < expected_free:
        raise RuntimeError("Private D+7 storage below safe generation budget")
    return {"capacity_verified": True, "minimum_required_bytes": expected_free}


def batch_target(anchor, index):
    """Map an existing fourteen-slot date/index to check()'s D+7 input.

    No token exchange or media generation: a private batch must not rebuild
    a fully verified V3 candidate, nor reuse the original visual backend.
    """
    if (type(anchor) is not dt.date or type(index) is not int
            or index not in range(14)):
        raise ValueError("Invalid private batch anchor or index")
    day=anchor+dt.timedelta(days=index//2)
    return day-dt.timedelta(days=7), ("09" if index%2==0 else "21")

def main():
    from scripts.umbral3_hf_storage import HfBucketStore
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--slot",choices=["09","21"],
                      help="Scheduled D+7 slot, based on Madrid civil today")
    mode.add_argument("--index",type=int,
                      help="Explicit immutable private fourteen-slot batch index")
    parser.add_argument("--today")
    parser.add_argument("--anchor")
    args=parser.parse_args()
    if args.index is not None:
        if args.today is not None or args.anchor is None:
            parser.error("--index requires --anchor and rejects --today")
        today,slot=batch_target(dt.date.fromisoformat(args.anchor),args.index)
    else:
        if args.anchor is not None:
            parser.error("--anchor is only valid with --index")
        today=(dt.date.fromisoformat(args.today) if args.today else
               dt.datetime.now(MADRID).date())
        slot=args.slot
    store=HfBucketStore.from_oidc()
    result=check(store,today,slot)
    if result["generate"]:
        result.update(assert_generation_budget(store))
    print("UMBRAL3_REFILL="+json.dumps(result,sort_keys=True),flush=True)
    out=os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out,"a",encoding="utf-8") as fh:
            fh.write(f"generate={'true' if result['generate'] else 'false'}\n")
            fh.write(f"anchor={result['anchor']}\n")
            fh.write(f"index={result['index']}\n")

if __name__=="__main__":
    main()
