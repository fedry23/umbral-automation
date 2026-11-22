"""Machine visual QA must never impersonate the human or approve corrupt media."""
import datetime as dt
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from scripts.umbral3_machine_qa import assess_logits, check_certificate, story_for, oldest_uncertified, POLICY, BACKEND, RECOVERY_BACKEND, REVISION, MODEL, PIN

ROOT=Path(__file__).resolve().parents[1]

def sample_logits():
    matrix=[]
    for i in range(6):
        row=[1.]*9
        row[i]=5.
        row[6]=4.
        row[7]=0.
        row[8]=0.
        matrix.append(row)
    return matrix

class AutomaticQATests(unittest.TestCase):
    def test_complete_six_shot_semantic_evidence_passes(self):
        result=assess_logits(sample_logits())
        self.assertTrue(result["passed"])
        self.assertEqual(result["matching_scenes"],6)
        self.assertEqual(result["horror_scenes"],6)

    def test_happy_non_horror_images_fail_closed(self):
        row=sample_logits()
        for x in row:
            x[7]=6.
        result=assess_logits(row)
        self.assertFalse(result["passed"])
        self.assertEqual(result["horror_scenes"],0)

    def test_scene_mismatch_fails_even_if_dark(self):
        row=sample_logits()
        for i in range(4):
            row[i][i]=-9.
        self.assertFalse(assess_logits(row)["passed"])

    def test_corrupt_nan_and_missing_frames_raise(self):
        for row in ([],sample_logits()[:5],[[1]*9]*7,
                    [([float("nan")]*9)]+sample_logits()[1:]):
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    assess_logits(row)

    def test_real_editorial_future_date_has_unique_authored_story(self):
        s=story_for(ROOT,"2026-11-28","09")
        self.assertEqual(s["title"],"La cinta amarilla")
        self.assertEqual(len(s["scenes"]),6)
        with self.assertRaises(RuntimeError):
            story_for(ROOT,"2050-01-01","21")

    def test_backlog_qa_selects_oldest_missing_certificate_before_new_tail(self):
        today=dt.date(2026,11,21)
        seen=[]
        def load(*args):
            day=args[1]
            seen.append(day)
            return {"bundle_sha256":"a"*64,"backend":BACKEND}
        def cert(_store,remote):
            return b"certificate" if "2026-11-22" in remote or "2026-11-23" in remote else None
        with patch("scripts.umbral3_machine_qa._pointer",side_effect=load),\\
             patch("scripts.umbral3_machine_qa._get",side_effect=cert),\\
             patch("scripts.umbral3_machine_qa.check_certificate",return_value={"machine_approved":True}):
            result=oldest_uncertified(Mock(),today,"09")
        self.assertEqual(result["date"],"2026-11-24")
        self.assertTrue(result["needs_qa"])
        self.assertEqual(seen,["2026-11-22","2026-11-23","2026-11-24"])
        self.assertFalse(result["ready_to_publish"])

    def test_backlog_does_not_override_invalid_existing_certificate(self):
        with patch("scripts.umbral3_machine_qa._pointer",return_value={"bundle_sha256":"a"*64}),\\
             patch("scripts.umbral3_machine_qa._get",return_value=b"tampered"),\\
             patch("scripts.umbral3_machine_qa.check_certificate",side_effect=RuntimeError("tampered")):
            with self.assertRaisesRegex(RuntimeError,"tampered"):
                oldest_uncertified(Mock(),dt.date(2026,11,21),"21")

    def test_backlog_ignores_unstored_images_but_not_stale_candidates(self):
        today=dt.date(2026,11,21)
        with patch("scripts.umbral3_machine_qa._pointer",side_effect=RuntimeError("Unindexed or stale private candidate")),\\
             patch("scripts.umbral3_machine_qa.story_for",return_value={}),\\
             patch("scripts.umbral3_machine_qa.find",return_value=None):
            result=oldest_uncertified(Mock(),today,"09")
            self.assertFalse(result["needs_qa"])
            self.assertEqual(result["missing_or_unready"],7)
        with patch("scripts.umbral3_machine_qa._pointer",side_effect=RuntimeError("Unindexed or stale private candidate")),\\
             patch("scripts.umbral3_machine_qa.story_for",return_value={}),\\
             patch("scripts.umbral3_machine_qa.find",return_value={"malicious":True}):
            with self.assertRaisesRegex(RuntimeError,"Unindexed or stale"):
                oldest_uncertified(Mock(),today,"09")

    def test_backlog_rejects_unbounded_future_or_incorrect_type(self):
        for invalid in ("2026-11-21",dt.datetime(2026,11,21),True,None):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                oldest_uncertified(Mock(),invalid,"09")

    def test_recovery_backend_can_be_certified_but_old_candidate_unchanged(self):
        from scripts.umbral3_machine_qa import _pointer, SUPPORTED_BACKENDS
        self.assertIn(RECOVERY_BACKEND,SUPPORTED_BACKENDS)
        story=story_for(ROOT,"2026-11-28","09")
        from scripts.umbral3_reserve import story_key
        sha=story_key(story)
        preferred={"story_sha256":sha,"bundle_sha256":"b"*64,
                   "model_revision":PIN,"backend":RECOVERY_BACKEND}
        old={"story_sha256":sha,"bundle_sha256":"a"*64,
             "model_revision":PIN,"backend":BACKEND}
        def find(store,day,slot,backend):
            return preferred if backend==RECOVERY_BACKEND else old
        with patch("scripts.umbral3_machine_qa.find",side_effect=find):
            selected=_pointer(Mock(),"2026-11-28","09",ROOT)
            self.assertEqual(selected[1]["backend"],RECOVERY_BACKEND)
            self.assertEqual(selected[1]["bundle_sha256"],"b"*64)
        with patch("scripts.umbral3_machine_qa.find",side_effect=lambda s,d,t,b:old if b==BACKEND else None):
            self.assertEqual(_pointer(Mock(),"2026-11-28","09",ROOT)[1]["backend"],BACKEND)

    def test_tampered_preferred_candidate_does_not_fall_back_to_original(self):
        from scripts.umbral3_machine_qa import _pointer
        def find(store,day,slot,backend):
            return {"story_sha256":"d"*64,"bundle_sha256":"b"*64,
                    "model_revision":PIN,"backend":RECOVERY_BACKEND} if backend==RECOVERY_BACKEND else None
        with patch("scripts.umbral3_machine_qa.find",side_effect=find):
            with self.assertRaisesRegex(RuntimeError,"Stale indexed"):
                _pointer(Mock(),"2026-11-28","09",ROOT)

    def test_missing_certificate_never_grants_automatic_approval(self):
        store=Mock()
        story=story_for(ROOT,"2026-11-28","09")
        from scripts.umbral3_reserve import story_key
        p={"story_sha256":story_key(story),"bundle_sha256":"a"*64,
           "model_revision":PIN,"backend":BACKEND}
        with patch("scripts.umbral3_machine_qa.find",return_value=p),\
             patch("scripts.umbral3_machine_qa._get",return_value=None):
            with self.assertRaisesRegex(RuntimeError,"No machine QA certificate"):
                check_certificate(store,"2026-11-28","09",ROOT)

    def test_human_approval_is_never_assumed_from_machine_certificate(self):
        store=Mock()
        story=story_for(ROOT,"2026-11-28","09")
        from scripts.umbral3_reserve import story_key
        sha=story_key(story)
        pointer={"story_sha256":sha,"bundle_sha256":"a"*64,"model_revision":PIN,
                 "backend":BACKEND}
        row={"version":1,"kind":"umbral3-automatic-machine-qa",
             "policy":POLICY,"date":"2026-11-28","slot":"09",
             "story_sha256":sha,"backend":BACKEND,"model_revision":PIN,
             "clip_model":MODEL,"clip_revision":REVISION,
             "scene_sha256":{f"scene_{i:02}.png":"b"*64 for i in range(6)},
             "image_scores":[50]*6,
             "semantic":{"passed":True,"matching_scenes":6,"horror_scenes":6},
             "human_review":False,"machine_approved":True,
             "ready_to_publish":False,"bundle_sha256":"a"*64}
        with patch("scripts.umbral3_machine_qa.find",return_value=pointer),\
             patch("scripts.umbral3_machine_qa._get",side_effect=lambda *_: json.dumps(row).encode()):
            self.assertFalse(check_certificate(store,"2026-11-28","09",ROOT)["human_review"])
            row["human_review"]=True
            with self.assertRaisesRegex(RuntimeError,"tampered"):
                check_certificate(store,"2026-11-28","09",ROOT)

if __name__=="__main__":
    unittest.main()
