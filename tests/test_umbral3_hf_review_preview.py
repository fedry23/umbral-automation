"""Private review objects must be stored unlisted and independently verified."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from scripts.umbral3_hf_review_preview import upload_review

class Api:
    def __init__(self):
        self.objects={}
    def list_bucket_tree(self,bucket,recursive,token):
        return [SimpleNamespace(path=key,size=len(data)) for key,data in self.objects.items()]
    def batch_bucket_files(self,bucket,add,token):
        for path,remote in add:
            self.objects[remote]=Path(path).read_bytes()
    def download_bucket_files(self,bucket,files,token):
        for name,dest in files:
            Path(dest).write_bytes(self.objects[name])
class Store:
    def __init__(self):
        self.api=Api()
        self.bucket="Fedry23/umbral-private"
        self.token="hf_test"
    def _ensure_auth(self):return None
    def quota(self):return {"free":5000000000}

class PreviewTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.store=Store()
        self.video=self.root/"candidate-2026-11-21-09.mp4"
        self.video.write_bytes(b"video-bytes")
        (self.root/"cover.jpg").write_bytes(b"cover")
        (self.root/"scene_contact_sheet.jpg").write_bytes(b"contact")
        self.summary={"date":"2026-11-21","slot":"09",
                      "visual_backend":"sdxl-lightning-2steps-ov-int8",
                      "candidate":True,"media_decoded":True,
                      "ready_to_publish":False,"visual_review":"not_performed"}
    def test_private_three_file_sha256_readback(self):
        result=upload_review(self.store,self.root,self.video,self.summary)
        self.assertEqual(result["files"],3)
        self.assertTrue(result["private"])
        self.assertFalse(result["ready_to_publish"])
        self.assertEqual(len(self.store.api.objects),3)
        self.assertEqual(result,upload_review(self.store,self.root,self.video,self.summary))
        self.assertTrue(all(k.startswith("umbral3/private-review/")
                            for k in self.store.api.objects))
    def test_corrupt_existing_file_rejected(self):
        upload_review(self.store,self.root,self.video,self.summary)
        key=next(k for k in self.store.api.objects if k.endswith("video.mp4"))
        self.store.api.objects[key]=b"corrupted !!"
        with self.assertRaises(RuntimeError):
            upload_review(self.store,self.root,self.video,self.summary)
    def test_refuse_publishable_media(self):
        self.summary["ready_to_publish"]=True
        with self.assertRaises(ValueError):
            upload_review(self.store,self.root,self.video,self.summary)
        self.assertFalse(self.store.api.objects)
