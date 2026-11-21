"""Real OIDC round-trip of a validated immutable storyboard ZIP (no publication).

An actual six-scene image package is written to the same private reserve
backend used by the production queue, downloaded, manifest checked, and reused.
Synthetic images test storage transport only, not visual readiness.
"""
import hashlib
import json
from pathlib import Path
import tempfile

from PIL import Image, ImageDraw

from scripts.umbral3_storage import get_or_prepare, object_key
from scripts.umbral3_hf_storage import HfBucketStore

ROOT = Path(__file__).resolve().parents[1]
DAY, SLOT = "2027-01-21", "09"
RECIPE = {"model": "private-storage-transport-check", "revision": "1", "steps": 0}

def exercise(store, story):
    call_count = 0
    def generate(item, folder):
        nonlocal call_count
        call_count += 1
        for i in range(len(item["scenes"])):
            img = Image.new("RGB", (256, 384), (20 + 31*i, 40 + 17*i, 65 + 13*i))
            ImageDraw.Draw(img).rectangle([i+12, i+30, 74+i, 121+i], fill=(233, 90+i, 35+i))
            img.save(folder / f"scene_{i:02}.png", optimize=True)
    with tempfile.TemporaryDirectory(prefix="umbral3-hf-zip-smoke-") as tmp:
        root = Path(tmp)
        first, status = get_or_prepare(store, story, DAY, SLOT, RECIPE, root/"first", generate)
        if status not in ("prepared", "reused", "reconciled"):
            raise RuntimeError("Unexpected reserve state")
        second, again = get_or_prepare(store, {**story, "episode_number": 12345},
                                      DAY, SLOT, RECIPE, root/"second", generate)
        if again != "reused" or len(first) != 6 or len(second) != 6 or call_count > 1:
            raise RuntimeError("Immutable reserve reuse failed")
        for a, b in zip(first, second):
            if hashlib.sha256(a.read_bytes()).digest() != hashlib.sha256(b.read_bytes()).digest():
                raise RuntimeError("Private readback corrupted scene")
        raw = store.get(object_key(story, DAY, SLOT, RECIPE))
        if raw is None:
            raise RuntimeError("Remote reserve object missing")
        return {"storage": "hf_bucket", "private": True, "date": DAY, "slot": SLOT,
                "bundle_sha256": hashlib.sha256(raw).hexdigest(), "bundle_bytes": len(raw),
                "scenes_verified": len(first), "first": status, "second": again,
                "number_independent": True, "artistic_quality": "not_assessed",
                "ready_to_publish": False}

def main():
    story = json.loads((ROOT/"tests/fixtures/umbral3_stories.json").read_text(encoding="utf-8"))[0]
    print("UMBRAL3_RESERVE_ROUNDTRIP="+json.dumps(exercise(HfBucketStore.from_oidc(), story)), flush=True)

if __name__ == "__main__":
    main()
