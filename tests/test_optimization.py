"""Regressions for bounded file hashing and publication scheduling order."""
import hashlib
import datetime as dt
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
    def test_expensive_private_render_is_explicit_and_branch_scoped(self):
        """Normal PR validation must never download models or spend CPU on renders."""
        import yaml
        workflow = yaml.load(
            Path(".github/workflows/episode_integration_gate.yml").read_text(),
            Loader=yaml.BaseLoader)
        condition = workflow["jobs"]["private-render"]["if"]
        self.assertEqual(condition,
            "github.event_name == 'workflow_dispatch' && "
            "github.ref == 'refs/heads/integration/umbral-3'")
        self.assertIn("pull_request", workflow["on"])
        self.assertIn("workflow_dispatch", workflow["on"])

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

    def test_pages_length_mismatch_avoids_full_download(self):
        class Remote(io.BytesIO):
            headers = {"Content-Length": "999"}
            def read(self, *args):
                raise AssertionError("Should not download mismatched remote asset")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "video.mp4"
            path.write_bytes(b"abc")
            with patch("scripts.wait_public_video.urllib.request.urlopen", return_value=Remote()):
                self.assertFalse(check_remote(path, "https://example.com/video.mp4"))

    def test_intent_is_durable_after_wait_and_before_single_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            (out/'prepared.json').write_text(json.dumps({'date':'2026-11-17','status':'prepared','container':'abc'}))
            events=[]
            with patch.object(publisher,'OUT',out), patch.object(publisher,'intent_path',return_value=out/'absent.json'), patch.object(publisher,'already_published',side_effect=lambda *a:(events.append('meta-read') or None)) as reader, patch.object(publisher,'now_local',return_value=dt.datetime(2026,11,17,20,30,tzinfo=publisher.TZ)), patch.object(publisher,'persist_intent',side_effect=lambda *a:events.append('persist')), patch.object(publisher,'wait_until_target',side_effect=lambda *a:events.append('wait')), patch.object(publisher,'api',side_effect=lambda *a:(events.append('post') or {'id':'123'})) as api, patch.object(publisher,'record_verified',side_effect=lambda *a:events.append('verify')):
                publisher.publish('2026-11-17')
                self.assertEqual(events,['meta-read','wait','persist','meta-read','post','verify'])
                self.assertEqual(reader.call_count,2)
                api.assert_called_once_with('POST',f'{publisher.ACCOUNT}/media_publish',{'creation_id':'abc'})

    def test_last_second_meta_duplicate_skips_irreversible_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            (out/'prepared.json').write_text(json.dumps({
                'date':'2026-11-17','status':'prepared','container':'abc'}))
            event=[]
            now=dt.datetime(2026,11,17,21,0,tzinfo=publisher.TZ)
            existing={'id':'already-in-meta','media_product_type':'REELS'}
            with patch.object(publisher,'OUT',out), patch.object(
                publisher,'intent_path',return_value=out/'absent.json'), patch.object(
                publisher,'already_published',side_effect=[None,existing]) as read, patch.object(
                publisher,'now_local',return_value=now), patch.object(
                publisher,'persist_intent',side_effect=lambda *a:event.append('persist')), patch.object(
                publisher,'api') as api, patch.object(
                publisher,'record_verified') as receipt:
                publisher.publish('2026-11-17')
                read.assert_has_calls([unittest.mock.call('2026-11-17')]*2)
                self.assertEqual(event,['persist'])
                api.assert_not_called()
                receipt.assert_called_once()
                self.assertEqual(receipt.call_args.args[1],'already-in-meta')

    def test_failed_final_meta_read_never_posts_or_claims_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            (out/'prepared.json').write_text(json.dumps({
                'date':'2026-11-17','status':'prepared','container':'abc'}))
            now=dt.datetime(2026,11,17,21,0,tzinfo=publisher.TZ)
            with patch.object(publisher,'OUT',out), patch.object(
                publisher,'intent_path',return_value=out/'absent.json'), patch.object(
                publisher,'already_published',side_effect=[None,RuntimeError('Meta listing incomplete')]), patch.object(
                publisher,'now_local',return_value=now), patch.object(
                publisher,'persist_intent') as persisted, patch.object(
                publisher,'api') as api, patch.object(
                publisher,'record_verified') as receipt:
                with self.assertRaisesRegex(RuntimeError,'Meta listing incomplete'):
                    publisher.publish('2026-11-17')
                persisted.assert_called_once()
                api.assert_not_called()
                receipt.assert_not_called()

    def test_expired_date_after_final_read_never_posts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            (out/'prepared.json').write_text(json.dumps({
                'date':'2026-11-17','status':'prepared','container':'abc'}))
            now=dt.datetime(2026,11,17,23,59,tzinfo=publisher.TZ)
            tomorrow=dt.datetime(2026,11,18,0,0,tzinfo=publisher.TZ)
            with patch.object(publisher,'OUT',out), patch.object(
                publisher,'intent_path',return_value=out/'absent.json'), patch.object(
                publisher,'already_published',side_effect=[None,None]), patch.object(
                publisher,'now_local',side_effect=[now,now,tomorrow]), patch.object(
                publisher,'persist_intent') as persist, patch.object(
                publisher,'api') as api, patch.object(
                publisher,'record_verified') as receipt:
                with self.assertRaisesRegex(RuntimeError,'Expired date during final'):
                    publisher.publish('2026-11-17')
                persist.assert_called_once()
                api.assert_not_called()
                receipt.assert_not_called()

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
