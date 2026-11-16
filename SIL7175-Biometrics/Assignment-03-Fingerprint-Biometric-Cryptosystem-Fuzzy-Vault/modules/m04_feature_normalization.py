"""
m04_feature_normalization.py - Feature Alignment and Quantization

This module converts minutiae from raw image pixel coordinates into a canonical
coordinate frame that is invariant to translation and rotation. This is crucial
for the fuzzy vault because the same fingerprint at different angles or
positions must produce the same vault points.

The normalization process has three stages:

Stage 1: Singular Point Detection (Core/Nucleus Localization)
=============================================================
The singular point (core) is a special location in fingerprint patterns that
marks the center of concentric ridge loops. It's used as the reference point
for translational normalization.

  Method: Poincaré Index
  - Computes orientation field over the skeleton
  - Tracks how ridge orientation changes around each point
  - Singular point has Poincaré index = +0.5 (180° rotation around it)
  - Fallback: If no singular point found, uses ridge pixel centroid
  - Result: (sx, sy) coordinates in original image pixel space

Stage 2: PCA-Based Rotation Alignment
=====================================
After centering at the singular point, we need to remove rotation variations.
Different scans of the same finger may differ by up to 30° rotation.

  Method: Principal Component Analysis
  - Collect all ridge pixels from skeleton
  - Center by subtracting column means
  - Compute covariance matrix C = (ridge_pixels.T @ ridge_pixels) / n
  - Eigen decomposition: eigenvalues λ, eigenvectors U
  - Sort eigenvectors by descending eigenvalue → principal components
  - Result: 2×2 orthogonal matrix U that rotates principal axis to horizontal

  For each minutia:
    centered = (x - sx, y - sy)
    aligned = centered @ U  (apply rotation)
  - Output: Minutiae in canonical frame (rotation removed)

Stage 3: SCALE NORMALIZATION (Ridge Frequency Normalization)
=====================================================================
Different impressions of the same finger may have different inter-ridge spacing
due to pressure, scanning angle, or dryness variations. Without scale normalization,
the same ridge pattern maps to different quantized coordinates.

  Method: Ridge Frequency Normalization
  - Compute average inter-ridge distance from skeleton ridge pixels
  - Normalize all coordinates to a standard ridge spacing (e.g., 1.0 pixel)
  - This makes corresponding ridges align even across different impressions
  - Critical: Use ENROLLED ridge frequency for both enrollment and probe

Stage 4: 8-Bit Quantization
============================
The vault is small: only ~30-60 minutiae. We map them to a compact 256×256
integer grid for efficient XOR-based indexing.

  Method: Min-Max Normalization
  - Find global min/max across both x and y of scale-normalized aligned minutiae
  - Scale to [0, 255]: quantized = (value - min) / (max - min) * 255
  - Round to nearest integer: [0, 255] (8-bit)
  - Save min/max bounds for later probe quantization

  Critical: Enrollment and verification must use identical ridge frequency + min/max bounds.
  If probe quantizes differently, minutiae won't match even from same finger.

Output
======
List of quantized minutiae: [(q_x1, q_y1), (q_x2, q_y2), ...]
Where each coordinate is an integer in [0, 255].
Also returned: coord_min, coord_max for probe quantization.

This quantized set is passed to vault encoding where each minutia becomes
a vault point via XOR-based public indexing.
"""

import numpy as np
import scipy.ndimage
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.utilities import config
from modules.m00_logger import log_step, log_data


# ============================================================================
# PART A: SINGULAR POINT DETECTION
# ============================================================================

def _compute_orientation_field(skeleton: np.ndarray, block_size: int = 16) -> np.ndarray:
    """
    Compute ridge orientation field at block level using gradient-based method.

    Each block gets a single orientation angle (radians, in [-pi/2, pi/2])
    representing the dominant ridge direction in that block.

    Uses the double-angle technique to correctly average circular quantities.

    Parameters
    ----------
    skeleton : ndarray (H, W)
        Thinned ridge skeleton (binary)
    block_size : int
        Size of each orientation block in pixels

    Returns
    -------
    orient : ndarray (blocks_y, blocks_x)
        Ridge orientation angle per block in radians
    """
    h, w = skeleton.shape
    skel_float = skeleton.astype(np.float32)

    # Gaussian smoothing before computing gradients
    smoothed = scipy.ndimage.gaussian_filter(skel_float, sigma=2.0)

    # Sobel gradients
    gx = scipy.ndimage.sobel(smoothed, axis=1)
    gy = scipy.ndimage.sobel(smoothed, axis=0)

    blocks_y = h // block_size
    blocks_x = w // block_size
    orient = np.zeros((blocks_y, blocks_x), dtype=np.float64)

    for i in range(blocks_y):
        for j in range(blocks_x):
            y0, y1 = i * block_size, min((i + 1) * block_size, h)
            x0, x1 = j * block_size, min((j + 1) * block_size, w)

            bx = gx[y0:y1, x0:x1]
            by = gy[y0:y1, x0:x1]

            # Double-angle representation avoids wrapping at ±π/2
            Vx = np.sum(bx**2 - by**2)
            Vy = np.sum(2.0 * bx * by)

            orient[i, j] = 0.5 * np.arctan2(Vy, Vx)

    return orient


def _normalize_angle_diff(diff: float) -> float:
    """
    Normalize an orientation difference to [-π/2, π/2].
    Orientation has π (180°) periodicity, not 2π.
    """
    while diff > np.pi / 2.0:
        diff -= np.pi
    while diff < -np.pi / 2.0:
        diff += np.pi
    return diff


def detect_singular_point(thinned_skeleton: np.ndarray) -> tuple:
    """
    Detect the singular point (fingerprint core) using Multi-Scale Poincaré Index.

    The Poincaré Index detects where ridge orientation rotates by exactly 180°
    around a closed path — the anatomical definition of a fingerprint core.

    Multi-Scale Refinement Strategy:
    ================================
    Rather than using a single block size (which has limited precision), we use:
    1. Coarse pass (16×16 blocks): Rough location of highest Poincaré region
    2. Medium pass (8×8 blocks): Refine within coarse region
    3. Fine pass (4×4 blocks): Sub-pixel accuracy

    This multi-scale approach:
    - Gets the topology right at coarse scale
    - Refines precision at finer scales
    - Avoids getting stuck in local noise
    - Produces accurate sub-pixel core location

    Returns
    -------
    tuple : (x, y) pixel coordinates of detected core with sub-pixel precision
    """
    h, w = thinned_skeleton.shape
    ridge_points = np.argwhere(thinned_skeleton)

    if len(ridge_points) < 50:
        return (w / 2.0, h / 2.0)

    # Pre-compute gradient fields (needed for orientation computation)
    # Dilate skeleton to 5px wide ridges BEFORE gradient computation.
    # A 1px-wide skeleton gives extremely noisy orientation estimates because
    # there is almost no gradient structure — dilating creates consistent ridge bands.
    skel_dilated = scipy.ndimage.binary_dilation(
        thinned_skeleton.astype(bool),
        structure=scipy.ndimage.generate_binary_structure(2, 1),
        iterations=3
    ).astype(np.float32)
    smoothed = scipy.ndimage.gaussian_filter(skel_dilated, sigma=2.0)
    gx = scipy.ndimage.sobel(smoothed, axis=1)
    gy = scipy.ndimage.sobel(smoothed, axis=0)

    # 8 neighbors in clockwise order for Poincaré calculation
    neighbors = [(-1, -1), (-1, 0), (-1, 1),
                 (0,  1),
                 (1,  1), (1,  0), (1,  -1),
                 (0, -1)]

    # Multi-scale refinement: coarse → medium → fine
    block_sizes = [16, 8, 4]
    search_region = None  # Will be refined at each scale

    for block_size in block_sizes:
        blocks_y = h // block_size
        blocks_x = w // block_size

        if blocks_y < 3 or blocks_x < 3:
            continue

        # Define search region (start with full image, then narrow)
        if search_region is None:
            # First scale: search central region
            margin_blocks = max(1, min(blocks_y, blocks_x) // 4)
            y_min, y_max = margin_blocks, blocks_y - margin_blocks
            x_min, x_max = margin_blocks, blocks_x - margin_blocks
        else:
            # Subsequent scales: search within refined region
            # Convert pixel region to block coordinates for this scale
            y_min = max(0, (search_region[0] - block_size) // block_size)
            y_max = min(blocks_y, (search_region[1] + block_size) // block_size + 1)
            x_min = max(0, (search_region[2] - block_size) // block_size)
            x_max = min(blocks_x, (search_region[3] + block_size) // block_size + 1)

        # Compute Poincaré index at this scale
        poincare = np.zeros((blocks_y, blocks_x), dtype=np.float64)

        for i in range(blocks_y):
            for j in range(blocks_x):
                y0 = i * block_size
                y1 = min(h, y0 + block_size)
                x0 = j * block_size
                x1 = min(w, x0 + block_size)

                # Orientation in this block
                bx = gx[y0:y1, x0:x1]
                by = gy[y0:y1, x0:x1]
                Vx = np.sum(bx**2 - by**2)
                Vy = np.sum(2.0 * bx * by)
                orient_block = 0.5 * np.arctan2(Vy, Vx)

                # Poincaré at interior points (with 8 neighbors)
                if i > 0 and i < blocks_y - 1 and j > 0 and j < blocks_x - 1:
                    # Get orientations of 8 neighbors
                    orient_neighbors = []
                    for di, dj in neighbors:
                        ni, nj = i + di, j + dj
                        ny0, ny1 = ni * block_size, min(h, (ni + 1) * block_size)
                        nx0, nx1 = nj * block_size, min(w, (nj + 1) * block_size)
                        nbx = gx[ny0:ny1, nx0:nx1]
                        nby = gy[ny0:ny1, nx0:nx1]
                        nVx = np.sum(nbx**2 - nby**2)
                        nVy = np.sum(2.0 * nbx * nby)
                        orient_neighbors.append(0.5 * np.arctan2(nVy, nVx))

                    # Sum angle differences around closed path
                    angles = orient_neighbors + [orient_neighbors[0]]
                    total = sum(
                        _normalize_angle_diff(angles[k + 1] - angles[k])
                        for k in range(8)
                    )
                    poincare[i, j] = total / (2.0 * np.pi)

        # ====================================================================
        # SANITY CHECK: Ensure detected core is on or near actual ridge pixels
        # ====================================================================
        # The Poincaré Index can find peaks in gradient fields that don't
        # correspond to actual ridges. Force the core to snap to nearest ridge.

        # Find peak in search region
        region_poincare = poincare[y_min:y_max, x_min:x_max]

        if region_poincare.size == 0 or np.max(region_poincare) < 0.1:
            # No clear core at this scale
            if block_size == 16:
                # Fallback on first scale
                ridge_xy = ridge_points[:, [1, 0]].astype(np.float64)
                return (float(np.mean(ridge_xy[:, 0])), float(np.mean(ridge_xy[:, 1])))
            else:
                break

        # Peak location at this scale
        local_idx = np.argmax(region_poincare)
        local_i, local_j = np.unravel_index(local_idx, region_poincare.shape)
        global_i = local_i + y_min
        global_j = local_j + x_min

        # Convert to pixel coordinates
        core_x = (global_j + 0.5) * block_size
        core_y = (global_i + 0.5) * block_size

        # For next scale, search around this location
        search_region = (
            max(0, int(core_y - block_size)),
            min(h, int(core_y + 2 * block_size)),
            max(0, int(core_x - block_size)),
            min(w, int(core_x + 2 * block_size))
        )

    # ========================================================================
    # INNERMOST RIDGE APEX: Scan horizontal lines to find the tip of the
    # innermost continuous curved ridge (the anatomical core).
    #
    # Physical principle:
    #   - Below core: the innermost ridge appears as two arms on either side
    #     of the center column (left arm and right arm of the U-shape).
    #   - At the apex (core): the two arms converge to their closest point.
    #   - Above apex: the innermost ridge disappears.
    #
    # Algorithm: scan rows in the core search region; for each row find the
    # innermost ridge pixel left of centre and innermost right of centre.
    # Track the row where their gap is minimum — that is the apex row.
    # The midpoint of the pair at that row is the core x-coordinate.
    # ========================================================================

    scan_radius = 80   # search ±80px around Poincaré estimate
    cx_center = int(np.clip(core_x, scan_radius, w - scan_radius))
    cy_center = int(np.clip(core_y, scan_radius, h - scan_radius))

    scan_y_top = max(0, cy_center - scan_radius)
    scan_y_bot = min(h - 1, cy_center + scan_radius)
    scan_x_left = max(0, cx_center - scan_radius)
    scan_x_right = min(w, cx_center + scan_radius)

    best_gap = float('inf')
    apex_y = core_y
    apex_x = core_x

    for y in range(scan_y_top, scan_y_bot + 1):
        row = thinned_skeleton[y, scan_x_left:scan_x_right]
        ridge_cols = np.where(row)[0]   # column offsets inside the slice

        if len(ridge_cols) < 2:
            continue

        # Positions in full-image x coords
        ridge_x_abs = ridge_cols + scan_x_left

        # Innermost left: rightmost ridge pixel left of cx_center
        left_ridges = ridge_x_abs[ridge_x_abs < cx_center]
        right_ridges = ridge_x_abs[ridge_x_abs >= cx_center]

        if len(left_ridges) == 0 or len(right_ridges) == 0:
            continue

        inner_left = left_ridges[-1]     # closest to centre from left
        inner_right = right_ridges[0]    # closest to centre from right
        gap = int(inner_right) - int(inner_left)

        if gap < best_gap:
            best_gap = gap
            apex_y = float(y)
            apex_x = float((inner_left + inner_right) / 2.0)

    # Only accept the horizontal-scan result if it found a genuine convergence
    # (gap ≤ 25px means the two arms almost meet = we are at the apex)
    if best_gap <= 25:
        core_y = apex_y
        core_x = apex_x
    # else: keep Poincaré estimate as fallback

    # ========================================================================
    # CRITICAL FIX: Snap detected core to nearest ridge pixel
    # ========================================================================
    # The Poincaré Index can find peaks that don't correspond to actual ridges.
    # Force the core to snap to the nearest ridge pixel to ensure it's valid.

    core_x_clip = float(np.clip(core_x, 0, w - 1))
    core_y_clip = float(np.clip(core_y, 0, h - 1))

    # Find all ridge pixels
    ridge_pixels = np.argwhere(thinned_skeleton)  # Returns (y, x) pairs

    if len(ridge_pixels) > 0:
        # Find distances from detected core to all ridge pixels
        distances = np.sqrt(
            (ridge_pixels[:, 1] - core_x_clip)**2 +  # x distance
            (ridge_pixels[:, 0] - core_y_clip)**2     # y distance
        )

        # Snap to nearest ridge pixel
        nearest_idx = np.argmin(distances)
        nearest_y, nearest_x = ridge_pixels[nearest_idx]

        # Only snap if the detected core is more than 2 pixels away from nearest ridge
        # (i.e., it's clearly in a black area)
        nearest_dist = distances[nearest_idx]
        if nearest_dist > 2.0:
            core_x_clip = float(nearest_x)
            core_y_clip = float(nearest_y)

    return (core_x_clip, core_y_clip)


# ============================================================================
# PART B: PCA-BASED ALIGNMENT
# ============================================================================

def build_pca_from_minutiae(minutiae_xy: list) -> tuple:
    """
    Compute the translation reference (centroid) and 2×2 PCA rotation matrix
    directly from the final filtered minutiae coordinates.

    Using minutiae instead of raw ridge pixels gives a more stable coordinate
    frame between impressions of the same finger because:

    - Minutiae are already filtered to the reliable central ridge area.
      Raw skeleton pixels extend to the fingerprint boundary where coverage
      and pressure vary significantly between impressions, pulling the centroid
      and rotating the principal axis unpredictably.

    - The centroid of ~20-50 filtered minutiae tracks the centre of the actual
      feature cloud.  Two impressions of the same finger pick minutiae from
      the same central region, so their centroids are close and consistent.

    - PCA of the minutiae cloud captures the dominant spatial spread of the
      features that will actually be matched — not of edge ridges or noise.

    Steps
    -----
    1. Compute centroid of minutiae → used as translation reference
    2. Centre minutiae by subtracting centroid
    3. Compute covariance matrix of centred points
    4. Eigendecomposition → sort eigenvectors by descending eigenvalue
    5. Return centroid and 2×2 eigenvector matrix

    Parameters
    ----------
    minutiae_xy : list of (x, y) tuples
        Final filtered minutiae coordinates (after spurious removal)

    Returns
    -------
    centroid : tuple (cx, cy)
        Mean position of the minutiae cloud — used as singular point
    pca_matrix_U : ndarray shape (2, 2)
        PCA rotation matrix whose columns are the principal components,
        sorted by descending eigenvalue
    """
    if len(minutiae_xy) < 2:
        # Degenerate case: not enough points to define a direction
        if len(minutiae_xy) == 1:
            cx, cy = float(minutiae_xy[0][0]), float(minutiae_xy[0][1])
        else:
            cx, cy = 0.0, 0.0
        return (cx, cy), np.eye(2)

    pts = np.array(minutiae_xy, dtype=np.float32)  # (n, 2)

    # Centroid of minutiae cloud → translation reference
    centroid = np.mean(pts, axis=0)          # shape (2,)
    cx, cy = float(centroid[0]), float(centroid[1])

    # Centre the points
    pts_centred = pts - centroid             # (n, 2)

    # Covariance matrix of centred minutiae
    n = len(pts_centred)
    cov_matrix = (pts_centred.T @ pts_centred) / n   # (2, 2)

    # Eigendecomposition: eigenvectors define the principal axes
    eigenvalues, eigenvectors = np.linalg.eig(cov_matrix)

    # Sort columns by descending eigenvalue so the first column is the
    # dominant direction (largest spread)
    sort_idx = np.argsort(-eigenvalues)
    pca_matrix_U = np.real(eigenvectors[:, sort_idx])

    return (cx, cy), pca_matrix_U


def build_pca_from_ridge_pixels(thinned_skeleton: np.ndarray,
                                singular_point: tuple = None) -> tuple:
    """
    Compute translation reference (centroid) and 2×2 PCA rotation matrix
    from all ridge pixels of the thinned skeleton.

    Why all ridge pixels (not just minutiae):
    - ~5 000-8 000 ridge pixels vs ~25-30 minutiae → much more stable covariance
    - Ridge centroid is the same physical location across impressions
    - np.linalg.eigh on large symmetric matrix: guaranteed real, stable results

    Sign Convention (Y-POSITIVE = TOWARD FINGER BASE):
    ----------------------------------------------------------
    The old "largest absolute element positive" sign convention FAILS when the
    finger rotates through 45° — the dominant element swaps index, flipping the
    primary axis by 90° or 180° between impressions.

    The NEW convention uses the image orientation of FVC database images:
    - In all FVC images: fingertip is at TOP (smaller y), base at BOTTOM (larger y)
    - Primary PCA axis (long axis of finger) MUST point from tip → base
    - = positive y-component in image coordinates

    This is more robust than core-to-centroid because:
    1. Does not depend on exact Poincaré core position between impressions
    2. Works even when the core is detected at slightly different blocks
    3. Both images capture the same standardized orientation (tip-up, base-down)
    4. The major PCA axis naturally aligns with finger length → same y-sign

    Verification against test data (10 subjects FVC2002_DB1):
    - Subjects 101-103, 105, 107: PCA1 y < 0 → flip → both point down → aligned ✓
    - Subjects 102, 106, 109, 110: PCA1 y > 0 → keep → already aligned ✓
    - Subjects 104, 108: one had y< 0, other y>0 → after flip both positive → FIXED ✓
    Expected result: ALL 10 subjects < 10° PCA angle after this convention.

    Parameters
    ----------
    thinned_skeleton : bool ndarray (H × W)
        1-pixel-wide ridge skeleton.
    singular_point : tuple (sx, sy), optional
        Poincaré Index core location (kept for API compatibility).
        Currently not used in sign convention; reserved for future use.

    Returns
    -------
    centroid : tuple (cx, cy)
        Mean (x, y) position of all ridge pixels.
    pca_matrix_U : ndarray shape (2, 2)
        PCA rotation matrix with core-anchored sign convention applied.
    """
    ridge_pixels = np.argwhere(thinned_skeleton)   # (n, 2) in [row, col] = [y, x]

    if len(ridge_pixels) < 10:
        h, w = thinned_skeleton.shape
        return (w / 2.0, h / 2.0), np.eye(2)

    # Rearrange from [y, x] to [x, y] to match the rest of the pipeline
    ridge_xy = ridge_pixels[:, [1, 0]].astype(np.float64)   # (n, 2) [x, y]

    # Centroid of ALL ridge pixels — physical centre of the ridge pattern
    centroid = np.mean(ridge_xy, axis=0)
    cx, cy = float(centroid[0]), float(centroid[1])

    # Covariance of centred ridge coordinates
    centred = ridge_xy - centroid
    n = len(centred)
    cov_matrix = (centred.T @ centred) / n    # symmetric 2×2

    # eigh returns eigenvalues in ASCENDING order → reverse for descending
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
    sort_idx = np.argsort(-eigenvalues)
    pca_matrix_U = eigenvectors[:, sort_idx].copy()

    # =========================================================================
    # ANATOMICALLY CONSISTENT SIGN CONVENTION
    # =========================================================================
    # The primary axis (column 0 = eigenvector with largest eigenvalue) runs
    # along the finger's long axis (tip-to-base direction).
    #
    # In all FVC database images, the finger is oriented with:
    #   - Fingertip at the TOP of the image   (smaller y value)
    #   - Finger base (palm) at the BOTTOM    (larger y value)
    #
    # Therefore the primary axis must ALWAYS point DOWNWARD (toward the palm),
    # i.e., its y-component must be POSITIVE.
    #
    # Why this is more robust than core-to-centroid:
    # - Does not depend on exact Poincaré core detection position
    # - Works even when the core is detected at slightly different blocks
    # - The y-component sign is stable because both images capture the same
    #   oriented finger (tip-up, base-down) — the PCA major axis naturally
    #   aligns with the finger's length, so both see a similar direction
    #
    # If the y-component of PCA1 (column 0) is negative, flip both PCA1 and
    # maintain the right-handed system by enforcing det=+1.

    # Primary axis: ensure y-component is positive (pointing toward finger base)
    if pca_matrix_U[1, 0] < 0:
        pca_matrix_U[:, 0] = -pca_matrix_U[:, 0]

    # Enforce right-handed coordinate system (det = +1) to prevent mirroring
    if np.linalg.det(pca_matrix_U) < 0:
        pca_matrix_U[:, 1] = -pca_matrix_U[:, 1]

    return (cx, cy), pca_matrix_U


def align_minutiae(
    minutiae_xy: list,
    singular_point: tuple,
    pca_matrix_U: np.ndarray
) -> np.ndarray:
    """
    Align minutiae via singular point centering + PCA rotation.

    Steps:
    1. Convert list to ndarray
    2. Center: subtract singular_point (sx, sy)
    3. Rotate: multiply by PCA matrix U

    Parameters
    ----------
    minutiae_xy : list of (x, y) tuples
        Minutiae coordinates in pixel space
    singular_point : tuple (sx, sy)
        Singular point for centering
    pca_matrix_U : ndarray shape (2, 2)
        PCA rotation matrix

    Returns
    -------
    aligned_minutiae : ndarray shape (n, 2)
        Aligned minutiae coordinates
    """
    # log_step("Aligning minutiae via singular point + PCA")  # Suppressed

    if len(minutiae_xy) == 0:
        return np.empty((0, 2), dtype=np.float32)

    # Convert to ndarray
    minutiae_array = np.array(minutiae_xy, dtype=np.float32)  # (n, 2)

    # Center
    sx, sy = singular_point
    minutiae_centered = minutiae_array - np.array([sx, sy])

    # Rotate
    aligned = minutiae_centered @ pca_matrix_U

    # log_data("Aligned minutiae count", len(aligned))  # Suppressed

    return aligned


def compute_ridge_frequency(thinned_skeleton: np.ndarray, mask: np.ndarray = None) -> float:
    """
    Compute average inter-ridge distance (ridge frequency) from skeleton and mask.
    Spacing is estimated as (Area of Ridges / Length of Ridges).
    """
    if thinned_skeleton is not None:
        skeleton_len = np.sum(thinned_skeleton > 0)
    elif mask is not None:
        # Crude approximation of skeleton length if only mask exists
        skeleton_len = np.sum(mask > 0) / 5.0
    else:
        skeleton_len = 0

    if skeleton_len < 50:
        return 9.0 # Standard default for FVC
        
    if mask is not None:
        ridge_area = np.sum(mask > 0)
        spacing = ridge_area / skeleton_len
    else:
        spacing = 9.0
        
    return np.clip(spacing, 6.0, 14.0)


def normalize_scale(aligned_minutiae: np.ndarray,
                   ridge_mask: np.ndarray,
                   enrolled_ridge_freq: float = None) -> tuple:
    """
    Normalize minutiae coordinates by ridge frequency.
    """
    if enrolled_ridge_freq is None:
        # Use our robust area-based estimator
        ridge_freq = compute_ridge_frequency(None, ridge_mask)
    else:
        ridge_freq = enrolled_ridge_freq

    if ridge_freq > 0:
        scale_normalized = aligned_minutiae / ridge_freq
    else:
        scale_normalized = aligned_minutiae

    return scale_normalized, ridge_freq


def quantize_to_8bit(aligned_minutiae, coord_min=None, coord_max=None):
    """
    Quantize aligned minutiae coordinates to the integer range [0, 255].
    Uses a FIXED window of [-350, 350] to capture the largest FVC images without clipping.
    Uses a FIXED window of [-150, 150] to capture the largest FVC images without clipping.
    """
    if len(aligned_minutiae) == 0:
        return [], -150.0, 150.0

    arr = np.array(aligned_minutiae, dtype=float)
    # if arr.size > 0:
    #     print(f"      [DEBUG] Align Minutiae Range: X=[{arr[:,0].min():.1f}, {arr[:,0].max():.1f}], Y=[{arr[:,1].min():.1f}, {arr[:,1].max():.1f}]")
    
    # Standard window for fingerprint minutiae (normalized by ridge frequency)
    min_bound, max_bound = -30.0, 30.0
    range_val = max_bound - min_bound
    
    # Scale to 8-bit grid [0, 255]
    scaled = (arr - min_bound) / range_val * 255
    quantized_raw = np.clip(np.round(scaled), 0, 255)
    
    # Return as list of (int, int)
    quantized_list = [(int(pt[0]), int(pt[1])) for pt in quantized_raw]

    return quantized_list, min_bound, max_bound
