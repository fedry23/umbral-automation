"""Independent private verification of a 14-Reel mixed V3/V3.1 repair panel.

Checks the seven priority remixes against immutable original scene pixels.
No Meta calls, secrets in output, automatic visual approval or public artifact.
"""
import datetime as dt
import hashlib
import io
import json
import zipfile

from scripts.umbral3_hf_storage import HfBucketStore
from scripts.umbral3_hf_candidate_index import find
from scripts.umbral3_evidence import verify_media_bundle
from scripts.umbral3_reserve_render import catalogs, load_slot
from scripts.umbral3_reserve import story_key
from scripts.umbral3_selective_plan import (
    OLD_BACKEND, NEW_BACKEND, PRIORITY, backend_for, selection,
)

ANCHOR=dt.date(2026,11,21)


def _load(store, pointer):
    if (pointer is None or pointer.get("visual_approved") is not False
            or pointer.get("ready_to_publish") is not False):
        raise RuntimeError("Missing immutable unapproved private candidate")
    blob=store.get(pointer["bundle_sha256"]+".zip")
    if (blob is None or len(blob)!=pointer["bundle_bytes"]
            or hashlib.sha256(blob).hexdigest()!=pointer["bundle_sha256"]):
        raise RuntimeError("Candidate has invalid bundle SHA256")
    verify_media_bundle(blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        report=json.loads(archive.read("summary.json"))
        png={f"scene_{i:02}.png":hashlib.sha256(
            archive.read(f"scene_{i:02}.png")).hexdigest() for i in range(6)}
        if f"candidate-{pointer['date']}-{pointer['slot']}.mp4" not in archive.namelist():
            raise RuntimeError("Missing dated candidate MP4")
    return report,png


def audit(store,anchor=ANCHOR):
    if anchor!=ANCHOR:
        raise ValueError("Unexpected immutable original seven-day batch")
    result={"anchor":anchor.isoformat(),"expected":14,"stored_complete":0,
            "regenerated_slots":0,"regenerated_scenes":0,"preserved_scenes":0,
            "missing":[],"corrupt":[],"private":True,"visual_approved":0,
            "ready_reels":0}
    catalog=catalogs()
    for index in range(14):
        story,day,slot,indices=selection(index,anchor,catalog)
        backend=backend_for(index)
        pointer=find(store,day,slot,backend)
        if pointer is None:
            result["missing"].append({"date":day,"slot":slot,"backend":backend})
            continue
        try:
            if pointer["story_sha256"]!=story_key(story):
                raise RuntimeError("Indexed story SHA changed")
            report,sha=_load(store,pointer)
            if (report.get("date")!=day or report.get("slot")!=slot
                    or report.get("visual_backend")!=backend
                    or report.get("story_sha256")!=pointer["story_sha256"]
                    or report.get("ready_to_publish") is not False
                    or report.get("visual_review")!="not_performed"):
                raise RuntimeError("Untrusted private candidate summary")
            if index in PRIORITY:
                original=find(store,day,slot,OLD_BACKEND)
                if original is None or original["story_sha256"]!=pointer["story_sha256"]:
                    raise RuntimeError("Missing original immutable V3 story")
                _,base_sha=_load(store,original)
                provenance=report.get("selective_provenance",{})
                if (provenance.get("base_bundle_sha256")!=original["bundle_sha256"]
                        or provenance.get("original_scene_sha256")!=base_sha
                        or provenance.get("final_scene_sha256")!=sha
                        or provenance.get("regenerated")!=list(indices)
                        or provenance.get("retained")!=[i for i in range(6) if i not in indices]):
                    raise RuntimeError("Selective provenance does not match original archive")
                if any((base_sha[f"scene_{i:02}.png"]==sha[f"scene_{i:02}.png"])
                       == (i in indices) for i in range(6)):
                    raise RuntimeError("Selective regeneration changed a retained scene")
                result["regenerated_slots"]+=1
                result["regenerated_scenes"]+=len(indices)
                result["preserved_scenes"]+=6-len(indices)
            else:
                if backend!=OLD_BACKEND or "selective_provenance" in report:
                    raise RuntimeError("Non-priority candidate was changed")
                result["preserved_scenes"]+=6
            result["stored_complete"]+=1
        except (RuntimeError,ValueError,KeyError,TypeError,IndexError,
                zipfile.BadZipFile,OverflowError):
            result["corrupt"].append({"date":day,"slot":slot,"backend":backend})
    if result["missing"] or result["corrupt"]:
        raise RuntimeError("Mixed private repair set is incomplete or mismatched: "
                           +json.dumps(result,sort_keys=True))
    if result["regenerated_slots"]!=7 or result["preserved_scenes"]+result["regenerated_scenes"]!=84:
        raise RuntimeError("Private repair coverage does not equal 84 scenes")
    return result


if __name__=="__main__":
    print("UMBRAL3_SELECTIVE_AUDIT="+json.dumps(
        audit(HfBucketStore.from_oidc()),sort_keys=True),flush=True)
