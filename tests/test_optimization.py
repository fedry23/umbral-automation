"""Regressions for bounded file hashing and publication scheduling order."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import os
import urllib.error
import unittest
from unittest.mock import patch
from scripts import publish_daily as publisher
from scripts.wait_public_video import stream_digest, check_remote

class OptimizationsTests(unittest.TestCase):
    def test_stream_hash_uses_bounded_reads(self):
        class Bounded(io.BytesIO):
            def read(self, n=-1):
                self.assert_size(n)
                return super().read(n)
            def assert_size(self, n):
                if not 0 < n <= 1024*1024:
                    raise AssertionError('Unbounded video download')
        raw=b'known-MP4-bytes'*200000
        self.assertEqual(stream_digest(Bounded(raw)),hashlib.sha256(raw).digest())

    def test_intent_is_durable_before_wait_and_single_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            (out/'prepared.json').write_text(json.dumps({'date':'2026-11-17','status':'prepared','container':'abc'}))
            events=[]
            with patch.object(publisher,'OUT',out), patch.object(publisher,'intent_path',return_value=out/'absent.json'), patch.object(publisher,'already_published',return_value=None), patch.object(publisher,'one_time_late_allowed',return_value=False), patch.object(publisher,'persist_intent',side_effect=lambda *a:events.append('persist')), patch.object(publisher,'wait_until_target',side_effect=lambda *a:events.append('wait')), patch.object(publisher,'api',side_effect=lambda *a:(events.append('post') or {'id':'123'})) as api, patch.object(publisher,'record_verified',side_effect=lambda *a:events.append('verify')):
                publisher.publish('2026-11-17')
                self.assertEqual(events,['persist','wait','post','verify'])
                api.assert_called_once_with('POST',f'{publisher.ACCOUNT}/media_publish',{'creation_id':'abc'})

    def test_failed_durable_write_never_publishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            (out/'prepared.json').write_text(json.dumps({'date':'2026-11-17','status':'prepared','container':'abc'}))
            with patch.object(publisher,'OUT',out), patch.object(publisher,'intent_path',return_value=out/'absent.json'), patch.object(publisher,'already_published',return_value=None), patch.object(publisher,'persist_intent',side_effect=RuntimeError('git failed')), patch.object(publisher,'api') as api:
                with self.assertRaises(RuntimeError): publisher.publish('2026-11-17')
                api.assert_not_called()

    def test_get_retry_but_post_never_repeated_and_token_redacted(self):
        def transient():
            return urllib.error.HTTPError('https://graph.facebook.com/media',503,'Unavailable',{},io.BytesIO(b'{"error":{"message":"private-token"}}'))
        with patch.dict(os.environ,{'IG_ACCESS_TOKEN':'private-token'}), patch.object(publisher.time,'sleep'), patch.object(publisher.urllib.request,'urlopen',side_effect=[transient(),io.BytesIO(b'{"id":"123"}')]) as call:
            self.assertEqual(publisher.api('GET','media'),{'id':'123'})
            self.assertEqual(call.call_count,2)
            req=call.call_args.args[0]
            self.assertNotIn('private-token',req.full_url)
        with patch.dict(os.environ,{'IG_ACCESS_TOKEN':'private-token'}), patch.object(publisher.urllib.request,'urlopen',side_effect=transient()) as call:
            with self.assertRaises(RuntimeError) as error:
                publisher.api('POST','media_publish',{'creation_id':'456'})
            self.assertNotIn('private-token',str(error.exception))
            self.assertEqual(call.call_count,1)
