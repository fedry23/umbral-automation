"""Build a SINGLE private cinematic candidate from an authored civil-time slot.

No Instagram tokens, no publishing, no official number reservation. These
separate preview videos carry a reversible placeholder number and MUST NOT
be treated as publishable before human visual review + late finalization.
"""
import argparse
from contextlib import nullcontext
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

from scripts.storyboard import validate_storyboard
from scripts.umbral3_queue import narration_id
from scripts.umbral3_reserve import story_key

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Europe/Madrid")

def load_slot(index, anchor, catalogs):
    if type(index) is not int or index not in range(14):
        raise ValueError("Slot index must be 0..13")
    if not isinstance(anchor,dt.date) or isinstance(anchor,dt.datetime):
        raise ValueError("Civil date required")
    day=(anchor+dt.timedelta(days=index//2)).isoformat()
    slot="09" if index%2==0 else "21"
    if set(catalogs)!={"09","21"}:
        raise ValueError("Missing complete editorial catalogs")
    selected=[s for s in catalogs[slot] if s.get("publish_date")==day]
    if len(selected)!=1:
        raise ValueError("Ambiguous or missing authored story")
    story=selected[0]
    validate_storyboard(story)
    story_key(story)
    same=[s for entries in catalogs.values() for s in entries if narration_id(s)==narration_id(story)]
    if len(same)!=1:
        raise ValueError("Duplicate narration across slots")
    if isinstance(story.get("episode_number"),int):
        raise ValueError("Editorial candidate must not preallocate official numbering")
    return story,day,slot

def catalogs():
    return {
        "09":json.loads((ROOT/"stories_morning.json").read_text(encoding="utf-8")),
        "21":json.loads((ROOT/"stories.json").read_text(encoding="utf-8")),
    }

def prepare(index,anchor,store_python,prepared_dir=None):
    if any(os.environ.get(k) for k in ("IG_ACCESS_TOKEN","IG_PUBLISH_ENABLED","UMBRAL_META_PUBLISH_ENABLED")):
        raise RuntimeError("Meta credentials prohibited in candidate generation")
    if not isinstance(store_python,str) or not store_python.startswith("/tmp/umbral3-hf-storage/"):
        raise ValueError("Expected isolated OIDC storage interpreter")
    import render
    from PIL import Image
    story,day,slot=load_slot(index,anchor,catalogs())
    # Never infer or write the actual episode number ahead of Instagram receipt.
    preview={**story,"episode_number":9101+index}
    name=f"candidate-{day}-{slot}.mp4"
    started=time.monotonic()
    if prepared_dir is not None:
        provided=Path(prepared_dir)
        if provided.is_symlink() or not provided.is_dir():
            raise ValueError("Private prepared scene directory is unsafe")
        context=nullcontext(provided)
    else:
        context=tempfile.TemporaryDirectory(prefix="umbral3-preview-")
    with context as directory:
        out=Path(directory)
        if prepared_dir is not None:
            from scripts.umbral3_lightning_scenes import MODEL,PIN
            model=json.loads((out/"model_used.json").read_text(encoding="utf-8"))
            if model.get("model")!=MODEL or model.get("revision")!=PIN:
                raise ValueError("Unpinned private Lightning scene assets")
            visual_record=json.loads((out/"visuals_manifest.json").read_text(encoding="utf-8"))
            video=render.render_story_media(preview,out,dt.date.fromisoformat(day),name,
                                            reserve_slot=slot,prepared_images=visual_record)
        else:
            model={"backend":"sd-turbo-legacy","revision":"unreviewed"}
            video=render.render_story_media(preview,out,dt.date.fromisoformat(day),name)
        if video!=out/name or not video.is_file() or video.stat().st_size<100_000:
            raise RuntimeError("Invalid rendered candidate")
        for item in (video,out/"voice.wav",out/"music.wav"):
            subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(item),"-f","null","-"],
                           check=True,timeout=180)
        for filename in ("cover.jpg","scene_contact_sheet.jpg",*(f"scene_{i:02}.png" for i in range(6))):
            with Image.open(out/filename) as im:
                if filename=="cover.jpg" and (im.size!=(1080,1920) or im.format!="JPEG"):
                    raise ValueError("Invalid cover")
                im.verify()
        timeline=json.loads((out/"shot_timeline.json").read_text(encoding="utf-8"))
        if len(timeline)!=6 or any(a["end"]!=b["start"] for a,b in zip(timeline,timeline[1:])):
            raise ValueError("Shot timeline discontinuity")
        if "Dialogue:" not in (out/"subtitles.ass").read_text(encoding="utf-8"):
            raise ValueError("Missing subtitles")
        quality=json.loads((out/"image_quality_report.json").read_text(encoding="utf-8"))
        if len(quality)!=6:
            raise ValueError("Incomplete image quality report")
        summary={
            "candidate":True,"media_decoded":True,"date":day,"slot":slot,"index":index,
            "placeholder_episode_number":preview["episode_number"],
            "story_sha256":story_key(story),
            "narration_sha256":hashlib.sha256(story["narration"].encode()).hexdigest(),
            "video_bytes":video.stat().st_size,
            "elapsed_seconds":round(time.monotonic()-started,2),
            "image_qa":quality,
            "visual_backend":model["backend"],
            "model_revision":model["revision"],
            "visual_review":"not_performed",
            "ready_to_publish":False,
        }
        if "selective_source" in model:
            source=model["selective_source"]
            from scripts.umbral3_selective_plan import NEW_BACKEND, OLD_BACKEND, selection
            from scripts.umbral3_reserve import _assets
            _,_,_,regenerated=selection(index,anchor)
            pixels={key:item["sha256"] for key,item in _assets(out,6).items()}
            original=source.get("original_scene_sha256",{})
            if (model.get("backend")!=NEW_BACKEND
                    or source.get("base_backend")!=OLD_BACKEND
                    or source.get("story_sha256")!=story_key(story)
                    or tuple(source.get("regenerated",()))!=regenerated
                    or set(original)!=set(pixels)
                    or any(original[key]!=pixels[key] for key in pixels
                           if int(key[6:8]) not in regenerated)
                    or any(original[key]==pixels[key] for key in pixels
                           if int(key[6:8]) in regenerated)):
                raise RuntimeError("Selective render changed preserved pixels or failed to redraw")
            summary["selective_provenance"]={
                "base_bundle_sha256":source["base_bundle_sha256"],
                "original_scene_sha256":original,
                "regenerated":list(regenerated),
                "retained":[i for i in range(6) if i not in regenerated],
                "final_scene_sha256":pixels,
            }
        report=out/"verified_private_candidate.json"
        report.write_text(json.dumps(summary,sort_keys=True),encoding="utf-8")
        subprocess.run([store_python,"-m","scripts.umbral3_hf_persist_candidate",
                        "--output",str(out),"--video",name,"--summary",str(report)],
                       cwd=ROOT,check=True,timeout=180)
        print("UMBRAL3_RESERVE_CANDIDATE="+json.dumps({
            "index":index,"date":day,"slot":slot,"stored":True,
            "visual_review":"not_performed","ready_to_publish":False,
            "elapsed_seconds":round(time.monotonic()-started,2)},sort_keys=True),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=int,required=True)
    p.add_argument("--anchor",required=True)
    p.add_argument("--prepared-dir",type=Path)
    p.add_argument("--single",action="store_true",help="Validate only one D+7 refill slot")
    args=p.parse_args()
    date=dt.date.fromisoformat(args.anchor)
    # An initial batch requires all 14 stories; an incremental refill must only
    # require its two new D+7 slots, not another seven future days of scripts.
    items=catalogs()
    selected=(args.index,) if args.single else range(14)
    for i in selected:
        load_slot(i,date,items)
    python=os.environ.get("UMBRAL_HF_STORAGE_PYTHON","")
    prepare(args.index,date,python,args.prepared_dir)

if __name__=="__main__":
    main()
