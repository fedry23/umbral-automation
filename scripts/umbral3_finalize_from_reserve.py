"""Late-bind the official episode number to SHA-verified six-scene media.

This does NOT contact Meta, publish, or decide visual approval. Candidate
image transfer happens separately with an OIDC-scoped storage interpreter.
All image generation is skipped: only the short voice/branding and encode
steps are repeated, to avoid speculative numbers in the private reserve.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

from scripts.umbral3_reserve_render import catalogs
from scripts.umbral3_reserve import validated_prepared_images
from scripts.episode_state import planned_episode, receipt_key
from scripts.technical_learning import load_profile

ROOT=Path(__file__).resolve().parents[1]
TZ=ZoneInfo("Europe/Madrid")

def select(day,slot,root):
    if slot not in ("09","21") or dt.date.fromisoformat(day).isoformat()!=day:
        raise ValueError("Invalid target civil time")
    path=root/("stories_morning.json" if slot=="09" else "stories.json")
    stories=json.loads(path.read_text(encoding="utf-8"))
    exact=[s for s in stories if s.get("publish_date")==day]
    if len(exact)!=1:
        raise ValueError("Missing or ambiguous civil-slot editorial story")
    return exact[0]



def require_machine_evidence(proof,day,slot,story,assets,root=ROOT):
    """Second independent gate after OIDC restoration and PNG SHA checks.

    Machine approval is NOT human approval. Prevent a backend substitution,
    missing visual score, forged quality flag or future-stale certificate from
    reusing the official finalizer. The private restore stage has already
    matched these scene bytes to the exact private indexed ZIP.
    """
    import re
    from scripts.umbral3_machine_qa import (
        SUPPORTED_BACKENDS,POLICY,PIN,SCENES,MODEL,REVISION,THRESHOLD)
    from scripts.umbral3_rollout import read_auto_policy
    from scripts.umbral3_reserve import story_key
    expected={key:assets[key]["sha256"] for key in SCENES}
    if (day<"2026-11-28" or read_auto_policy(root) is not True
            or not isinstance(proof,dict)
            or proof.get("version")!=1
            or proof.get("kind")!="umbral3-automatic-machine-qa"
            or proof.get("policy")!=POLICY
            or proof.get("date")!=day or proof.get("slot")!=slot
            or proof.get("story_sha256")!=story_key(story)
            or proof.get("backend") not in SUPPORTED_BACKENDS
            or proof.get("model_revision")!=PIN
            or proof.get("clip_model")!=MODEL
            or proof.get("clip_revision")!=REVISION
            or not isinstance(proof.get("bundle_sha256"),str)
            or re.fullmatch(r"[0-9a-f]{64}",proof["bundle_sha256"]) is None
            or proof.get("human_review") is not False
            or proof.get("machine_approved") is not True
            or proof.get("ready_to_publish") is not False
            or proof.get("scene_sha256")!=expected
            or not isinstance(proof.get("image_scores"),list)
            or len(proof["image_scores"])!=6
            or any(type(x) not in (int,float) or x<10 for x in proof["image_scores"])
            or not isinstance(proof.get("semantic"),dict)
            or proof["semantic"].get("passed") is not True
            or proof["semantic"].get("matching_scenes",0)<THRESHOLD["min_scene_matches"]
            or proof["semantic"].get("horror_scenes",0)<THRESHOLD["min_horror_votes"]):
        raise RuntimeError("Machine certificate does not match restored actual scenes")
    return True

def finalize(day,slot,media_dir,number=None,root=ROOT,private_test=False,official_receipts_root=None,machine_evidence=None):
    media_dir=Path(media_dir)
    if not media_dir.is_dir() or media_dir.is_symlink():
        raise ValueError("Invalid restored private media directory")
    story=select(day,slot,root)
    handoff=json.loads((media_dir/"visuals_manifest.json").read_text(encoding="utf-8"))
    # Fail before TTS/FFmpeg if a different story, slot, or corrupt scene was supplied.
    validated_prepared_images(handoff,story,day,slot,media_dir)
    # Editorial input may be an integration branch with STALE official receipts.
    # Use the separately checked-out, freshest release branch as the sole source
    # of official episode allocation. Do not infer numbers from candidate media.
    receipts_root=Path(official_receipts_root) if official_receipts_root is not None else Path(root)
    if not receipts_root.is_dir() or not (receipts_root/"docs"/"published").is_dir():
        raise RuntimeError("Authoritative official receipts checkout unavailable")
    receipt=receipts_root/"docs"/"published"/(receipt_key(day,slot)+".json")
    if receipt.is_file():
        raise RuntimeError("This official slot already has a publication receipt")
    official=planned_episode(day,slot,root=receipts_root)
    if number is not None and (type(number) is not int or number!=official):
        raise ValueError("Official episode number moved; do not reuse stale media")
    if not private_test:
        if dt.datetime.now(TZ).date().isoformat()!=day:
            raise RuntimeError("Live finalization only allowed on its own civil day")
        # The local handoff flag is untrusted (it comes from restored media).
        # Review is an explicit owner registry entry on the release checkout,
        # bound to the precise six PNG hashes, story and publishing slot.
        from scripts.umbral3_visual_approval import require_visual_approval
        from scripts.umbral3_reserve import story_key
        if machine_evidence is None:
            require_visual_approval(root,day,slot,story_key(story),handoff["assets"])
            review_kind="owner"
        else:
            # The isolated OIDC restore has already checked SHA-bound private
            # certificate + actual six PNGs; recheck without network access.
            require_machine_evidence(machine_evidence,day,slot,story,
                                     handoff["assets"],root)
            review_kind="machine"
        handoff={**handoff,"visual_approved":True}
    elif handoff.get("visual_approved") is not False:
        raise RuntimeError("Private tests may only use unapproved candidates")
    from render import render_story_media
    profile=load_profile(day,slot)
    final_story={**story,"episode_number":official,"technical_profile":profile}
    path=media_dir/f"umbral_{day.replace('-','')}{'_09' if slot=='09' else ''}.mp4"
    output=render_story_media(final_story,media_dir,dt.date.fromisoformat(day),
                              path.name,active_profile=profile,
                              reserve_slot=slot,prepared_images=handoff)
    if output!=path or not output.is_file() or output.stat().st_size<100_000:
        raise RuntimeError("Late-numbered media output invalid")
    subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(output),"-f","null","-"],
                   check=True,timeout=180)
    rendered=json.loads((media_dir/"story_used.json").read_text(encoding="utf-8"))
    if rendered.get("episode_number")!=official or rendered.get("title")!=story["title"]:
        raise RuntimeError("Late numbering not embedded in final story")
    return {"date":day,"slot":slot,"episode_number":official,
            "private_test":bool(private_test),
            "art_authorized":bool(not private_test and handoff["visual_approved"]),
            "owner_reviewed":not private_test and review_kind=="owner",
            "machine_approved":not private_test and review_kind=="machine",
            "visual_approved":handoff["visual_approved"] if not private_test else False,
            "ready_to_publish":bool(not private_test and handoff["visual_approved"]),
            "video_bytes":output.stat().st_size}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--slot",choices=["09","21"],required=True)
    p.add_argument("--media-dir",type=Path,required=True)
    p.add_argument("--private-test",action="store_true")
    p.add_argument("--official-receipts-root",type=Path,
                   help="Fresh authoritative main checkout, never integration receipts")
    args=p.parse_args()
    result=finalize(args.date,args.slot,args.media_dir,
                    private_test=args.private_test,
                    official_receipts_root=args.official_receipts_root)
    print("UMBRAL3_FINALIZATION="+json.dumps(result,sort_keys=True),flush=True)
