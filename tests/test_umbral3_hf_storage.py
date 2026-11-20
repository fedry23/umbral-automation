"""Storage adapter regression tests: no model, network, or credentials."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest

from scripts.umbral3_hf_storage import HfBucketStore, BUCKET, PREFIX, CAP

KEY = hashlib.sha256(b"umbral3 immutable ZIP").hexdigest() + ".zip"

class BucketApi:
    def __init__(self):
        self.objects = {}
        self.fail_after_write = False
        self.corrupt_download = False
    def bucket_info(self, bucket, token):
        return SimpleNamespace(id=BUCKET, private=True, size=sum(map(len,self.objects.values())))
    def list_bucket_tree(self, bucket, recursive, token):
        return [SimpleNamespace(path=k,size=len(v)) for k,v in self.objects.items()]
    def batch_bucket_files(self, bucket, add, token):
        for path, key in add:
            self.objects[key] = Path(path).read_bytes()
        if self.fail_after_write:
            raise RuntimeError("lost transport response")
    def download_bucket_files(self, bucket, files, token):
        for key, dest in files:
            Path(dest).write_bytes(b"corrupt" if self.corrupt_download else self.objects[key])

class HfStoreRegressionTests(unittest.TestCase):
    def setUp(self):
        self.api=BucketApi()
        self.store=object.__new__(HfBucketStore)
        self.store.api=self.api
        self.store.bucket=BUCKET
        self.store.token="hf_test_nonsecret"
        self.store.verify_private=lambda: self.api.bucket_info(BUCKET, self.store.token)
    def test_roundtrip_reuse_no_second_write(self):
        value=b"PK\x03\x04important immutable private bytes"
        self.assertIsNone(self.store.get(KEY))
        self.assertTrue(self.store.put_new(KEY,value))
        self.assertEqual(self.store.get(KEY),value)
        self.assertFalse(self.store.put_new(KEY,b"different bytes"))
        self.assertEqual(self.store.get(KEY),value)
    def test_rejects_unsafe_names_and_empty_files(self):
        for key in ("../outside.zip","a/b.zip","wrong.zip",""):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.store.get(key)
        with self.assertRaises(ValueError):
            self.store.put_new(KEY,b"")
    def test_readback_detects_corruption(self):
        self.assertTrue(self.store.put_new(KEY,b"some bytes longer"))
        self.api.corrupt_download=True
        with self.assertRaisesRegex(RuntimeError,"size mismatch"):
            self.store.get(KEY)
    def test_uncertain_upload_must_reconcile_by_readback(self):
        self.api.fail_after_write=True
        with self.assertRaisesRegex(RuntimeError,"uncertain"):
            self.store.put_new(KEY,b"one write")
        self.assertEqual(self.store.get(KEY),b"one write")
        self.assertFalse(self.store.put_new(KEY,b"new content"))
    def test_cap_headroom_fails_closed(self):
        self.store.verify_private=lambda: SimpleNamespace(id=BUCKET, private=True,
                                                          size=CAP-100_000)
        with self.assertRaisesRegex(RuntimeError,"headroom"):
            self.store.put_new(KEY,b"new data")
        self.assertFalse(self.api.objects)
    def test_quota_values_from_conservative_cap(self):
        self.assertEqual(self.store.quota(),
                         {"used":0,"allocated":CAP,"free":CAP})
