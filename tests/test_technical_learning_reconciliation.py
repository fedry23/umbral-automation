import unittest
from scripts.technical_learning import EXPERIMENT, profile_for, evaluate
from scripts.reconcile_publications import reconcile_one

class TechnicalLearning(unittest.TestCase):
    def test_unknown_policy_uses_control(self):
        self.assertEqual(profile_for("2026-11-19", "09", {"mode":"promoted"})["music_gain"],1.0)
    def test_balanced_assignment(self):
        policy={"schema":1,"experiment":EXPERIMENT,"mode":"experiment"}
        for slot in ("09","21"):
            arms=[profile_for(f"2026-11-{day:02d}",slot,policy)["arm"] for day in range(1,21)]
            self.assertEqual(arms.count("music-minus-1.4db"),4)
    def test_invalid_and_sparse_data(self):
        self.assertEqual(evaluate([None,{}, {"media_id":"x","slot":[],"arm":"control"}])["decision"],"hold")
    def rows(self, skip):
        return [{"media_id":f"{slot}-{arm}-{i}", "slot":slot,"arm":arm,
                 "experiment":EXPERIMENT,"quality_passed":True,"editorial_arm":"fixed",
                 "reach":100,"skip":skip if arm!="control" else .5,
                 "watch_seconds":20,"age_hours":168,"duration_seconds":60}
                for slot in ("09","21") for arm in ("control","music-minus-1.4db") for i in range(5)]
    def test_eligible_promotion(self):
        self.assertEqual(evaluate(self.rows(.30))["decision"],"eligible_for_promotion")
    def test_reversion(self):
        self.assertEqual(evaluate(self.rows(.70))["decision"],"revert")
    def test_equal_is_hold(self):
        self.assertEqual(evaluate(self.rows(.50))["decision"],"hold")
    def test_no_duplicate_or_stale_observations(self):
        rows=self.rows(.30)
        self.assertEqual(evaluate([dict(r,age_hours=200) for r in rows])["decision"],"hold")
        self.assertEqual(evaluate([rows[0]]*30)["decision"],"hold")

class Reconciliation(unittest.TestCase):
    def setUp(self):
        self.key="2026-11-19_09"
        self.intent={"date":"2026-11-19","slot":"09","episode_number":12}
        self.media={"id":"123","media_product_type":"REELS","caption":"🩸 UMBRAL · OFICIAL · 2026-11-19 · MAÑANA · EPISODIO 12","permalink":"https://www.instagram.com/reel/test/","timestamp":"2026-11-19T08:00:00Z"}
    def test_unique_verified_media(self):
        result=reconcile_one(self.key,self.intent,{},[self.media],lambda _: self.media)
        self.assertEqual(result["verification"],"published_media_read_back")
        self.assertEqual(result["episode_number"],12)
    def test_missing_or_ambiguous_media(self):
        for media in ([],[self.media,self.media]):
            with self.assertRaises(RuntimeError):
                reconcile_one(self.key,self.intent,{},media,lambda _: self.media)
    def test_mismatched_receipt(self):
        with self.assertRaises(ValueError):
            reconcile_one(self.key,self.intent,{"date":"2026-11-19","episode_number":13},[self.media],lambda _: self.media)
    def test_wrong_timestamp(self):
        with self.assertRaises(ValueError):
            reconcile_one(self.key,self.intent,{},[self.media],lambda _:dict(self.media,timestamp="2026-11-20T08:00:00Z"))
