import unittest
from scripts.cinematic5_learning import equal_age, compare, arm_for

def row(id="1",observed="2026-11-28T08:00:00Z",arm="control"):
    return {"media_id":id,"published_at":"2026-11-27T08:00:00Z","observed_at":observed,
            "slot":"09","arm":arm,"experiment_id":"hook-v1","skip":.74,"watch_seconds":7.6,"reach":60}

class Cinematic5LearningTest(unittest.TestCase):
    def test_equal_age(self):
        self.assertEqual(len(equal_age([row(),row(observed="2026-11-28T09:00:00Z"),row("2","2026-11-30T08:00:00Z")],24)),1)
    def test_missing_and_small_samples(self):
        a=row(); a["watch_seconds"]=None
        self.assertEqual(compare([a,row("2",arm="experiment")],24)[0]["recommendation"],"insufficient_data")
    def test_invalid_skip(self):
        a=row(); a["skip"]=74
        self.assertEqual(equal_age([a],24),[])
    def test_rollback_advisory(self):
        rows=[row(str(i)) for i in range(10)]
        for i in range(10,20):
            a=row(str(i),arm="experiment"); a["skip"]=.9; a["watch_seconds"]=3; rows.append(a)
        result=compare(rows,24)[0]
        self.assertEqual(result["recommendation"],"review_rollback")
        self.assertFalse(result["automatic_changes"])
    def test_assignment(self):
        self.assertEqual(arm_for("a","hook"),arm_for("a","hook"))
