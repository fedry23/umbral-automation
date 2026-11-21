"""Isolated CPU feasibility benchmark, not a visual-quality approval.

No publication credentials, remote model code, network inference or media upload.
Model snapshots are pinned. Images are held in memory and never published.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import shutil
import tempfile
import time

MODELS = {
    "sdxl": ("OpenVINO/stable-diffusion-xl-base-1.0-int8-ov",
             "f90474e5021709d62af1a7e18d06b149e70ed1c0", 20, 5.0),
    "flux": ("OpenVINO/FLUX.1-schnell-int8-ov",
             "b722e705a0e7cef61e0f169cc1d8b7f86afac403", 4, 0.0),
}
WIDTH, HEIGHT = 512, 896
PROMPTS = (
    "Close view of a hand-shaped bulge emerging from wet white plaster, empty room with bare wooden floor, painter in grey overalls, cold window light, realistic cinematic horror",
    "Painter in grey overalls scraping five grooves in white plaster with a steel scraper, empty room with bare wooden floor, cold window light, realistic cinematic horror",
)

def benchmark(backend):
    import openvino_genai as ov
    from huggingface_hub import model_info, snapshot_download
    from PIL import Image, ImageStat
    model, revision, steps, guide = MODELS[backend]
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="umbral3-ov-") as tmp:
        metadata = model_info(model, revision=revision, files_metadata=True, timeout=30)
        if metadata.sha != revision:
            raise RuntimeError("Model revision mismatch")
        sizes = [item.size for item in metadata.siblings]
        if not sizes or any(size is None for size in sizes):
            raise RuntimeError("Cannot verify model download size")
        total_bytes = sum(sizes)
        free = shutil.disk_usage(tmp).free
        print(json.dumps({"model": model, "revision": revision, "download_bytes": total_bytes,
                          "free_disk_bytes": free}), flush=True)
        if total_bytes + 2_000_000_000 > free:
            raise RuntimeError("Insufficient disk for pinned model and runtime headroom")
        directory = snapshot_download(model, revision=revision, local_dir=Path(tmp)/"model",
                                      max_workers=2)
        downloaded = time.monotonic()
        pipe = ov.Text2ImagePipeline(str(directory), "CPU")
        loaded = time.monotonic()
        shots = []
        for i, prompt in enumerate(PROMPTS):
            start = time.monotonic()
            tensor = pipe.generate(prompt, num_inference_steps=steps, guidance_scale=guide,
                                   width=WIDTH, height=HEIGHT, rng_seed=881+i)
            image = Image.fromarray(tensor.data[0]).convert("RGB")
            if image.size != (WIDTH, HEIGHT):
                raise ValueError("Unexpected generated dimensions")
            if max(ImageStat.Stat(image).stddev) < 2:
                raise ValueError("Flat or corrupt generated image")
            shots.append({"shot": i+1, "seconds": round(time.monotonic()-start, 2),
                          "sha256_pixels": hashlib.sha256(image.tobytes()).hexdigest()})
            del tensor, image
        if len({s["sha256_pixels"] for s in shots}) != len(shots):
            raise RuntimeError("Identical generated shots")
        report = {"backend": backend, "model": model, "revision": revision,
                  "dimensions": [WIDTH, HEIGHT], "steps": steps,
                  "download_seconds": round(downloaded-started, 2),
                  "load_seconds": round(loaded-downloaded, 2), "shots": shots,
                  "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "elapsed_seconds": round(time.monotonic()-started, 2),
                  "visual_review": "not_performed", "production_approved": False}
        print("UMBRAL3_OV_BENCHMARK=" + json.dumps(report), flush=True)
        return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True, choices=MODELS)
    benchmark(parser.parse_args().backend)
