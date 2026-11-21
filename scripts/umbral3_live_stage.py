"""Stage an owner-approved, late-numbered UMBRAL Reel for the existing Meta publisher.

Only callable inside the trusted GitHub main workflow. Never accesses Meta or
publishes directly. The older pipeline remains a separate, locked fallback.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

from scripts.episode_state import inventory,receipt_key
from scripts.umbral3_release_policy import approved_slot
from scripts.umbral3_reserve import validated_prepared_images
from scripts.technical_learning import load_profile

ROOT=Path(__file__).resolve().parents[1]
MADRID=ZoneInfo("Europe/Madrid")
REQUIRED=("cover.jpg","story_used.json","caption.txt","branding_timing.json",
          "music.wav","voice.wav","subtitles.ass","intro_card.png","outro_card.png")


def stage(day,slot,root=ROOT,storage_python=None,run=subprocess.run,now=None):
    root=Path(root)
    now=now or dt.datetime.now(MADRID)
    if now.tzinfo is None or now.astimezone(MADRID).date().isoformat()!=day:
        raise RuntimeError("Live staging only allowed for today's Madrid civil date")
    if slot not in ("09","21"):
        raise ValueError("Unsupported publication slot")
    # Official receipts may have changed since GitHub scheduled this job.
    _last,receipts=inventory(root)
    if receipt_key(day,slot) in receipts:
        raise RuntimeError("Already published; never stage a duplicate official slot")
    approved_slot(day,slot,root,now)
    if not isinstance(storage_python,str) or not storage_python.startswith("/tmp/umbral3-hf-storage/"):
        raise RuntimeError("Expected isolated OIDC bucket reader, never a reusable long-lived token")
    target=root/"staged"
    if target.is_symlink() or (target.exists() and any(target.iterdir())):
        raise RuntimeError("Refuse to replace staged media from another workflow")
    from scripts.umbral3_finalize_from_reserve import finalize
    from scripts import stage_morning_reel,stage_daily_reel
    importer=stage_morning_reel if slot=="09" else stage_daily_reel
    with tempfile.TemporaryDirectory(prefix="umbral3-owner-live-") as tmp:
        folder=Path(tmp)
        run([storage_python,"-m","scripts.umbral3_approved_restore",
             "--date",day,"--slot",slot,"--output",str(folder)],
            cwd=root,check=True,timeout=180)
        # An approved private image has NOT yet been published, so we still
        # bind the actual episode number to authoritative current receipts.
        decision=finalize(day,slot,folder,root=root,
                          official_receipts_root=root,private_test=False)
        if (decision.get("ready_to_publish") is not True
                or decision.get("visual_approved") is not True):
            raise RuntimeError("Live finalization did not authorize validated artwork")
        suffix="_09" if slot=="09" else ""
        video=f"umbral_{day.replace('-','')}{suffix}.mp4"
        story=json.loads((folder/"story_used.json").read_text(encoding="utf-8"))
        caption=(folder/"caption.txt").read_text(encoding="utf-8")
        importer.verify_story(story,caption,day)
        if story.get("episode_number")!=decision["episode_number"]:
            raise RuntimeError("Final episode changed between render and media staging")
        if story.get("technical_profile")!=load_profile(day,slot,root):
            raise RuntimeError("Stale audiovisual experiment in private video")
        importer.validate_cover(folder/"cover.jpg")
        importer.validate_mp4(folder/video)
        if (not caption.startswith(f"Historia {decision['episode_number']}: {story['title']}\\n")
                or not (folder/"subtitles.ass").read_text(encoding="utf-8").count("Dialogue:")):
            raise RuntimeError("Late-numbered audio/caption/subtitles invalid")
        timings=json.loads((folder/"branding_timing.json").read_text(encoding="utf-8"))
        if not 0<timings["intro_end"]<timings["outro_start"]<timings["duration"]:
            raise RuntimeError("Final branding timings corrupt")
        target.mkdir(parents=True,exist_ok=False)
        for name in (*REQUIRED,video):
            p=folder/name
            if not p.is_file() or p.is_symlink():
                raise RuntimeError("Required final media missing: "+name)
            shutil.copy2(p,target/name)
    return {"date":day,"slot":slot,"episode_number":decision["episode_number"],
            "video":str(target/video),"image_source":"owner-approved-private",
            "ready_for_meta_preflight":True,
            "published":False}


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--slot",required=True,choices=["09","21"])
    p.add_argument("--storage-python",default="/tmp/umbral3-hf-storage/bin/python")
    args=p.parse_args()
    print("UMBRAL3_OFFICIAL_STAGED="+json.dumps(
        stage(args.date,args.slot,storage_python=args.storage_python),sort_keys=True))
