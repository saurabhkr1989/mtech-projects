"""
m00_roi_detector.py - Region of Interest (ROI) Detection

Locates the region of interest (ROI) in a fingerprint image.
The core point serves as the reference for all alignment transformations.

Per reference implementation, the core point is DETERMINISTIC:
  core_point = (w // 2, h // 2)

This is NOT detected via orientation coherence or Poincaré index.
It's simply the image center, which provides a stable reference
across different impressions of the same finger.
"""

import numpy as np


class ROIResult:
    """Container for ROI detection results."""
    def __init__(self, mask, roi_image, core_point, bbox, confidence, source):
        self.mask = mask
        self.roi_image = roi_image
        self.core_point = core_point  # (x, y) tuple
        self.bbox = bbox              # (x_min, y_min, x_max, y_max)
        self.confidence = confidence  # float [0, 1]
        self.source = source          # "deterministic" or method name


def locate_roi(image: np.ndarray) -> ROIResult:
    """
    Locate ROI in fingerprint image using deterministic image center.

    Uses the image center as the core point, which provides a stable,
    reproducible reference for alignment across all impressions of
    the same finger.

    Parameters
    ----------
    image : ndarray
        Input fingerprint image (any shape)

    Returns
    -------
    ROIResult
        Contains:
          - mask: full-image mask (all 255)
          - roi_image: copy of input image
          - core_point: (w//2, h//2) — deterministic image center
          - bbox: (0, 0, w-1, h-1)
          - confidence: 1.0 (deterministic, always reliable)
          - source: "deterministic"
    """
    h, w = image.shape[:2]

    # Full-image ROI mask (everything is valid)
    mask = np.ones_like(image, dtype=np.uint8) * 255

    # Bounding box covers entire image
    bbox = (0, 0, w - 1, h - 1)

    # DETERMINISTIC core point: image center (per reference implementation)
    core_point = (w // 2, h // 2)

    return ROIResult(
        mask=mask,
        roi_image=image.copy(),
        core_point=core_point,
        bbox=bbox,
        confidence=1.0,
        source="deterministic"
    )
