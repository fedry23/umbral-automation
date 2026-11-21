"""Scheduled seven-day private refill never re-renders a valid archived slot."""
import datetime as dt
import hashlib
import io
import json
import unittest
from unittest.mock import Mock,patch
import zipfile
from scripts.umbral3_refill_gate import check,BACKEND,PIN

class RefillTests(unittest.TestCase):
    def test_missing_21nov_slot_asks_for_one_reel(self):
        store=Mock()
        with patch("scripts.umbral3_refill_gate.find",return_value=None):
            morning=check(store,dt.date(2026,11,14),"09")
            evening=check(store,dt.date(2026,11,14),"21")
        self.assertEqual(morning["anchor"],"2026-11-21")
        self.assertEqual(morning["index"],0)
        self.assertEqual(evening["index"],1)
        self.assertTrue(morning["generate"])
        self.assertFalse(morning["ready_to_publish"])
        store.get.assert_not_called()
    def test_existing_verified_zip_skips_reproduction(self):
        store=Mock()
        with patch("scripts.umbral3_refill_gate.find",return_value=None):
            original=check(store,dt.date(2026,11,14),"09")
        summary={"candidate":True,"date":original["date"],"slot":"09",
                 "story_sha256":original["story_sha256"],
                 "visual_backend":BACKEND,
                 "visual_review":"not_performed","ready_to_publish":False}
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,"w") as z:
            z.writestr("summary.json",json.dumps(summary))
            z.writestr("candidate-2026-11-21-09.mp4",b"test")
        blob=stream.getvalue()
        digest=hashlib.sha256(blob).hexdigest()
        store.get.return_value=blob
        index={"story_sha256":original["story_sha256"],"model_revision":PIN,"bundle_sha256":digest,
               "bundle_bytes":len(blob)}
        with patch("scripts.umbral3_refill_gate.find",return_value=index),patch(
            "scripts.umbral3_refill_gate.verify_media_bundle",return_value={"assets":21}):
            checked=check(store,dt.date(2026,11,14),"09")
        self.assertFalse(checked["generate"])
        self.assertTrue(checked["stored_full_candidate"])
        self.assertFalse(checked["ready_to_publish"])
    def test_stale_story_never_overwritten(self):
        store=Mock()
        with patch("scripts.umbral3_refill_gate.find",return_value={"story_sha256":"0"*64}):
            with self.assertRaisesRegex(RuntimeError,"stale story"):
                check(store,dt.date(2026,11,14),"09")
        store.get.assert_not_called()
    def test_stale_model_never_reused(self):
        store=Mock()
        with patch("scripts.umbral3_refill_gate.find",return_value={"story_sha256":"x", "model_revision":"old"}):
            with self.assertRaisesRegex(RuntimeError,"stale story"):
                check(store,dt.date(2026,11,14),"09")
        with patch("scripts.umbral3_refill_gate.find",side_effect=lambda *args: {"story_sha256":__import__('scripts.umbral3_refill_gate',fromlist=['story_key']).story_key(__import__('scripts.umbral3_reserve_render',fromlist=['load_slot','catalogs']).load_slot(0,dt.date(2026,11,21),__import__('scripts.umbral3_reserve_render',fromlist=['catalogs']).catalogs())[0]), "model_revision":"old"}):
            with self.assertRaisesRegex(RuntimeError,"stale visual model"):
                check(store,dt.date(2026,11,14),"09")

    def test_missing_nextweek_story_fails_not_falls_back(self):
        with self.assertRaisesRegex(ValueError,"missing authored story"):
            check(Mock(),dt.date(2034,2,5),"09")
