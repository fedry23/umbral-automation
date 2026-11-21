"""Read-only exact six-scene review fingerprint for user-accepted private V3.

This command never claims that a ZIP is publishable or owner approved.
It emits content hashes and slot/asset identity for a separate, explicit
GitHub-reviewed approval file. No original images or URLs are printed.
"""
import hashlib
import io
import json
import zipfile
from scripts.umbral3_hf_candidate_index import find
from scripts.umbral3_hf_storage import HfBucketStore
from scripts.umbral3_evidence import verify_media_bundle
from scripts.umbral3_reserve import story_key
from scripts.umbral3_reserve_render import catalogs, load_slot

DATE="2026-11-22"
SLOT="21"
BACKEND="sdxl-lightning-2steps-ov-int8-horror-v3"
EXPECTED_SHA="18f8c19740611eb818eb5262010b85a73d34c1fa96667736e67eecc68b4495a3"

def report(store, entries=None):
    story, day, slot = load_slot(3, __import__("datetime").date(2026,11,21), entries or catalogs())
    if (day, slot) != (DATE, SLOT):
        raise RuntimeError("Unexpected V3 review target")
    pointer=find(store,DATE,SLOT,BACKEND)
    if pointer is None or pointer["bundle_sha256"]!=EXPECTED_SHA or pointer["story_sha256"]!=story_key(story):
        raise RuntimeError("V3 exact reviewed candidate not found")
    raw=store.get(EXPECTED_SHA+".zip")
    if not isinstance(raw,bytes) or len(raw)!=pointer["bundle_bytes"] or hashlib.sha256(raw).hexdigest()!=EXPECTED_SHA:
        raise RuntimeError("V3 archive integrity mismatch")
    verify_media_bundle(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        manifest=json.loads(z.read("manifest.json"))
        summary=json.loads(z.read("summary.json"))
        if (summary.get("visual_backend")!=BACKEND or summary.get("ready_to_publish") is not False
                or summary.get("visual_review")!="not_performed"):
            raise RuntimeError("Unexpected V3 candidate status")
        members=manifest["assets"]
        scenes={f"scene_{i:02}.png":members[f"scene_{i:02}.png"]["sha256"] for i in range(6)}
        for name, digest in scenes.items():
            if hashlib.sha256(z.read(name)).hexdigest()!=digest:
                raise RuntimeError("V3 scene byte mismatch")
    return {"version":1,"date":DATE,"slot":SLOT,"backend":BACKEND,
            "story_sha256":pointer["story_sha256"],"scene_sha256":scenes,
            "candidate_sha256":EXPECTED_SHA,"user_review":"pending_registry_record",
            "ready_to_publish":False}

if __name__=="__main__":
    print("UMBRAL3_REVIEW_FINGERPRINT="+json.dumps(report(HfBucketStore.from_oidc()),sort_keys=True),flush=True)
