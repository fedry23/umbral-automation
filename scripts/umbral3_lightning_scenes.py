"""Fast CPU 2-step SDXL Lightning scene generation for PRIVATE review only.

Runs in an isolated venv. Emits 6 fully verified PNGs and an immutable
story/day/slot SHA-256 handoff, not an approved Reel or public artifact.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

MODEL="rupeshs/SDXL-Lightning-2steps-openvino-int8"
PIN="347b21e571d7b8a716af83f64d68c5c028c51c56"
W,H=512,896

def render_images(index, anchor, output):
    from huggingface_hub import model_info, snapshot_download
    from optimum.intel.openvino.modeling_diffusion import OVStableDiffusionXLPipeline
    from PIL import ImageStat
    import torch
    from render import visual_shots
    from image_quality import assess_image
    from scripts.umbral3_reserve_render import load_slot, catalogs
    from scripts.umbral3_reserve import _assets, story_key
    story,day,slot=load_slot(index,anchor,catalogs())
    if output.exists() and any(output.iterdir()):
        raise ValueError("Private Lightning output must start empty")
    output.mkdir(parents=True,exist_ok=True,mode=0o700)
    direction = os.environ.get("UMBRAL_HORROR_DIRECTION", "original")
    if direction == "horror-v2":
        from scripts.umbral3_horror_direction import directed_prompts
        # Delay until the pinned SDXL tokenizer is available; never truncate
        # the scene action or its horror anomaly without noticing.
        prompts = None
    elif direction == "horror-v3":
        from scripts.umbral3_horror_v3 import directed_prompts_v3
        prompts = None
    elif direction == "horror-v3-1":
        from scripts.umbral3_horror_v31 import directed_prompts_v31
        prompts = None
    elif direction == "original":
        prompts = visual_shots(story)
    else:
        raise ValueError("Unrecognized private horror direction")
    if prompts is not None and (len(prompts)!=6 or len(set(prompts))!=6):
        raise ValueError("Six distinct storyboard prompts required")
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix="umbral3-lightning-model-") as tmp:
        info=model_info(MODEL,revision=PIN,files_metadata=True,timeout=30)
        if info.sha!=PIN:
            raise RuntimeError("Pinned Lightning revision mismatch")
        sizes=[f.size for f in info.siblings]
        if not sizes or any(type(n) is not int for n in sizes):
            raise RuntimeError("Pinned model size unverified")
        if sum(sizes)+2_000_000_000>shutil.disk_usage(tmp).free:
            raise RuntimeError("Not enough disk for model and workspace")
        directory=snapshot_download(MODEL,revision=PIN,max_workers=2)
        pipe=OVStableDiffusionXLPipeline.from_pretrained(
            directory,device="CPU",ov_config={"CACHE_DIR":str(Path(tmp)/"cache")})
        if direction == "horror-v2":
            prompts = directed_prompts(story, pipe.tokenizer)
        elif direction == "horror-v3":
            prompts = directed_prompts_v3(story, pipe.tokenizer)
        elif direction == "horror-v3-1":
            prompts = directed_prompts_v31(story, pipe.tokenizer)
        if len(prompts)!=6 or len(set(prompts))!=6:
            raise ValueError("Six unique visual story beats required")
        report=[]
        images=[]
        for i,prompt in enumerate(prompts):
            tokens=pipe.tokenizer(prompt,truncation=False).input_ids
            if len(tokens)>pipe.tokenizer.model_max_length:
                raise ValueError(f"Shot {i+1}: authored prompt exceeds model context")
            best=None
            attempts=[]
            for attempt in range(2):
                seed=({"original": 730000, "horror-v2": 830000, "horror-v3": 930000, "horror-v3-1": 1030000}[direction]) + index*1000 + i*17 + attempt*123
                started_shot=time.monotonic()
                image=pipe(prompt=prompt,width=W,height=H,
                           num_inference_steps=2,guidance_scale=1.0,
                           generator=torch.Generator(device="cpu").manual_seed(seed)).images[0]
                if image.size!=(W,H) or max(ImageStat.Stat(image).stddev)<2:
                    raise ValueError("Lightning returned flat or wrong-size image")
                score,reasons=assess_image(image,images[-1] if images else None)
                attempts.append({"seed":seed,"seconds":round(time.monotonic()-started_shot,2),
                                 "score":round(score,2),"reasons":reasons})
                if not reasons:
                    best=image
                    break
            if best is None:
                raise RuntimeError(f"Shot {i+1} failed after two bounded retries")
            path=output/f"scene_{i:02}.png"
            best.save(path,format="PNG",optimize=True)
            images.append(best)
            report.append({"scene":i+1,"attempts":attempts,"accepted_score":attempts[-1]["score"]})
            print(f"UMBRAL3_LIGHTNING_SHOT={i+1}/6 seconds={attempts[-1]['seconds']}",flush=True)
        manifest={
            "version":1,
            "kind":"umbral3-scene-handoff",
            "date":day,"slot":slot,
            "story_sha256":story_key(story),
            "assets":_assets(output,6),
            "visual_approved":False,
        }
        (output/"visuals_manifest.json").write_text(json.dumps(manifest,sort_keys=True),encoding="utf-8")
        (output/"image_quality_report.json").write_text(json.dumps(report,sort_keys=True),encoding="utf-8")
        (output/"model_used.json").write_text(json.dumps({
            "backend":("sdxl-lightning-2steps-ov-int8" if direction=="original" else f"sdxl-lightning-2steps-ov-int8-{direction}"),"model":MODEL,
            "direction_version":direction,
            "revision":PIN,"steps":2,
            "seconds":round(time.monotonic()-started,2),
            "visual_review":"not_performed"
        },sort_keys=True),encoding="utf-8")
        print("UMBRAL3_LIGHTNING_SCENES_READY="+json.dumps({
            "date":day,"slot":slot,"images":6,
            "seconds":round(time.monotonic()-started,2),
            "visual_review":"not_performed",
            "ready_to_publish":False
        },sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=int,required=True)
    p.add_argument("--anchor",required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    render_images(args.index,dt.date.fromisoformat(args.anchor),args.output)
