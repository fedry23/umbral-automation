import unittest
import numpy as np
from PIL import Image
from image_quality import assess_image


class ImageQualityTests(unittest.TestCase):
    def test_rejects_blank_image(self):
        _, reasons = assess_image(Image.new('RGB', (384, 640), (0, 0, 0)))
        self.assertIn('low_contrast', reasons)
        self.assertIn('exposure', reasons)

    def test_accepts_detailed_image(self):
        rng = np.random.default_rng(42)
        image = Image.fromarray(rng.integers(20, 230, (640, 384, 3), dtype=np.uint8))
        _, reasons = assess_image(image)
        self.assertEqual(reasons, [])

    def test_dark_cinematic_scene_is_not_rejected(self):
        rng = np.random.default_rng(17)
        pixels = rng.integers(4, 34, (640, 384, 3), dtype=np.uint8)
        image = Image.fromarray(pixels)
        _, reasons = assess_image(image)
        self.assertEqual(reasons, [])

    def test_rejects_duplicate(self):
        rng = np.random.default_rng(3)
        image = Image.fromarray(rng.integers(20, 230, (640, 384, 3), dtype=np.uint8))
        _, reasons = assess_image(image, image)
        self.assertIn('near_duplicate', reasons)


if __name__ == '__main__':
    unittest.main()
