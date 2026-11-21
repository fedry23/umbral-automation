"""Restore one privately indexed unapproved Reel's SIX visual frames.

This is an isolated HF OIDC process. Never writes credentials to disk, never
downloads arbitrary paths, never marks visual work approved or publishable.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

from scripts.umbral3_hf_storage import HfBucketStore
from scripts.umbral3_hf_candidate_index import find
from scripts.umbral3_evidence import verify_media_bundle

def restore(day,slot,backend,story_sha,output):
    from PIL import Image
    if not re.fullmatch("[0-9a-f]{64}",story_sha):
        raise ValueError("Expected immutable editorial SHA")
    store=HfBucketStore.from_oidc()
    pointer=find(store,day,slot,backend)
    if pointer is None or pointer["story_sha256"]!=story_sha:
        raise ValueError("Missing or stale private candidate")
    raw=store.get(pointer["bundle_sha256"]+".zip")
    if raw is None or len(raw)!=pointer["bundle_bytes"]:
        raise RuntimeError("Missing or truncated private full Reel")
    verify_media_bundle(raw)
    if hashlib.sha256(raw).hexdigest()!=pointer["bundle_sha256"]:
        raise ValueError("Full candidate ZIP SHA mismatch")
    output=Path(output)
    if output.is_symlink() or (output.exists() and any(output.iterdir())):
        raise ValueError("Refuse to overwrite an image restoration destination")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        summary=json.loads(archive.read("summary.json"))
        if (summary.get("candidate") is not True or summary.get("ready_to_publish") is not False
            or summary.get("visual_review")!="not_performed"
            or summary.get("date")!=day or summary.get("slot")!=slot
            or summary.get("story_sha256")!=story_sha
            or summary.get("visual_backend")!=backend
            or summary.get("model_revision")!=pointer["model_revision"]):
            raise ValueError("Private candidate is not the requested unapproved story")
        assets={}
        with tempfile.TemporaryDirectory(prefix="umbral3-handoff-") as tmp:
            stage=Path(tmp)
            for i in range(6):
                name=f"scene_{i:02}.png"
                with archive.open(name) as source, (stage/name).open("wb") as dest:
                    while chunk:=source.read(1024*1024):
                        dest.write(chunk)
                file=stage/name
                if file.stat().st_size>25_000_000 or file.stat().st_size==0:
                    raise ValueError("Private image size violation")
                with Image.open(file) as im:
                    if im.format!="PNG" or im.width>=im.height or not 256<=im.width<=2048 or not 256<=im.height<=2048:
                        raise ValueError("Invalid private portrait PNG")
                    im.verify()
                with Image.open(file) as im:
                    im.load()
                    w,h=im.size
                assets[name]={"bytes":file.stat().st_size,
                              "sha256":hashlib.sha256(file.read_bytes()).hexdigest(),
                              "width":w,"height":h}
            if len({v["sha256"] for v in assets.values()})!=6:
                raise ValueError("Duplicated shots in private media")
            handoff={"version":1,"kind":"umbral3-scene-handoff",
                     "date":day,"slot":slot,"story_sha256":story_sha,
                     "assets":assets,"visual_approved":False}
            output.mkdir(parents=True,exist_ok=True,mode=0o700)
            for i in range(6):
                os.replace(stage/f"scene_{i:02}.png",output/f"scene_{i:02}.png")
            (output/"visuals_manifest.json").write_text(json.dumps(handoff,sort_keys=True),encoding="utf-8")
    print("UMBRAL3_PRIVATE_SCENE_HANDOFF="+json.dumps({
        "date":day,"slot":slot,"backend":backend,"images":6,
        "verified":True,"visual_approved":False,"ready_to_publish":False
    },sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--slot",required=True,choices=["09","21"])
    p.add_argument("--backend",required=True)
    p.add_argument("--story-sha",required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    restore(args.date,args.slot,args.backend,args.story_sha,args.output)
