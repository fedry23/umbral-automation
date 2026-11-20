"""Private *synthetic* full-media archive round-trip. Not a playable Reel.

Validates immutable ZIP v2, all obligatory components, hashes, and persistence
over authenticated HF OIDC. It never accesses Meta or generates models.
"""
import hashlib
import json
from pathlib import Path
import tempfile

from scripts.umbral3_evidence import persist_fixture, verify_media_bundle
from scripts.umbral3_hf_storage import HfBucketStore

FILES = [
    "cover.jpg", "scene_contact_sheet.jpg", "subtitles.ass",
    "shot_timeline.json", "image_quality_report.json", "timings.json",
    "voice.wav", "music.wav", "intro_card.png", "outro_card.png",
    "branding_timing.json", "caption.txt", "story_used.json",
    *(f"scene_{i:02}.png" for i in range(6)),
]
REPORT = {"fixture": 1, "media_decoded": False, "visual_review": "not_performed",
          "synthetic_transport_test": True, "ready_to_publish": False}

def run():
    store = HfBucketStore.from_oidc()
    with tempfile.TemporaryDirectory(prefix="umbral3-full-archive-protocol-") as root:
        directory = Path(root)
        video = directory / "private-fixture-1.mp4"
        video.write_bytes(b"synthetic storage-only mp4 payload: NOT A VIDEO")
        for name in FILES:
            (directory/name).write_bytes(("synthetic-storage-protocol:" + name).encode())
        receipt = persist_fixture(store, directory, video, REPORT)
        archive = store.get(receipt["key"])
        if archive is None or hashlib.sha256(archive).hexdigest() != receipt["sha256"]:
            raise RuntimeError("Private synthetic full archive missing or corrupt")
        verified = verify_media_bundle(archive)
        if verified["assets"] != len(FILES) + 2 or verified["manifest_version"] != 2:
            raise RuntimeError("Private full-media manifest invalid")
        # Strictly return evidence metadata; never echo signed URLs or file content.
        return {"bucket_private": True, "synthetic": True, "decoded_media": False,
                "key": receipt["key"], "sha256": receipt["sha256"],
                "bytes": len(archive), "assets": verified["assets"],
                "protocol": "immutable-full-media-v2", "readback_verified": True,
                "visual_approved": False, "ready_to_publish": False}

if __name__ == "__main__":
    print("UMBRAL3_FULL_ARCHIVE_STORAGE=" + json.dumps(run(), sort_keys=True), flush=True)
