"""Fast, dependency-light image QA for UMBRAL.

Detects objective rendering defects, not semantic mistakes or bad anatomy.
"""
import numpy as np
from PIL import Image, ImageOps


def assess_image(image, previous=None):
    """Return (score, reasons). Higher score is better; hard failures are flagged."""
    rgb = ImageOps.exif_transpose(image).convert('RGB').resize((128, 192))
    pixels = np.asarray(rgb, dtype=np.float32)
    gray = pixels.mean(axis=2)
    contrast = float(gray.std())
    saturation = float((pixels.max(axis=2) - pixels.min(axis=2)).mean())
    detail = float(np.abs(np.diff(gray, axis=0)).mean() +
                   np.abs(np.diff(gray, axis=1)).mean())
    mean = float(gray.mean())
    reasons = []
    if contrast < 9:
        reasons.append('low_contrast')
    if detail < 2.0:
        reasons.append('blur_or_flat')
    if mean < 8 or mean > 248:
        reasons.append('exposure')
    if saturation < 2 and contrast < 18:
        reasons.append('near_monochrome_flat')
    similarity = 0.0
    if previous is not None:
        prev = np.asarray(ImageOps.exif_transpose(previous).convert('RGB').resize((128, 192)), dtype=np.float32)
        similarity = float(np.abs(pixels - prev).mean())
        if similarity < 5:
            reasons.append('near_duplicate')
    score = min(contrast, 60) * .5 + min(detail, 30) + min(saturation, 45) * .1
    if previous is not None:
        score += min(similarity, 30) * .3
    score -= len(reasons) * 30
    return round(score, 2), reasons
