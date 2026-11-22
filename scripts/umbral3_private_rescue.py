"""Isolated one-slot V3.1 cinematic rescue; immutable private evidence only.

Triggered by owner-authorized main GitHub Actions job. No Meta, no publication,
no overwrite of the rejected V3 candidate or existing machine QA receipts.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

from scripts.umbral3_machine_qa import RECOVERY_BACKEND, story_for
from scripts.umbral3_hf_candidate_index import find
from scripts.umbral3_lightning_scenes import PIN
from scripts.umbral3_refill_gate import assert_generation_budget
from scripts.umbral3_reserve import story_key
from scripts.umbral3_evidence import verify_media_bundle

ROOT=Path(__file__).resolve().parents[1]


def check(store,day,slot,root=ROOT):
    from scripts.umbral3_reserve_render import catalogs,load_slot
    if dt.date.fromisoformat(day).isoformat()!=day or day<"2026-11-28":
        raise ValueError("Rescue only for authorized future civil dates")
    if slot not in ("09","21"):
        raise ValueError("Wrong civil slot")
    index=0 if slot=="09" else 1
    story,checked,checked_slot=load_slot(index,dt.date.fromisoformat(day),catalogs())
    if checked!=day or checked_slot!=slot or story_key(story)!=story_key(story_for(root,day,slot)):
        raise RuntimeError("Rescue editorial mismatch")
    pointer=find(store,day,slot,RECOVERY_BACKEND)
    if pointer is None:
        assert_generation_budget(store)
        return {"date":day,"slot":slot,"index":index,"generate":True,
                "backend":RECOVERY_BACKEND,"ready_to_publish":False}
    if pointer["story_sha256"]!=story_key(story) or pointer["model_revision"]!=PIN:
        raise RuntimeError("Stale or modified immutable rescue candidate")
    raw=store.get(pointer["bundle_sha256"]+".zip")
    if raw is None or len(raw)!=pointer["bundle_bytes"] or hashlib.sha256(raw).hexdigest()!=pointer["bundle_sha256"]:
        raise RuntimeError("Private V3.1 candidate missing or corrupt")
    verify_media_bundle(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        summary=json.loads(archive.read("summary.json"))
        if (summary.get("date")!=day or summary.get("slot")!=slot
                or summary.get("story_sha256")!=story_key(story)
                or summary.get("visual_backend")!=RECOVERY_BACKEND
                or summary.get("model_revision")!=PIN
                or summary.get("ready_to_publish") is not False
                or summary.get("visual_review")!="not_performed"
                or summary.get("candidate") is not True
                or f"candidate-{day}-{slot}.mp4" not in archive.namelist()):
            raise RuntimeError("Unexpected private rescue media contract")
    return {"date":day,"slot":slot,"index":index,"generate":False,
            "backend":RECOVERY_BACKEND,"stored_full_candidate":True,
            "bundle_sha256":pointer["bundle_sha256"],"ready_to_publish":False}


def main():
    from scripts.umbral3_hf_storage import HfBucketStore
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--slot",choices=["09","21"],required=True)
    p.add_argument("--require-stored",action="store_true")
    args=p.parse_args()
    result=check(HfBucketStore.from_oidc(),args.date,args.slot)
    if args.require_stored and result["generate"]:
        raise RuntimeError("No completed private rescue media after generation")
    out=os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out,"a",encoding="utf-8") as fd:
            fd.write("generate="+("true" if result["generate"] else "false")+"\n")
            fd.write("index="+str(result["index"])+"\n")
    print("UMBRAL3_PRIVATE_HORROR_RESCUE="+json.dumps(result,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
