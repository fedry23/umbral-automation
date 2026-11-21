"""Full UMBRAL 3 must preserve main's minimal, least-privilege OIDC identity."""
from pathlib import Path
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]

class OIDCIdentityIntegrationTests(unittest.TestCase):
    def test_main_identity_probe_stays_isolated_from_publication(self):
        w=yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                    Loader=yaml.BaseLoader)
        self.assertEqual(w["permissions"],{"contents":"read"})
        self.assertIn("main",w["on"]["push"]["branches"])
        self.assertEqual(w["on"]["push"]["paths"],["ops/umbral3-storage-kick.txt"])
        job=w["jobs"]["production-oidc-probe"]
        self.assertIn("refs/heads/main",job["if"])
        self.assertIn("fedry23/umbral-automation",job["if"])
        self.assertEqual(job["permissions"],{"contents":"read","id-token":"write"})
        self.assertEqual(job["env"]["UMBRAL_HF_BUCKET"],"Fedry23/umbral-private")
        combined=str(job)
        self.assertNotIn("IG_ACCESS_TOKEN",combined)
        self.assertNotIn("graph.facebook.com",combined)
        self.assertNotIn("upload-artifact",combined)
        self.assertIn("umbral3_hf_probe",combined)
    def test_refill_requires_owner_control_and_has_no_meta_permissions(self):
        w=yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                    Loader=yaml.BaseLoader)
        refill=w["jobs"]["daily-refill"]
        self.assertIn("refs/heads/main",refill["if"])
        self.assertIn("vars.UMBRAL3_RESERVE_ENABLED != 'false'",refill["if"])
        self.assertEqual(refill["permissions"],{"contents":"read","id-token":"write"})
        self.assertIn("scripts.umbral3_rollout --mode refill",str(refill["steps"]))
        self.assertNotIn("IG_ACCESS_TOKEN",str(refill))
        self.assertNotIn("graph.facebook.com",str(refill))
    def test_existing_development_trusted_publisher_claims_preserved(self):
        w=yaml.load((ROOT/".github/workflows/umbral3_hf_storage.yml").read_text(),
                    Loader=yaml.BaseLoader)
        self.assertIn("integration/umbral-3",w["on"]["push"]["branches"])
        self.assertIn("refs/heads/integration/umbral-3",w["jobs"]["verify"]["if"])
