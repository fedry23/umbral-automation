"""Restore exact owner-approved private scenes for isolated live or test staging.

A private candidate is NOT a publication or a fully reviewed finished video.
This helper refuses stale backend pointers or bundle/scene hashes before it
returns a verified scene manifest. No Meta credentials or POST calls.
"""
import argparse
import json
from pathlib import Path

from scripts.umbral3_hf_candidate_index import find
from scripts.umbral3_hf_restore_candidate import restore
from scripts.umbral3_release_policy import approved_slot,ROOT
from scripts.umbral3_reserve import validated_prepared_images
from scripts.umbral3_visual_approval import require_visual_approval
from scripts.umbral3_reserve_render import catalogs


def approved_restore(day,slot,output,root=ROOT,store=None,now=None,mode="owner"):
    from scripts.umbral3_hf_storage import HfBucketStore
    if mode not in ("owner","machine"):
        raise ValueError("Unsupported artistic authorization type")
    store=store or HfBucketStore.from_oidc()
    if mode=="owner":
        plan=approved_slot(day,slot,root,now)
    else:
        # Independent neural + exact SHA certificate: NEVER a human owner signoff.
        from scripts.umbral3_rollout import read_auto_policy
        from scripts.umbral3_machine_qa import check_certificate
        if day<"2026-11-28" or read_auto_policy(root) is not True:
            raise RuntimeError("Machine approval not authorized for civil day")
        proof=check_certificate(store,day,slot,root)
        plan={"backend":proof["backend"],"bundle_sha256":proof["bundle_sha256"],
              "story_sha256":proof["story_sha256"],"scene_sha256":proof["scene_sha256"]}
    pointer=find(store,day,slot,plan["backend"])
    if (pointer is None
        or pointer["bundle_sha256"]!=plan["bundle_sha256"]
        or pointer["story_sha256"]!=plan["story_sha256"]
        or pointer["visual_approved"] is not False
        or pointer["ready_to_publish"] is not False):
        raise RuntimeError("Private indexed media does not match owner-approved exact candidate")
    # Only after trust checks are complete do we extract private scene bytes.
    restore(day,slot,plan["backend"],plan["story_sha256"],output)
    handoff=json.loads((Path(output)/"visuals_manifest.json").read_text(encoding="utf-8"))
    import json as _json
    editorial=_json.loads((Path(root)/("stories_morning.json" if slot=="09" else "stories.json")).read_text(encoding="utf-8"))
    matches=[s for s in editorial if s.get("publish_date")==day]
    if len(matches)!=1:
        raise RuntimeError("Editorial story changed during private restoration")
    validated_prepared_images(handoff,matches[0],day,slot,output)
    if mode=="owner":
        require_visual_approval(root,day,slot,plan["story_sha256"],handoff["assets"])
    if {k:v["sha256"] for k,v in handoff["assets"].items()}!=plan["scene_sha256"]:
        raise RuntimeError("Restored PNG pixels differ from authorized source")
    if mode=="machine":
        # Written only after OIDC private certificate AND byte-for-byte scene check.
        # Never mark media/handoff as human-reviewed or publishable here.
        (Path(output)/"machine_quality_certificate.json").write_text(
            json.dumps(proof,sort_keys=True),encoding="utf-8")
    return {"date":day,"slot":slot,"backend":plan["backend"],
            "source_bundle_sha256":plan["bundle_sha256"],
            "verified_scenes":6,"owner_reviewed":mode=="owner",
            "machine_approved":mode=="machine",
            "ready_to_publish":False}


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--slot",choices=["09","21"],required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--mode",choices=["owner","machine"],default="owner")
    args=p.parse_args()
    print("UMBRAL3_PRIVATE_ART_RESTORE="+json.dumps(
        approved_restore(args.date,args.slot,args.output,mode=args.mode),sort_keys=True))
