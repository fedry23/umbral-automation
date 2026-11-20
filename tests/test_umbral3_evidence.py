import hashlib
import io
import json
import unittest
from unittest.mock import Mock, patch
from scripts.umbral3_evidence import quota, persist, probe, HEADROOM

class PrivateEvidenceTests(unittest.TestCase):
    def store(self):
        store = Mock()
        store.token = "test-only"
        response = io.BytesIO(json.dumps({"used": 100, "allocation": {".tag": "individual", "allocated": 200_000_000}}).encode())
        store.opener.open.return_value.__enter__.return_value = response
        return store

    def test_quota(self):
        self.assertEqual(quota(self.store())["free"], 199_999_900)

    def test_unsupported_quota_fails(self):
        store = self.store()
        store.opener.open.return_value.__enter__.return_value = io.BytesIO(b'{"used": 3, "allocation": {".tag": "team", "allocated": 10}}')
        with self.assertRaisesRegex(RuntimeError, "quota"):
            quota(store)

    def test_reconciles_lost_response(self):
        store = Mock()
        data = b"fixture"
        store.get.side_effect = [None, data]
        store.put_new.side_effect = RuntimeError("lost response")
        with patch("scripts.umbral3_evidence.quota", return_value={"free": HEADROOM+100}):
            receipt = persist(store, data)
        self.assertEqual(receipt["sha256"], hashlib.sha256(data).hexdigest())

    def test_no_write_low_quota(self):
        store = Mock()
        store.get.return_value = None
        with patch("scripts.umbral3_evidence.quota", return_value={"free": HEADROOM}):
            with self.assertRaisesRegex(RuntimeError, "headroom"):
                persist(store, b"fixture")
        store.put_new.assert_not_called()

    def test_corrupt_readback_never_accepted(self):
        store = Mock()
        store.get.return_value = b"wrong"
        with self.assertRaisesRegex(RuntimeError, "readback"):
            persist(store, b"fixture")
        store.put_new.assert_not_called()

    def test_probe_is_idempotent(self):
        store = Mock()
        objects = {}
        store.get.side_effect = objects.get
        store.put_new.side_effect = lambda k, d: objects.setdefault(k, d)
        with patch("scripts.umbral3_evidence.quota", return_value={"free": HEADROOM+10000}):
            self.assertEqual(probe(store), probe(store))
        self.assertEqual(store.put_new.call_count, 1)
