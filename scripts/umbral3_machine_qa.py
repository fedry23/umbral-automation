"""Evidence-based automatic artistic QA; it is NOT an owner signoff.

Uses a pinned public CLIP vision-language model plus hard local integrity gates.
All receipts stay in the private HF bucket; never post media or Meta credentials.
An undecidable, missing-model or poor-quality result cannot be promoted.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import zipfile

from scripts.umbral3_hf_candidate_index import find, remote_name
from scripts.umbral3_lightning_scenes import PIN
from scripts.umbral3_refill_gate import BACKEND
from scripts.umbral3_reserve import story_key
from scripts.umbral3_evidence import verify_media_bundle

ROOT=Path(__file__).resolve().parents[1]
MODEL="openai/clip-vit-base-patch32"
REVISION="d15b5f29721ca72dac15f8526b284be910de18be"
POLICY="umbral3-machine-qa-v1"
PREFIX="umbral3/automatic-qa/"
SHA=re.compile(r"[0-9a-f]{64}")
SCENES=[f"scene_{i:02}.png" for i in range(6)]
THRESHOLD={"min_scene_matches":4,"min_horror_votes":4,
           "max_semantic_rank":3,"min_horror_margin":0.6}


def story_for(root,day,slot):
    from scripts.storyboard import validate_storyboard
    if slot not in ("09","21") or dt.date.fromisoformat(day).isoformat()!=day:
        raise ValueError("Invalid machine QA date or slot")
    src=Path(root)/("stories_morning.json" if slot=="09" else "stories.json")
    stories=json.loads(src.read_text(encoding="utf-8"))
    matches=[x for x in stories if x.get("publish_date")==day]
    if len(matches)!=1:
        raise RuntimeError("Machine QA requires exactly one authored story")
    validate_storyboard(matches[0])
    return matches[0]


def assess_logits(scores):
    """Require subject relevance AND a dark/unsettling signal from six actual frames.

    Each row: six story-shot image/text logits, then horror, cheerful, neutral.
    Relative scores are not calibrated probabilities; fail closed on ambiguity.
    """
    import math
    if (not isinstance(scores,list) or len(scores)!=6
            or any(not isinstance(row,list) or len(row)!=9 for row in scores)):
        raise ValueError("Incomplete CLIP visual evidence")
    hits=0
    horror=0
    evidence=[]
    for i,row in enumerate(scores):
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in row):
            raise ValueError("Nonfinite machine vision similarity")
        # The expected storyboard shot must be among the top three authored beats.
        rank=1+sum(v>row[i] for k,v in enumerate(row[:6]) if k!=i)
        margin=row[6]-max(row[7],row[8])
        if rank<=THRESHOLD["max_semantic_rank"]:
            hits+=1
        if margin>=THRESHOLD["min_horror_margin"]:
            horror+=1
        evidence.append({"scene":i,"shot_rank":rank,
                         "horror_margin":round(margin,3)})
    passed=hits>=THRESHOLD["min_scene_matches"] and horror>=THRESHOLD["min_horror_votes"]
    return {"passed":passed,"matching_scenes":hits,"horror_scenes":horror,
            "evidence":evidence}


def _prompts(story):
    # CLIP truncates at 77 tokens. Preserve both subject and final anomaly.
    lines=[]
    for shot in story["scenes"]:
        prompt=shot["visual_prompt"] if isinstance(shot,dict) else str(shot)
        words=prompt.split()
        concise=words[:32]+(words[-28:] if len(words)>60 else words[32:])
        lines.append("Photorealistic cinematic horror still: "+" ".join(concise))
    return lines+[
        "A dark photorealistic cinematic horror scene, ominous shadow, unsettling supernatural threat",
        "A colorful cheerful children's illustration with smiling friends in bright sunshine",
        "A neutral bright corporate office stock photograph of furniture",
    ]


def _clip_logits(images,story):
    import torch
    from transformers import CLIPModel, CLIPProcessor
    processor=CLIPProcessor.from_pretrained(MODEL,revision=REVISION)
    model=CLIPModel.from_pretrained(MODEL,revision=REVISION,use_safetensors=True)
    model.eval()
    inputs=processor(images=images,text=_prompts(story),return_tensors="pt",
                     padding=True,truncation=True)
    with torch.inference_mode():
        result=model(**inputs).logits_per_image.float().cpu().tolist()
    if len(result)!=6:
        raise RuntimeError("CLIP failed to assess every scene")
    return result


def evaluate_bundle(raw,story,day,slot,backend=BACKEND,semantic=None):
    from PIL import Image
    from image_quality import assess_image
    verify_media_bundle(raw)
    story_digest=story_key(story)
    if backend!=BACKEND:
        raise RuntimeError("Automatic QA only permits the pinned full horror V3 backend")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        summary=json.loads(archive.read("summary.json"))
        if (summary.get("candidate") is not True
                or summary.get("date")!=day or summary.get("slot")!=slot
                or summary.get("story_sha256")!=story_digest
                or summary.get("visual_backend")!=backend
                or summary.get("model_revision")!=PIN
                or summary.get("media_decoded") is not True
                or summary.get("ready_to_publish") is not False
                or summary.get("visual_review")!="not_performed"):
            raise RuntimeError("Stale or non-private cinematic candidate")
        generated=json.loads(archive.read("image_quality_report.json"))
        timeline=json.loads(archive.read("shot_timeline.json"))
        used=json.loads(archive.read("story_used.json"))
        if (len(generated)!=6 or len(timeline)!=6
                or used.get("title")!=story["title"]
                or not isinstance(used.get("episode_number"),int)
                or not 9101<=used["episode_number"]<=9114
                or any(a.get("end")!=b.get("start") for a,b in zip(timeline,timeline[1:]))):
            raise RuntimeError("Bad storyboard, image report or timeline")
        images=[]
        photometric=[]
        for i,key in enumerate(SCENES):
            with Image.open(io.BytesIO(archive.read(key))) as image:
                image.load()
                if image.format!="PNG" or image.size!=(512,896):
                    raise RuntimeError("Unexpected private scene format/resolution")
                rgb=image.convert("RGB")
            score,reasons=assess_image(rgb,images[-1] if images else None)
            if reasons or score<10 or generated[i].get("scene")!=i+1:
                raise RuntimeError("Unacceptable or mismatched scene image")
            if not isinstance(generated[i].get("accepted_score"),(int,float)):
                raise RuntimeError("Missing saved CPU image-quality evidence")
            images.append(rgb)
            photometric.append(score)
        with Image.open(io.BytesIO(archive.read("cover.jpg"))) as cover:
            if cover.size!=(1080,1920) or cover.format!="JPEG":
                raise RuntimeError("Invalid final cover dimensions")
            cover.verify()
        # Caller may supply synthetic scores only in local unit tests. Runtime
        # always invokes the actual pinned CLIP model on ALL six restored PNGs.
        scores=_clip_logits(images,story) if semantic is None else semantic
        outcome=assess_logits(scores)
        if not outcome["passed"]:
            raise RuntimeError("Visual semantics or horror atmosphere below acceptance gate")
        return {"version":1,"kind":"umbral3-automatic-machine-qa",
                "policy":POLICY,"date":day,"slot":slot,
                "story_sha256":story_digest,"backend":backend,
                "model_revision":PIN,"clip_model":MODEL,"clip_revision":REVISION,
                "scene_sha256":{key:hashlib.sha256(archive.read(key)).hexdigest() for key in SCENES},
                "image_scores":photometric,"semantic":outcome,
                "human_review":False,"machine_approved":True,
                "ready_to_publish":False}


def _remote(day,slot,backend):
    remote_name(day,slot,backend)
    return f"{PREFIX}{day}/{slot}/{backend}.json"


def _get(store,remote):
    store._ensure_auth()
    matches=[x for x in store.api.list_bucket_tree(store.bucket,recursive=True,token=store.token)
             if getattr(x,"path",None)==remote]
    if len(matches)>1:
        raise RuntimeError("Conflicting machine QA receipts")
    if not matches:
        return None
    if type(matches[0].size) is not int or not 100<=matches[0].size<=9000:
        raise RuntimeError("Unsafe machine QA receipt size")
    with tempfile.TemporaryDirectory(prefix="umbral3-automatic-receipt-") as tmp:
        p=Path(tmp)/"qa.json"
        store.api.download_bucket_files(store.bucket,files=[(remote,p)],token=store.token)
        if p.is_symlink() or p.stat().st_size!=matches[0].size:
            raise RuntimeError("Machine QA readback size mismatch")
        return p.read_bytes()


def _pointer(store,day,slot,root):
    story=story_for(root,day,slot)
    pointer=find(store,day,slot,BACKEND)
    if pointer is None or pointer["story_sha256"]!=story_key(story) or pointer["model_revision"]!=PIN:
        raise RuntimeError("Unindexed or stale private candidate")
    return story,pointer


def check_certificate(store,day,slot,root=ROOT):
    """Fast remote read for live router; NEVER confuses a certificate with owner approval."""
    story,pointer=_pointer(store,day,slot,root)
    raw=_get(store,_remote(day,slot,BACKEND))
    if raw is None:
        raise RuntimeError("No machine QA certificate; legacy must take over")
    row=json.loads(raw)
    fields={"version","kind","policy","date","slot","story_sha256","backend",
            "model_revision","clip_model","clip_revision","scene_sha256",
            "image_scores","semantic","human_review","machine_approved",
            "ready_to_publish","bundle_sha256"}
    if (not isinstance(row,dict) or set(row)!=fields
            or row["version"]!=1 or row["kind"]!="umbral3-automatic-machine-qa"
            or row["policy"]!=POLICY or row["date"]!=day or row["slot"]!=slot
            or row["story_sha256"]!=story_key(story)
            or row["backend"]!=BACKEND or row["model_revision"]!=PIN
            or row["clip_model"]!=MODEL or row["clip_revision"]!=REVISION
            or row["bundle_sha256"]!=pointer["bundle_sha256"]
            or row["human_review"] is not False or row["machine_approved"] is not True
            or row["ready_to_publish"] is not False
            or not isinstance(row["scene_sha256"],dict)
            or set(row["scene_sha256"])!=set(SCENES)
            or any(not isinstance(v,str) or not SHA.fullmatch(v)
                   for v in row["scene_sha256"].values())
            or not isinstance(row["image_scores"],list)
            or len(row["image_scores"])!=6
            or any(type(v) not in (int,float) or v<10 for v in row["image_scores"])
            or not isinstance(row["semantic"],dict)
            or row["semantic"].get("passed") is not True
            or row["semantic"].get("matching_scenes",0)<THRESHOLD["min_scene_matches"]
            or row["semantic"].get("horror_scenes",0)<THRESHOLD["min_horror_votes"]):
        raise RuntimeError("Stale, tampered or ambiguous automated quality certificate")
    return row


def certify(store,day,slot,root=ROOT):
    story,pointer=_pointer(store,day,slot,root)
    remote=_remote(day,slot,BACKEND)
    prior=_get(store,remote)
    if prior is not None:
        return check_certificate(store,day,slot,root)
    raw=store.get(pointer["bundle_sha256"]+".zip")
    if raw is None or len(raw)!=pointer["bundle_bytes"]:
        raise RuntimeError("Candidate ZIP missing or truncated")
    if hashlib.sha256(raw).hexdigest()!=pointer["bundle_sha256"]:
        raise RuntimeError("Private candidate SHA-256 mismatch")
    record=evaluate_bundle(raw,story,day,slot)
    record["bundle_sha256"]=pointer["bundle_sha256"]
    data=json.dumps(record,sort_keys=True,separators=(",",":")).encode()
    if len(data)>9000:
        raise RuntimeError("Unbounded machine certificate")
    store._ensure_auth()
    try:
        store.api.batch_bucket_files(store.bucket,add=[(data,remote)],token=store.token)
    except Exception:
        pass  # Reconcile any uncertain write, never claim success without readback.
    if _get(store,remote)!=data:
        raise RuntimeError("Automatic QA certificate write/readback mismatch")
    return check_certificate(store,day,slot,root)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=["certify","check"],required=True)
    p.add_argument("--date",required=True)
    p.add_argument("--slot",choices=["09","21"],required=True)
    args=p.parse_args()
    from scripts.umbral3_hf_storage import HfBucketStore
    store=HfBucketStore.from_oidc()
    result=(certify(store,args.date,args.slot) if args.mode=="certify"
            else check_certificate(store,args.date,args.slot))
    print("UMBRAL3_AUTOMATIC_QA="+json.dumps({
        "date":args.date,"slot":args.slot,"policy":POLICY,
        "bundle_sha256":result["bundle_sha256"],
        "human_review":False,"machine_approved":True,
        "ready_to_publish":False
    },sort_keys=True),flush=True)


if __name__=="__main__":
    main()
