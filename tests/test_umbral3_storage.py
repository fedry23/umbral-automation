import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import zipfile
from PIL import Image
from scripts.umbral3_storage import LocalStore, DropboxStore, get_or_prepare, object_key, restore

ROOT = Path(__file__).resolve().parents[1]

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.store=LocalStore(self.root/'private')
        self.story=json.loads((ROOT/'tests/fixtures/umbral3_stories.json').read_text())[0]
        self.recipe={'model':'test','revision':'fixture','steps':4}
        self.args=(self.story,'2027-03-28','09',self.recipe)
        self.calls=0
    def generate(self, story, folder):
        self.calls+=1
        for i in range(6):
            Image.new('RGB',(256,384),(i*20,30,40)).save(folder/f'scene_{i:02}.png')
    def test_reuse_across_restart_and_number_change(self):
        paths,status=get_or_prepare(self.store,*self.args,self.root/'first',self.generate)
        self.assertEqual(status,'prepared')
        changed={**self.story,'episode_number':14}
        paths2,status=get_or_prepare(LocalStore(self.root/'private'),changed,*self.args[1:],self.root/'second',self.generate)
        self.assertEqual(status,'reused')
        self.assertEqual(self.calls,1)
        self.assertEqual([p.read_bytes() for p in paths],[p.read_bytes() for p in paths2])
    def test_corruption_not_regenerated_or_silently_replaced(self):
        key=object_key(*self.args)
        self.store.put_new(key,b'invalid')
        with self.assertRaises(zipfile.BadZipFile):
            get_or_prepare(self.store,*self.args,self.root/'bad',self.generate)
        self.assertEqual(self.calls,0)
        self.assertFalse(self.store.put_new(key,b'replacement'))
    def test_lost_write_response_reconciled(self):
        parent=self.store
        class LostResponse:
            def get(self,k): return parent.get(k)
            def put_new(self,k,d):
                parent.put_new(k,d)
                raise RuntimeError('lost response')
        _,status=get_or_prepare(LostResponse(),*self.args,self.root/'recover',self.generate)
        self.assertEqual(status,'reconciled')
        self.assertEqual(self.calls,1)
    def test_no_receipt_no_success(self):
        store=Mock()
        store.get.return_value=None
        store.put_new.side_effect=RuntimeError('network')
        with self.assertRaisesRegex(RuntimeError,'not confirmed'):
            get_or_prepare(store,*self.args,self.root/'unconfirmed',self.generate)
        self.assertFalse((self.root/'unconfirmed').exists())
    def test_zip_traversal_rejected(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('../outside','bad')
        with self.assertRaises(ValueError):
            restore(buf.getvalue(),*self.args,self.root/'out')
        self.assertFalse((self.root/'outside').exists())
    def test_missing_oauth(self):
        with self.assertRaisesRegex(RuntimeError,'not configured'):
            DropboxStore('','','')
