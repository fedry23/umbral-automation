import unittest
from scripts.umbral3_semantic import choose_candidate

def candidate(margin=0, semantic=10, technical=20, reasons=()):
    return {"semantic_score": semantic, "semantic_margin": margin, "score": technical, "reasons": reasons}

class SemanticTests(unittest.TestCase):
    def test_reject_technical_defect_even_with_higher_score(self):
        self.assertEqual(choose_candidate([candidate(30, 99, reasons=["exposure"]), candidate(1)]), 1)
    def test_discriminates_target_instead_of_generic_high_score(self):
        self.assertEqual(choose_candidate([candidate(-2, 40), candidate(3, 25)]), 1)
    def test_deterministic_tiebreak(self):
        self.assertEqual(choose_candidate([candidate(1), candidate(1)]), 0)
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            choose_candidate([candidate(float("nan"))])
    def test_all_bad(self):
        with self.assertRaises(RuntimeError):
            choose_candidate([candidate(reasons=["blur"])])
