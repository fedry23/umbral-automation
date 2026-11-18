import unittest
from scripts.technical_evidence import join_observations, ACCOUNT
from scripts.collect_technical_insights import parse_insights
from scripts.technical_learning import profile_for

class TechnicalEvidence(unittest.TestCase):
    def setUp(self):
        self.receipt={"verification":"published_media_read_back","instagram_media_id":"123",
                      "published_at":"2026-11-19T08:00:00Z","slot":"09",
                      "technical_profile":profile_for("2026-11-19","09",
                        {"schema":1,"experiment":"music-balance-v1","mode":"experiment"}),
                      "duration_seconds":71,"editorial_protocol":"fixed-v1",
                      "cover_verification":{"matched":True}}
        self.snapshot={"source":"Windsor.ai Instagram","account":ACCOUNT,
                       "measurement_time_verified":True,"measured_at":"2026-11-26T08:00:00Z",
                       "retrieved_at":"2026-11-26T08:05:00Z","rows":[
                         {"media_id":"123","media_reach":100,"media_reel_skip_rate":.6,
                          "media_reel_avg_watch_time":12500}]}
    def test_valid_join_and_units(self):
        rows, rejected=join_observations([("2026-11-19_09",self.receipt)],[self.snapshot])
        self.assertEqual(len(rows),1)
        self.assertEqual(rejected,[])
        self.assertEqual(rows[0]["watch_seconds"],12.5)
        self.assertEqual(rows[0]["age_hours"],168)
        self.assertEqual(rows[0]["slot"],"09")

    def test_cached_unsupported_and_uncontrolled_excluded(self):
        for snapshot, receipt in [
            ({**self.snapshot,"measurement_time_verified":False},self.receipt),
            (self.snapshot,{**self.receipt,"editorial_protocol":None}),
            (self.snapshot,{**self.receipt,"cover_verification":{"matched":False}}),
            (self.snapshot,{**self.receipt,"slot":"21"}),
            ({**self.snapshot,"measured_at":"2026-11-27T08:00:00Z",
                "retrieved_at":"2026-11-27T09:00:00Z"},self.receipt)]:
            rows, rejected=join_observations([("2026-11-19_09",receipt)],[snapshot])
            self.assertEqual(rows,[])
            self.assertEqual(len(rejected),1)

    def test_meta_live_does_not_mix_with_windsor(self):
        meta={**self.snapshot,"source":"Meta Graph API","retrieval_mode":"live_http",
              "measurement_time_verified":False}
        rows,_=join_observations([("2026-11-19_09",self.receipt)],[meta,self.snapshot,meta])
        self.assertEqual({row["source"] for row in rows},{"Meta Graph API","Windsor.ai Instagram"})
        self.assertEqual(len(rows),2)

    def test_parse_insights(self):
        payload={"data":[{"name":"reach","values":[{"value":80}]},
                         {"name":"reels_skip_rate","values":[{"value":65.2}]},
                         {"name":"ig_reels_avg_watch_time","total_value":{"value":10000}}]}
        parsed=parse_insights(payload)
        self.assertEqual(parsed["media_reach"],80)
        self.assertAlmostEqual(parsed["media_reel_skip_rate"],.652)
        self.assertEqual(parsed["media_reel_avg_watch_time"],10000)
        with self.assertRaises(ValueError):
            parse_insights({"data":payload["data"][:2]})
        with self.assertRaises(ValueError):
            parse_insights({"data":payload["data"]+[payload["data"][0]]})
