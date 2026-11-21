"""Safety policy for a main-only, no-secret, no-Meta OIDC verification workflow."""
from pathlib import Path
import re
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/umbral3_hf_storage.yml"
PROBE=ROOT/"scripts/umbral3_hf_probe.py"

class ProductionOIDCPolicyTests(unittest.TestCase):
    def test_production_probe_policy_stays_nonpublishing(self):
        data=yaml.load(WORKFLOW.read_text(encoding="utf-8"),Loader=yaml.BaseLoader)
        self.assertEqual(data["permissions"],{"contents":"read"})
        self.assertEqual(set(data["jobs"]),{"production-oidc-probe"})
        job=data["jobs"]["production-oidc-probe"]
        self.assertEqual(job["permissions"],{"contents":"read","id-token":"write"})
        self.assertIn("refs/heads/main",job["if"])
        self.assertIn("fedry23/umbral-automation",job["if"])
        self.assertEqual(job["env"]["UMBRAL_HF_BUCKET"],"Fedry23/umbral-private")
        triggers=data["on"]
        self.assertEqual(triggers["push"]["branches"],["main"])
        self.assertEqual(triggers["push"]["paths"],["ops/umbral3-storage-kick.txt"])
        self.assertNotIn("schedule",triggers)
        joined=WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("IG_ACCESS_TOKEN",joined)
        self.assertNotIn("IG_PUBLISH_ENABLED",joined)
        self.assertNotIn("graph.facebook.com",joined)
        self.assertNotIn("upload-artifact",joined)
    def test_production_probe_does_not_import_renderer_or_post_to_meta(self):
        source=PROBE.read_text(encoding="utf-8")
        self.assertIn("https://huggingface.co/oauth/token",source)
        self.assertIn("ACTIONS_ID_TOKEN_REQUEST_TOKEN",source)
        self.assertIn("UMBRAL_HF_BUCKET",source)
        self.assertNotIn("IG_ACCESS_TOKEN",source)
        self.assertNotIn("instagram_media_id",source)
        self.assertNotIn("graph.facebook.com",source)
        self.assertNotIn("import render",source)
        self.assertEqual(re.findall(r"^PROBE = ",source,re.M).__len__(),1)

if __name__=="__main__":
    unittest.main()
