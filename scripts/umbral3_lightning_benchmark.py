"""Isolated, no-credentials CPU feasibility of accelerated SDXL Lightning.

Measure 2 real portrait samples and memory. No output image is uploaded.
This is a TECHNICAL test, not cinematic quality approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import shutil
import tempfile
import time

MODEL = "rupeshs/SDXL-Lightning-2steps-openvino-int8"
PROMPTS = [
    "Realistic cinematic photograph in an abandoned Spanish house: a fresh damp paint wall with five unnatural claw marks emerging, aged oak floorboards, cold moonlight through a single window, 35mm horror film, sharp depth, coherent architecture, no text",
    "Realistic cinematic photograph in the same abandoned Spanish house: an old steel paint scraper lying next to the same wet white wall, five deep claw marks, aged oak floorboards, the same cold moonlight, 35mm horror film, no people, no text"
]

def benchmark():
    from huggingface_hub import model_info, snapshot_download
    from optimum.intel.openvino.modeling_diffusion import OVStableDiffusionXLPipeline
    from PIL import ImageStat
    import torch
    t=time.monotonic()
    with tempfile.TemporaryDirectory(prefix="umbral3-lightning-") as folder:
        meta=model_info(MODEL, files_metadata=True, timeout=35)
        if not isinstance(meta.sha,str) or len(meta.sha)!=40:
            raise RuntimeError("Model revision not pinned")
        sizes=[f.size for f in meta.siblings]
        if not sizes or any(type(n) is not int or n < 0 for n in sizes):
            raise RuntimeError("Model file sizes unverified")
        disk=shutil.disk_usage(folder).free
        if sum(sizes)+2_000_000_000>=disk:
            raise RuntimeError("Insufficient model disk headroom")
        print("UMBRAL3_LIGHTNING_MODEL="+json.dumps({
            "model":MODEL,"sha":meta.sha,"download_bytes":sum(sizes)}),flush=True)
        directory=snapshot_download(MODEL,revision=meta.sha,
                                    local_dir=Path(folder)/"model", max_workers=2)
        downloaded=time.monotonic()
        pipe=OVStableDiffusionXLPipeline.from_pretrained(
            directory, device="CPU", ov_config={"CACHE_DIR":str(Path(folder)/"cache")})
        ready=time.monotonic()
        samples=[]
        for i,prompt in enumerate(PROMPTS):
            started=time.monotonic()
            image=pipe(prompt=prompt,width=512,height=896,
                       num_inference_steps=2,guidance_scale=1.0,
                       generator=torch.Generator(device="cpu").manual_seed(7300+i)).images[0]
            if image.size != (512,896) or max(ImageStat.Stat(image).stddev)<2:
                raise ValueError("Invalid sample")
            samples.append({"shot":i+1,"seconds":round(time.monotonic()-started,2),
                            "sha256_pixels":hashlib.sha256(image.tobytes()).hexdigest()})
        if samples[0]["sha256_pixels"]==samples[1]["sha256_pixels"]:
            raise RuntimeError("Duplicate visuals")
        print("UMBRAL3_LIGHTNING_BENCHMARK="+json.dumps({
            "model":MODEL,"revision":meta.sha,"shots":samples,
            "download_seconds":round(downloaded-t,2),
            "load_seconds":round(ready-downloaded,2),
            "total_seconds":round(time.monotonic()-t,2),
            "peak_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "visual_review":"not_performed","production_approved":False}),flush=True)

if __name__=="__main__":
    benchmark()
