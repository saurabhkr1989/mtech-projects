"""
m04_core_detector_refined.py - Refined core detection using ridge endpoint analysis

Detects fingerprint core by finding the tip of the innermost ridge.

Core definition: The apex/endpoint of the innermost ridge that forms
the center of the loop/whorl pattern. This is an anatomically consistent
point across multiple impressions of the same fingerprint.

Algorithm:
1. Multi-scale block-based Poincaré for coarse localization
2. Ridge endpoint detection within coarse region
3. Find the innermost ridge endpoint = true core
"""

import numpy as np
import scipy.ndimage
from scipy.ndimage import binary_erosion, label, distance_transform_edt


def find_ridge_endpoints(thinned_skeleton: np.ndarray,
                        search_y_min: int, search_y_max: int,
                        search_x_min: int, search_x_max: int) -> np.ndarray:
    """
    Find ridge endpoints in a search region.

    Ridge endpoints are pixels with exactly ONE connected ridge neighbor
    (bifurcations have 3+ neighbors, regular ridge pixels have 2).

    Parameters
    ----------
    thinned_skeleton : ndarray (H, W)
        Thinned ridge skeleton (binary)
    search_y_min, search_y_max, search_x_min, search_x_max : int
        Region boundaries

    Returns
    -------
    endpoints : list of (y, x) tuples
        Ridge endpoint locations
    """
    # Extract search region
    region = thinned_skeleton[search_y_min:search_y_max, search_x_min:search_x_max]

    h, w = region.shape
    endpoints = []

    # For each ridge pixel in region, count connected neighbors
    for i in range(1, h - 1):
        for j in range(1, w - 1):
            if region[i, j] == 0:  # Not a ridge pixel
                continue

            # Count 8-connected ridge neighbors
            neighbors = region[i-1:i+2, j-1:j+2]
            ridge_count = np.sum(neighbors) - region[i, j]  # Exclude self

            # Endpoint: exactly 1 connected neighbor
            # (Regular ridge: 2, bifurcation: 3+)
            if ridge_count == 1:
                endpoints.append((i + search_y_min, j + search_x_min))

    return endpoints


def find_innermost_ridge_endpoint(thinned_skeleton: np.ndarray,
                                 core_estimate: tuple,
                                 search_radius: int = 40) -> tuple:
    """
    Find the tip of the innermost ridge starting from core estimate.

    The innermost ridge forms the center of loop/whorl patterns.
    Its endpoint/apex is the true anatomical core.

    Algorithm:
    1. Find all ridge endpoints in search region
    2. The endpoint CLOSEST to core estimate = outermost loop
    3. Trace inward from outermost endpoint → find innermost
    4. Return innermost endpoint = true core

    Parameters
    ----------
    thinned_skeleton : ndarray (H, W)
        Thinned ridge skeleton
    core_estimate : tuple (y, x)
        Approximate core from block-based Poincaré
    search_radius : int
        Search window radius

    Returns
    -------
    core_location : tuple (y, x)
        Refined core location
    confidence : float
        Confidence in detection (0 to 1)
    """
    h, w = thinned_skeleton.shape
    core_y, core_x = core_estimate

    # Define search region
    y_min = max(1, int(core_y) - search_radius)
    y_max = min(h - 1, int(core_y) + search_radius)
    x_min = max(1, int(core_x) - search_radius)
    x_max = min(w - 1, int(core_x) + search_radius)

    # Find all ridge endpoints
    endpoints = find_ridge_endpoints(thinned_skeleton, y_min, y_max, x_min, x_max)

    if not endpoints:
        return core_estimate, 0.0

    endpoints = np.array(endpoints)

    # Strategy: The innermost ridge endpoint is the one FURTHEST FROM IMAGE BOUNDARY
    # OR closest to center of mass of ridge skeleton in region

    # Compute distance from each endpoint to nearest image boundary
    boundary_distances = np.minimum(
        np.minimum(endpoints[:, 0], h - endpoints[:, 0]),  # Top/bottom
        np.minimum(endpoints[:, 1], w - endpoints[:, 1])   # Left/right
    )

    # Innermost endpoint = furthest from boundary
    innermost_idx = np.argmax(boundary_distances)
    innermost_endpoint = endpoints[innermost_idx]

    # Confidence: ratio of innermost to outer distances
    max_dist = np.max(boundary_distances)
    min_dist = np.min(boundary_distances)
    confidence = (max_dist - min_dist) / (max_dist + 1e-8) if max_dist > 0 else 0.0

    return tuple(innermost_endpoint), float(confidence)


def refine_core_with_ridge_endpoints(thinned_skeleton: np.ndarray,
                                    core_block_estimate: tuple) -> tuple:
    """
    Refine block-based core estimate using ridge endpoint analysis.

    Two-step refinement:
    1. Find innermost ridge endpoint within search region
    2. Apply sub-pixel refinement based on local ridge curvature

    Parameters
    ----------
    thinned_skeleton : ndarray (H, W)
        Thinned ridge skeleton
    core_block_estimate : tuple (y, x)
        Core from block-based Poincaré method

    Returns
    -------
    refined_core : tuple (y, x)
        Refined core location
    metrics : dict
        Diagnostic metrics
    """
    # Step 1: Find innermost ridge endpoint
    core_refined, confidence = find_innermost_ridge_endpoint(
        thinned_skeleton,
        core_block_estimate,
        search_radius=40
    )

    # Step 2: Sub-pixel refinement using local ridge orientation
    h, w = thinned_skeleton.shape
    core_y, core_x = core_refined

    # Compute local orientation field around refined core
    window_size = 16
    win_y_min = max(1, int(core_y) - window_size)
    win_y_max = min(h - 1, int(core_y) + window_size)
    win_x_min = max(1, int(core_x) - window_size)
    win_x_max = min(w - 1, int(core_x) + window_size)

    if win_y_max - win_y_min >= 6 and win_x_max - win_x_min >= 6:
        # Extract window and compute orientation gradient
        window_skel = thinned_skeleton[win_y_min:win_y_max, win_x_min:win_x_max]
        window_float = window_skel.astype(np.float32)
        window_smooth = scipy.ndimage.gaussian_filter(window_float, sigma=1.5)

        # Gradients
        gx = scipy.ndimage.sobel(window_smooth, axis=1)
        gy = scipy.ndimage.sobel(window_smooth, axis=0)

        # Orientation field
        Vx = gx**2 - gy**2
        Vy = 2.0 * gx * gy
        orient = 0.5 * np.arctan2(Vy, Vx)

        # Orientation gradient (ridge curvature)
        orient_grad_y = scipy.ndimage.sobel(orient, axis=0)
        orient_grad_x = scipy.ndimage.sobel(orient, axis=1)
        curvature = np.sqrt(orient_grad_y**2 + orient_grad_x**2)

        # Find peak curvature
        max_idx = np.argmax(curvature)
        peak_y, peak_x = np.unravel_index(max_idx, curvature.shape)

        # Sub-pixel refinement: weighted centroid
        if 1 <= peak_y < curvature.shape[0]-1 and 1 <= peak_x < curvature.shape[1]-1:
            neighborhood = curvature[peak_y-1:peak_y+2, peak_x-1:peak_x+2]
            weights = neighborhood.flatten()
            weights = np.maximum(weights, 0)
            weights = weights / (np.sum(weights) + 1e-8)

            y_offsets = np.array([-1, -1, -1, 0, 0, 0, 1, 1, 1])
            x_offsets = np.array([-1, 0, 1, -1, 0, 1, -1, 0, 1])

            offset_y = np.sum(weights * y_offsets)
            offset_x = np.sum(weights * x_offsets)

            core_y_subpix = win_y_min + peak_y + offset_y
            core_x_subpix = win_x_min + peak_x + offset_x

            core_refined = (core_y_subpix, core_x_subpix)

    metrics = {
        'method': 'ridge_endpoint_analysis',
        'confidence': confidence,
        'core_location': core_refined,
    }

    return core_refined, metrics


if __name__ == "__main__":
    print("Refined core detector module loaded")
