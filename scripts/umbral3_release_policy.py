"""Fail-closed release selection for exact owner-approved mixed V3/V3.1 images.

Pure policy needs no HF token or Meta credentials. A verified private source
is never equivalent to permission to POST; the official publisher must still
reconcile Meta and lock the civil slot before publication.
"""
import datetime as dt
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from scripts.episode_state import inventory, receipt_key
from scripts.umbral3_reserve import slots, story_key
from scripts.umbral3_visual_approval import require_visual_approval

ROOT=Path(__file__).resolve().parents[1]
MADRID=ZoneInfo("Europe/Madrid")
SHA=re.compile(r"[0-9a-f]{64}")
BACKENDS={
    "sdxl-lightning-2steps-ov-int8-horror-v3",
    "sdxl-lightning-2steps-ov-int8-horror-v3-1-selective",
}
BOARD="859be1ef1001f5be6476c87db5c90a47f866a30b19d91a39597bbea748e14b2e"


def approved_slot(day,slot,root=ROOT,now=None):
    """Return an exact source identity, never a publish-ready boolean."""
    root=Path(root)
    key=receipt_key(day,slot)
    now=now or dt.datetime.now(MADRID)
    if now.tzinfo is None:
        raise ValueError("Release clock must be timezone-aware")
    now=now.astimezone(MADRID)
    if dt.date.fromisoformat(day)<now.date():
        raise RuntimeError("Historical slot cannot be deployed or republished")
    # Even a valid image cannot be staged against an unresolved Meta intent.
    _last,receipts=inventory(root)
    if key in receipts:
        raise RuntimeError("Official slot already has a verified publication receipt")
    name="stories_morning.json" if slot=="09" else "stories.json"
    stories=json.loads((root/name).read_text(encoding="utf-8"))
    selected=[s for s in stories if s.get("publish_date")==day]
    if len(selected)!=1:
        raise RuntimeError("Missing or ambiguous editorial story for release")
    story=selected[0]
    sha=story_key(story)
    manifest=json.loads((root/"docs/umbral3-owner-visual-signoff-2026-11-21.json").read_text(encoding="utf-8"))
    if (manifest.get("version")!=1 or manifest.get("owner")!="fedry23"
        or manifest.get("private_board_sha256")!=BOARD
        or manifest.get("visual_approved")!=14
        or manifest.get("production_ready") is not False
        or manifest.get("merge_pr_18_authorized") is not False):
        raise RuntimeError("Unexpected owner-review manifest")
    entries=manifest.get("entries",[])
    if not isinstance(entries,list) or len(entries)!=14:
        raise RuntimeError("Incomplete signed-off visual registry")
    matches=[x for x in entries if x.get("date")==day and x.get("slot")==slot]
    if len(matches)>1:
        raise RuntimeError("Conflicting original owner approvals")
    if matches:
        item=matches[0]  # Frozen 84-image review: never change or extend it.
    else:
        # Separate append-only signoffs for future scenes. A valid archived ZIP,
        # visual score or the 2026-11-21 board is NEVER a future owner's review.
        future=root/"docs"/"umbral3-future-signoffs"/(key+".json")
        if not future.is_file():
            raise RuntimeError("No exact owner-approved artwork for civil slot")
        if future.is_symlink() or not 0<future.stat().st_size<=9_000:
            raise RuntimeError("Invalid future owner approval record")
        item=json.loads(future.read_text(encoding="utf-8"))
        required={"version","kind","owner","date","slot","title",
                  "reviewed_at","reviewed_board_sha256","backend","story_sha256",
                  "private_candidate_bundle_sha256","scene_sha256","record"}
        if (not isinstance(item,dict) or set(item)!=required
                or item["version"]!=1
                or item["kind"]!="umbral3-explicit-owner-future-signoff"
                or item["owner"]!="fedry23"
                or item["date"]!=day or item["slot"]!=slot
                or item["title"]!=story["title"]
                or not isinstance(item["reviewed_board_sha256"],str)
                or not SHA.fullmatch(item["reviewed_board_sha256"])):
            raise RuntimeError("Untrusted future owner review metadata")
        approved_file=root/"docs"/"visual_approvals"/(key+".json")
        if not approved_file.is_file() or approved_file.is_symlink():
            raise RuntimeError("Missing independent future visual approval")
        visual=json.loads(approved_file.read_text(encoding="utf-8"))
        if (visual.get("reviewed_at")!=item["reviewed_at"]
                or item["reviewed_board_sha256"] not in visual.get("notes","")
                or item["private_candidate_bundle_sha256"] not in visual.get("notes","")):
            raise RuntimeError("Future owner review evidence is not bound to approved bytes")
    bundle=item.get("private_candidate_bundle_sha256")
    backend=item.get("backend")
    record_name="docs/visual_approvals/"+key+".json"
    assets=item.get("scene_sha256",{})
    if (item.get("story_sha256")!=sha
        or item.get("record")!=record_name
        or backend not in BACKENDS
        or not isinstance(bundle,str) or not SHA.fullmatch(bundle)
        or not isinstance(assets,dict)
        or set(assets)!={f"scene_{i:02}.png" for i in range(6)}):
        raise RuntimeError("Approved slot metadata does not match editorial source")
    require_visual_approval(root,day,slot,sha,{k:{"sha256":v} for k,v in assets.items()})
    return {"date":day,"slot":slot,"title":story["title"],
            "story_sha256":sha,"backend":backend,
            "bundle_sha256":bundle,"scene_sha256":assets,
            "visual_approved":True,"ready_to_publish":False}


def future_coverage(root=ROOT,now=None):
    """Audit the next 14 slots without pretending unreviewed art is safe."""
    now=now or dt.datetime.now(MADRID)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware release planning required")
    report={"as_of":now.astimezone(MADRID).isoformat(),
            "expected_future_slots":14,"approved":0,
            "unapproved_or_missing":[],"all_future_art_approved":False,
            "production_ready":False}
    for target in slots(now,7):
        day,slot=target["date"],target["slot"]
        try:
            item=approved_slot(day,slot,root,now)
        except (RuntimeError,ValueError,KeyError,OSError,TypeError) as exc:
            report["unapproved_or_missing"].append({"date":day,"slot":slot,
                   "reason":str(exc).split(":")[0][:110]})
        else:
            report["approved"]+=1
    report["all_future_art_approved"]=(report["approved"]==14)
    # Image sign-off alone never authorizes final MP4 or Meta publication.
    report["production_ready"]=False
    return report


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--date")
    p.add_argument("--slot",choices=["09","21"])
    p.add_argument("--future",action="store_true")
    p.add_argument("--root",type=Path,default=ROOT)
    args=p.parse_args()
    if args.future:
        result=future_coverage(args.root)
    else:
        if not args.date or not args.slot:
            p.error("--date and --slot required without --future")
        result=approved_slot(args.date,args.slot,args.root)
    print("UMBRAL3_RELEASE_POLICY="+json.dumps(result,sort_keys=True,ensure_ascii=False))
