"""Privately recover unchanged V3 PNGs before selective V3.1 re-render.

Original ZIPs and index entries remain immutable. This may only write local
temporary output; publishability and owner approval are always FALSE.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile

from scripts.umbral3_evidence import verify_media_bundle
from scripts.umbral3_hf_candidate_index import find
from scripts.umbral3_hf_storage import HfBucketStore
from scripts.umbral3_reserve import _assets, story_key
from scripts.umbral3_selective_plan import OLD_BACKEND, NEW_BACKEND, selection


def _verified(store, pointer):
    if (pointer is None or pointer.get("ready_to_publish") is not False
            or pointer.get("visual_approved") is not False):
        raise ValueError("Unapproved private candidate required")
    blob=store.get(pointer["bundle_sha256"]+".zip")
    if (blob is None or len(blob)!=pointer["bundle_bytes"]
            or hashlib.sha256(blob).hexdigest()!=pointer["bundle_sha256"]):
        raise RuntimeError("Original private ZIP failed SHA-256 readback")
    verify_media_bundle(blob)
    return blob


def prepare(store, index, anchor, output):
    story,day,slot,replace=selection(index,anchor)
    sha=story_key(story)
    target=find(store,day,slot,NEW_BACKEND)
    if target is not None:
        if target["story_sha256"]!=sha:
            raise RuntimeError("Stale selective candidate would overwrite reviewed story")
        blob=_verified(store,target)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            summary=json.loads(z.read("summary.json"))
        provenance=summary.get("selective_provenance",{})
        if (summary.get("date")!=day or summary.get("slot")!=slot
                or summary.get("visual_backend")!=NEW_BACKEND
                or tuple(provenance.get("regenerated",()))!=replace
                or summary.get("ready_to_publish") is not False):
            raise RuntimeError("Existing selective candidate does not match recipe")
        return {"generate":False,"date":day,"slot":slot,"index":index,
                "ready_to_publish":False,"reused_full_candidate":True}
    base=find(store,day,slot,OLD_BACKEND)
    if base is None or base["story_sha256"]!=sha:
        raise RuntimeError("Expected original V3 archive missing or editorially stale")
    blob=_verified(store,base)
    output=Path(output)
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("Selective recovery requires an empty private directory")
    output.mkdir(parents=True,exist_ok=True,mode=0o700)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        summary=json.loads(z.read("summary.json"))
        if (summary.get("date")!=day or summary.get("slot")!=slot
                or summary.get("story_sha256")!=sha
                or summary.get("visual_backend")!=OLD_BACKEND
                or summary.get("ready_to_publish") is not False
                or summary.get("visual_review")!="not_performed"):
            raise ValueError("Untrusted original V3 story or slot")
        original={}
        for i in range(6):
            name=f"scene_{i:02}.png"
            data=z.read(name)
            (output/name).write_bytes(data)
            original[name]=hashlib.sha256(data).hexdigest()
    if {k:v["sha256"] for k,v in _assets(output,6).items()}!=original:
        raise RuntimeError("Restored original scene hashes have changed")
    record={"version":1,"index":index,"date":day,"slot":slot,
            "story_sha256":sha,"base_backend":OLD_BACKEND,
            "base_bundle_sha256":base["bundle_sha256"],
            "original_scene_sha256":original,
            "regenerated":list(replace),
            "retained":[i for i in range(6) if i not in replace]}
    (output/"selective_source.json").write_text(json.dumps(record,sort_keys=True))
    return {"generate":True,"date":day,"slot":slot,"index":index,
            "regenerate":list(replace),"preserve":record["retained"],
            "ready_to_publish":False,"reused_full_candidate":False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--anchor",required=True)
    parser.add_argument("--index",required=True,type=int)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=prepare(HfBucketStore.from_oidc(),args.index,
                   dt.date.fromisoformat(args.anchor),args.output)
    print("UMBRAL3_SELECTIVE_PREPARE="+json.dumps(result,sort_keys=True),flush=True)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as f:
            f.write("generate="+("true" if result["generate"] else "false")+"\n")


if __name__=="__main__":
    main()
