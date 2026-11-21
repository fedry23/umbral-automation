"""Private slot pointer transport tests; no network or credentials."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest

from scripts.umbral3_hf_candidate_index import remote_name,register,find

class FakeApi:
    def __init__(self):
        self.objects={}
        self.fail_after_write=False
    def list_bucket_tree(self,bucket,recursive,token):
        return [SimpleNamespace(path=k,size=len(v)) for k,v in self.objects.items()]
    def download_bucket_files(self,bucket,files,token):
        for key,dest in files:
            Path(dest).write_bytes(self.objects[key])
    def batch_bucket_files(self,bucket,add,token):
        for contents,path in add:
            self.objects[path]=contents if isinstance(contents,bytes) else Path(contents).read_bytes()
        if self.fail_after_write:
            raise RuntimeError("Lost response")

class Store:
    def __init__(self):
        self.api=FakeApi()
        self.bucket="Fedry23/umbral-private"
        self.token="hf_testing"
    def _ensure_auth(self): return None

class IndexTests(unittest.TestCase):
    def setUp(self):
        self.store=Store()
        self.body=b"validated private video package"
        self.hash=hashlib.sha256(self.body).hexdigest()
        self.receipt={"key":self.hash+".zip","sha256":self.hash,"bytes":len(self.body)}
        self.storyhash=hashlib.sha256(b"editorial story").hexdigest()
        self.summary={"date":"2026-11-21","slot":"09","visual_backend":"sdxl-lightning-2steps-ov-int8",
                      "model_revision":"347b21e571d7b8a716af83f64d68c5c028c51c56",
                      "story_sha256":self.storyhash,"candidate":True,
                      "media_decoded":True,"ready_to_publish":False,
                      "visual_review":"not_performed"}
    def test_register_and_find_across_fresh_store(self):
        self.assertIsNone(find(self.store,"2026-11-21","09",self.summary["visual_backend"]))
        record=register(self.store,self.summary,self.receipt)
        self.assertEqual(record,find(self.store,"2026-11-21","09",self.summary["visual_backend"]))
        self.assertEqual(len(self.store.api.objects),1)
        self.assertEqual(register(self.store,self.summary,self.receipt),record)
        self.assertEqual(len(self.store.api.objects),1)
        self.assertIs(record["ready_to_publish"],False)
    def test_uncertain_write_reconciles_exact_pointer(self):
        self.store.api.fail_after_write=True
        record=register(self.store,self.summary,self.receipt)
        self.assertEqual(find(self.store,"2026-11-21","09",self.summary["visual_backend"]),record)
    def test_other_reel_must_not_replace_same_slot_and_backend(self):
        register(self.store,self.summary,self.receipt)
        alt=hashlib.sha256(b"different").hexdigest()
        with self.assertRaisesRegex(RuntimeError,"Different candidate"):
            register(self.store,self.summary,{"key":alt+".zip","sha256":alt,"bytes":12})
        self.assertEqual(find(self.store,"2026-11-21","09",self.summary["visual_backend"])["bundle_sha256"],self.hash)
    def test_reject_publishable_spoofing(self):
        x={**self.summary,"ready_to_publish":True}
        with self.assertRaises(ValueError):
            register(self.store,x,self.receipt)
        self.assertEqual(self.store.api.objects,{})
    def test_reject_unsafe_slot_backend_and_date(self):
        for day,slot,backend in [
            ("2026-11-21","../09","sdxl-lightning-2steps-ov-int8"),
            ("2026-11-21","09","../../foo"),
            ("2026-99-99","09","sdxl-lightning-2steps-ov-int8")]:
            with self.subTest(day=day,slot=slot,backend=backend),self.assertRaises(ValueError):
                remote_name(day,slot,backend)
