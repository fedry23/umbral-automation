"""Persist and read back actual private fixture media via isolated HF OIDC.

This module runs in a dedicated Python environment with huggingface_hub >= 1.
It MUST NOT import the media generation model stack, which pins older hub APIs.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.umbral3_hf_storage import HfBucketStore
from scripts.umbral3_evidence import persist_fixture

def persist(output, filename, summary_path):
    folder = Path(output).resolve(strict=True)
    video = (folder / filename).resolve(strict=True)
    if video.parent != folder or video.suffix.lower() != ".mp4" or not video.is_file():
        raise ValueError("Invalid private fixture video")
    report = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    if report.get("fixture") not in (1, 2, 3) or report.get("media_decoded") is not True:
        raise ValueError("Unverified private fixture")
    if report.get("visual_review") != "not_performed":
        raise ValueError("Unexpected artistic approval status")
    store = HfBucketStore.from_oidc()
    receipt = persist_fixture(store, folder, video, report)
    if not (len(receipt["key"]) == 68 and receipt["key"].endswith(".zip") and
            receipt["bytes"] > 100_000 and len(receipt["sha256"]) == 64):
        raise ValueError("Invalid private fixture receipt")
    result = {"fixture": report["fixture"], "sha256": receipt["sha256"],
              "key": receipt["key"], "bytes": receipt["bytes"],
              "private": True, "readback_verified": True,
              "visual_review": "not_performed", "ready_to_publish": False}
    print("UMBRAL3_PRIVATE_MEDIA_STORED=" + json.dumps(result, sort_keys=True), flush=True)
    return result

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--summary", type=Path, required=True)
    args = ap.parse_args()
    persist(args.output, args.video, args.summary)
