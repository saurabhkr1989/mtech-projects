"""
m01_image_preprocessing.py - Fingerprint Image Processing Pipeline

This module transforms raw fingerprint images into processed skeletons ready for
minutiae extraction. The pipeline consists of three major stages:

1. SEGMENTATION (Block-Based Variance)
   - Divides image into 16×16 blocks
   - Computes variance in each block
   - Marks blocks with low variance (smooth areas) as background
   - Marks blocks with high variance (ridge structures) as foreground
   - Excludes top/bottom margins to remove scanner artifacts
   - Result: Binary foreground mask indicating valid fingerprint region

2. ENHANCEMENT (Gabor Filter Bank)
   - Applies oriented Gabor filters to enhance ridge/valley contrast
   - Uses 8 orientations and Deshmukh's frequency (0.1)
   - Produces binary map where ridges appear white
   - Critical for low-quality images; helps make thin ridges visible
   - Uses global caching: Gabor kernels computed once, reused across images
   - Optional GPU acceleration via CUDA if available

3. THINNING (Morphological Skeletonization)
   - Reduces ridge patterns from multi-pixel width to 1-pixel skeleton
   - Uses Zhang-Suen algorithm (via scikit-image.morphology.skeletonize)
   - Preserves connectivity of ridge structures
   - Result: Binary skeleton suitable for minutiae extraction
   - Note: Skeletons may have spurious branches (filled in later)

Output
------
Binary skeleton image (dtype bool) where:
  - True (1) = ridge pixel (part of actual fingerprint ridge pattern)
  - False (0) = background or valley

This skeleton is then passed to the minutiae extraction module to identify
ridge endings and bifurcations.
"""

import numpy as np
import cv2
from skimage.morphology import skeletonize, erosion, ellipse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.utilities import config
from modules.m00_logger import log_step, log_data
import fingerprint_enhancer

# GPU acceleration check
_GPU_ENHANCEMENT_AVAILABLE = False
try:
    from modules.utilities.gpu_accelerator import enhance_with_gpu_gabor, is_gpu_available
    if is_gpu_available():
        _GPU_ENHANCEMENT_AVAILABLE = True
except (ImportError, RuntimeError):
    _GPU_ENHANCEMENT_AVAILABLE = False


# ============================================================================
# PART A: IMAGE LOADING AND SEGMENTATION
# ============================================================================

def _load_as_grayscale(image_path: str) -> np.ndarray:
    """
    Load a fingerprint image as grayscale.

    Reads image file and converts to single-channel grayscale if needed.
    Fingerprint images are naturally represented as grayscale since color
    information carries no biometric value.

    Parameters
    ----------
    image_path : str
        Path to image file (.tif, .bmp, .jpg, etc.)

    Returns
    -------
    np.ndarray
        Grayscale image as uint8 array (shape: height × width)

    Raises
    ------
    ValueError
        If image file cannot be read (file not found, corrupted, unsupported format)
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")
    
    # Debug: verify buffer uniqueness
    import hashlib
    # img_hash = hashlib.sha1(img.tobytes()).hexdigest()
    # print(f"      [DEBUG] Loaded from {os.path.basename(image_path)}: Hash={img_hash[:8]}")
    
    return img


def _segment_by_block_variance(grayscale_img: np.ndarray, block_size: int = 16,
                               threshold: float = 55.0,
                               top_margin_px: int = 20,
                               bottom_margin_px: int = 20) -> np.ndarray:
    """
    Segment the valid fingerprint region using block-level intensity variance.

    The image is divided into non-overlapping square blocks.  Blocks whose
    pixel variance exceeds the threshold are classified as fingerprint
    (foreground); the rest are background (smooth skin or scanner noise).

    After block classification the mask is eroded inward so that minutiae at
    the very edge of the ridge pattern are excluded downstream.

    Parameter tuning rationale (images ~350×330 px):
    - threshold 55: high enough to reject low-contrast scanner-edge blocks
      without discarding genuine ridge texture in the fingerprint centre.
      The previous value of 65 was too aggressive for these image sizes.
    - top/bottom margin 20 px: excludes scanner frame rows without eating into
      the fingerprint area that often starts within 20–30 px of the top.
    - internal erosion 10 px: removes boundary-adjacent blocks that can contain
      partial ridges, while preserving the large central ridge area.

    Parameters
    ----------
    grayscale_img : np.ndarray
        Input grayscale fingerprint image
    block_size : int
        Side length (px) of each classification block (default 16)
    threshold : float
        Variance threshold separating fingerprint texture from background.
    top_margin_px : int
        Pixel rows to force-exclude at the image top (scanner casing artifacts).
    bottom_margin_px : int
        Pixel rows to force-exclude at the image bottom.

    Returns
    -------
    foreground : bool ndarray
        Binary mask (same shape as input) where True = valid fingerprint region
    """
    height, width = grayscale_img.shape
    foreground = np.zeros((height, width), dtype=bool)

    for y in range(top_margin_px, height - bottom_margin_px, block_size):
        for x in range(0, width, block_size):
            y_end = min(y + block_size, height)
            x_end = min(x + block_size, width)
            block = grayscale_img[y:y_end, x:x_end]

            if np.var(block) > threshold:
                foreground[y:y_end, x:x_end] = True

    # Erode inward to push the mask boundary away from the raw fingerprint edge.
    # 10 px is sufficient to exclude partial-ridge blocks while retaining the
    # full central minutiae-rich area for images of ~350 px width.
    margin_px = 10
    kernel = ellipse(margin_px, margin_px)
    foreground = erosion(foreground, kernel)

    return foreground


def _create_central_roi(foreground_mask: np.ndarray, singular_point: tuple = None,
                       core_exclusion_radius: int = 30) -> np.ndarray:
    """
    Create central ROI by excluding:
    1. Core area (circular region around singular point)
    2. Edge artifacts (already done by erosion)

    Parameters
    ----------
    foreground_mask : bool ndarray
        Foreground mask from segmentation
    singular_point : tuple
        (x, y) coordinates of singular point (core)
    core_exclusion_radius : int
        Radius to exclude around core (default 30 pixels)

    Returns
    -------
    central_roi : bool ndarray
        Mask of central region (excluding core area)
    """
    # log_step(f"Creating central ROI (excluding core radius={core_exclusion_radius}px)")  # Suppressed

    central_roi = foreground_mask.copy()

    if singular_point is not None:
        sy, sx = int(singular_point[1]), int(singular_point[0])
        height, width = foreground_mask.shape

        # Create circular mask around singular point
        yy, xx = np.ogrid[:height, :width]
        core_mask = (yy - sy)**2 + (xx - sx)**2 <= core_exclusion_radius**2

        # Exclude core area
        central_roi[core_mask] = False

        # log_data("Excluded core area", f"({sx}, {sy})")  # Suppressed

    # log_data("Central ROI pixels", np.sum(central_roi))  # Suppressed

    return central_roi


# ============================================================================
# PART B: ENHANCEMENT AND BINARIZATION
# ============================================================================

def enhance_and_binarize(raw_image_path: str, threshold: float = 0.05) -> np.ndarray:
    """
    CORRECT ENHANCEMENT PIPELINE:
    1. Load grayscale
    2. Segment foreground
    3. Apply Deshmukh enhancement (CPU or GPU)
    4. Return enhanced image (boolean)

    Uses GPU-accelerated Gabor filtering when available (~5-10x speedup).

    Parameters
    ----------
    raw_image_path : str
        Path to fingerprint image
    threshold : float
        Deshmukh ridge_segment_thresh parameter

    Returns
    -------
    enhanced : bool ndarray
        Enhanced ridge image (True = ridge, False = background)
    """
    # log_step("Loading and enhancing fingerprint image")  # Suppressed

    grayscale = _load_as_grayscale(raw_image_path)

    # Try GPU acceleration first, fallback to CPU
    if _GPU_ENHANCEMENT_AVAILABLE:
        try:
            enhanced_bool = enhance_with_gpu_gabor(grayscale, threshold=threshold)
            return enhanced_bool
        except Exception as e:
            # log_data("GPU enhancement", f"Failed, falling back to CPU: {str(e)}")  # Suppressed
            pass

    # Apply Deshmukh enhancement (CPU fallback)
    enhanced_bool = fingerprint_enhancer.enhance_fingerprint(
        grayscale,
        ridge_segment_thresh=threshold
    )

    return enhanced_bool


# ============================================================================
# PART C: RIDGE THINNING
# ============================================================================

def thin_ridges_to_skeleton(binary_ridge_image: np.ndarray) -> np.ndarray:
    """
    Reduce ridge image to 1-pixel-wide skeleton using morphological thinning.

    Parameters
    ----------
    binary_ridge_image : uint8 ndarray
        255 = ridge, 0 = background

    Returns
    -------
    skeleton : bool ndarray
        True = skeleton pixel, False = background
    """
    # log_step("Thinning ridges to 1-pixel skeleton (Zhang-Suen)")  # Suppressed for clean output

    # Convert to binary (0 or 1)
    ridge_binary = (binary_ridge_image > 0).astype(np.uint8)

    # Apply skimage's skeletonize (Zhang-Suen algorithm)
    skeleton = skeletonize(ridge_binary)

    ridge_pixels = int(skeleton.sum())
    # log_data("Skeleton ridge pixels", ridge_pixels)  # Suppressed

    return skeleton


# ============================================================================
# PUBLIC PIPELINE
# ============================================================================

def preprocess_fingerprint(image_path: str, enhancement_threshold: float = 0.07) -> tuple:
    """
    Complete preprocessing pipeline: load → enhance → thin → skeleton.

    Parameters
    ----------
    image_path : str
        Path to fingerprint image
    enhancement_threshold : float
        Gabor enhancement threshold (default 0.07)

    Returns
    -------
    skeleton : bool ndarray
        1-pixel-wide ridge skeleton
    foreground_mask : bool ndarray
        Foreground mask from segmentation
    """
    # log_step("Starting fingerprint preprocessing pipeline")  # Suppressed

    # Load grayscale
    grayscale = _load_as_grayscale(image_path)

    # Segment foreground
    foreground_mask = _segment_by_block_variance(grayscale)

    # Enhance with Gabor
    enhanced_bool = fingerprint_enhancer.enhance_fingerprint(
        grayscale,
        ridge_segment_thresh=enhancement_threshold
    )
    enhanced_uint8 = (enhanced_bool * 255).astype(np.uint8)

    # The enhancer crops the image to a block-size multiple internally.
    # Pad back to original dimensions so the foreground mask aligns correctly.
    if enhanced_uint8.shape != grayscale.shape:
        gh, gw = grayscale.shape
        eh, ew = enhanced_uint8.shape
        # Create a same-size array and use minimum dimensions to copy pixels
        resampled = np.zeros_like(grayscale)
        bh, bw = min(gh, eh), min(gw, ew)
        resampled[:bh, :bw] = enhanced_uint8[:bh, :bw]
        enhanced_uint8 = resampled

    # Mask out background before thinning so the skeletonizer does not generate
    # false ridge branches in scanner-edge regions that the Gabor enhancer treated
    # as foreground but our variance segmentation correctly excluded.
    enhanced_uint8[~foreground_mask] = 0

    # Thin to skeleton
    skeleton = thin_ridges_to_skeleton(enhanced_uint8)

    # log_step("Preprocessing pipeline complete")  # Suppressed

    return skeleton, foreground_mask


# ============================================================================
# PARALLEL IMAGE BATCH PROCESSING
# ============================================================================

def preprocess_fingerprints_parallel(image_paths: list, enhancement_threshold: float = 0.07, max_workers: int = None) -> list:
    """
    Process multiple fingerprint images in parallel.

    Parameters
    ----------
    image_paths : list
        List of image file paths
    enhancement_threshold : float
        Gabor enhancement threshold (default 0.07)
    max_workers : int
        Number of parallel workers (default: CPU count - 1)

    Returns
    -------
    results : list
        List of (skeleton, foreground_mask) tuples corresponding to input images
    """
    from concurrent.futures import ProcessPoolExecutor
    from multiprocessing import cpu_count

    if max_workers is None:
        max_workers = max(1, cpu_count() - 1)

    # log_step(f"Preprocessing {len(image_paths)} images in parallel ({max_workers} workers)")  # Suppressed

    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(preprocess_fingerprint, path, enhancement_threshold)
            for path in image_paths
        ]

        completed = 0
        for future in futures:
            try:
                result = future.result()
                results.append(result)
                completed += 1
                if completed % max(1, len(image_paths) // 10) == 0:
                    pass  # log_data suppressed
            except Exception as e:
                # log_warning(f"Error processing image: {str(e)}")  # Suppressed
                results.append(None)

    # log_data("Parallel preprocessing complete", f"{completed}/{len(image_paths)}")  # Suppressed
    return results
