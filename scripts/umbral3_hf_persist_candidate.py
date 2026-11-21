"""Persist a protected civil-slot video candidate (never marked approved)."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from scripts.umbral3_hf_storage import HfBucketStore
from scripts.umbral3_evidence import persist_fixture

FILENAME=re.compile(r"candidate-(20[0-9]{2}-[01][0-9]-[0-3][0-9])-(09|21)\\.mp4")

def persist(output,filename,summary_path):
    root=Path(output).resolve(strict=True)
    video=(root/filename).resolve(strict=True)
    match=FILENAME.fullmatch(filename)
    if not match or video.parent!=root or video.suffix!=".mp4":
        raise ValueError("Invalid unpublishable candidate filename")
    data=json.loads(Path(summary_path).read_text(encoding="utf-8"))
    if (data.get("candidate") is not True or data.get("media_decoded") is not True
        or data.get("ready_to_publish") is not False
        or data.get("visual_review")!="not_performed"
        or data.get("date")!=match.group(1) or data.get("slot")!=match.group(2)
        or type(data.get("placeholder_episode_number")) is not int
        or not 9101<=data["placeholder_episode_number"]<=9114
        or len(data.get("story_sha256",""))!=64
        or len(data.get("narration_sha256",""))!=64):
        raise ValueError("Invalid private candidate contract")
    store=HfBucketStore.from_oidc()
    receipt=persist_fixture(store,root,video,data)
    payload=store.get(receipt["key"])
    if receipt["bytes"]<100_000 or payload is None or hashlib.sha256(payload).hexdigest()!=receipt["sha256"]:
        raise RuntimeError("Private candidate readback mismatch")
    print("UMBRAL3_PRIVATE_CANDIDATE_STORED="+json.dumps({
        "date":data["date"],"slot":data["slot"],"index":data["index"],
        "key":receipt["key"],"bytes":receipt["bytes"],
        "sha256":receipt["sha256"],"private":True,
        "visual_review":"not_performed","ready_to_publish":False}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--video",required=True)
    p.add_argument("--summary",type=Path,required=True)
    args=p.parse_args()
    persist(args.output,args.video,args.summary)
