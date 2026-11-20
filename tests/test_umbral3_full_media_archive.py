"""Private complete audiovisual archive integrity checks without media generation."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts.umbral3_evidence import (
    HEADROOM, persist_fixture, verify_media_bundle,
)

MEMBERS = [
    "cover.jpg", "scene_contact_sheet.jpg", "subtitles.ass",
    "shot_timeline.json", "image_quality_report.json", "timings.json",
    "voice.wav", "music.wav", "intro_card.png", "outro_card.png",
    "branding_timing.json", "caption.txt", "story_used.json",
    *(f"scene_{i:02}.png" for i in range(6)),
]

class FakeStore:
    def __init__(self):
        self.blobs = {}
    def get(self, name):
        return self.blobs.get(name)
    def put_new(self, name, data):
        if name in self.blobs:
            return False
        self.blobs[name] = data
        return True

class PrivateMediaArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / "private-fixture-1.mp4"
        self.video.write_bytes(b"dummy-media-for-storage-check-only")
        for name in MEMBERS:
            (self.root/name).write_bytes(("test-fixture:" + name).encode())
        self.summary = {"fixture": 1, "media_decoded": True,
                        "visual_review": "not_performed"}
        self.store = FakeStore()
    def archive(self):
        with patch("scripts.umbral3_evidence.quota",
                   return_value={"free": HEADROOM+100_000_000}):
            receipt = persist_fixture(self.store, self.root, self.video, self.summary)
        return receipt, self.store.get(receipt["key"])
    def test_full_package_manifest_includes_audio_branding_and_video(self):
        receipt, bundle = self.archive()
        self.assertEqual(receipt["sha256"], hashlib.sha256(bundle).hexdigest())
        result = verify_media_bundle(bundle)
        self.assertEqual(result["assets"], len(MEMBERS)+2)
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(set(manifest["assets"]), set(MEMBERS)|{"summary.json",self.video.name})
            self.assertFalse(manifest["publishable"])
            self.assertFalse(manifest["visual_approved"])
        receipt2, bundle2 = self.archive()
        self.assertEqual(receipt2,receipt)
        self.assertEqual(bundle2,bundle)
    def test_tampered_member_is_rejected(self):
        _, raw = self.archive()
        dest=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as source:
            with zipfile.ZipFile(dest,"w") as output:
                for name in source.namelist():
                    content=source.read(name)
                    output.writestr(name, b"tampered" if name=="voice.wav" else content)
        with self.assertRaisesRegex(ValueError,"(hash|size) mismatch"):
            verify_media_bundle(dest.getvalue())
    def test_missing_audio_fails_closed(self):
        (self.root/"music.wav").unlink()
        with self.assertRaisesRegex(ValueError,"Missing or unsafe"):
            persist_fixture(self.store,self.root,self.video,self.summary)
        self.assertEqual(self.store.blobs,{})
    def test_rejects_compressed_members_before_readback(self):
        _, raw = self.archive()
        edited = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as original:
            with zipfile.ZipFile(edited, "w", compression=zipfile.ZIP_DEFLATED) as replacement:
                for name in original.namelist():
                    replacement.writestr(name, original.read(name))
        with self.assertRaisesRegex(ValueError, "safe bounds"):
            verify_media_bundle(edited.getvalue())

    def test_rejects_zip_traversal(self):
        with io.BytesIO() as buffer:
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("manifest.json", "{}")
                archive.writestr("../escape", "blocked")
            with self.assertRaisesRegex(ValueError, "Unsafe ZIP members"):
                verify_media_bundle(buffer.getvalue())
