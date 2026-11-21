"""Scheduled seven-day private refill never re-renders a valid archived slot."""
import datetime as dt
import hashlib
import io
import json
import unittest
from unittest.mock import Mock,patch
import zipfile
from scripts.umbral3_refill_gate import check,BACKEND,PIN,batch_target

class RefillTests(unittest.TestCase):
    def test_private_batch_index_maps_all_fourteen_exact_slots(self):
        anchor=dt.date(2026,11,21)
        for i in range(14):
            today,slot=batch_target(anchor,i)
            self.assertEqual(today+dt.timedelta(days=7),
                             anchor+dt.timedelta(days=i//2))
            self.assertEqual(slot,"09" if i%2==0 else "21")
        for invalid in (-1,14,True,"3",None):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                batch_target(anchor,invalid)
        with self.assertRaises(ValueError):
            batch_target(dt.datetime(2026,11,21),0)

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
        with patch("scripts.umbral3_refill_gate.find",return_value=None):
            missing=check(store,dt.date(2026,11,14),"09")
        obsolete={"story_sha256":missing["story_sha256"],"model_revision":"old"}
        with patch("scripts.umbral3_refill_gate.find",return_value=obsolete):
            with self.assertRaisesRegex(RuntimeError,"stale visual model"):
                check(store,dt.date(2026,11,14),"09")
        store.get.assert_not_called()

    def test_missing_nextweek_story_fails_not_falls_back(self):
        with self.assertRaisesRegex(ValueError,"missing authored story"):
            check(Mock(),dt.date(2034,2,5),"09")

    def test_capacity_preflight_rejects_low_space_before_expensive_generation(self):
        from scripts.umbral3_refill_gate import assert_generation_budget
        from scripts.umbral3_evidence import HEADROOM
        from scripts.umbral3_storage import LIMIT

        class PrivateQuota:
            def __init__(self, free):
                self.free = free
            def quota(self):
                return {"used": 5_000_000_000-self.free,
                        "allocated": 5_000_000_000, "free": self.free}

        threshold = LIMIT + HEADROOM + 20_000_000
        with self.assertRaisesRegex(RuntimeError, "below safe generation budget"):
            assert_generation_budget(PrivateQuota(threshold-1))
        result = assert_generation_budget(PrivateQuota(threshold))
        self.assertTrue(result["capacity_verified"])
        self.assertEqual(result["minimum_required_bytes"], threshold)

