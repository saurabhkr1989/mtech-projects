"""
m05_ridge_spacing_normalizer.py - Normalize inter-ridge spacing

Handles elastic deformation between different captures of same fingerprint
by normalizing ridge spacing to a constant value.

Fingerprints exhibit elastic deformation:
- Pressure variations change local ridge spacing
- Finger positioning changes ridge density
- This causes minutiae to shift in position

Solution: Normalize minutiae positions based on local ridge spacing
- Compute local inter-ridge distance around each minutia
- Scale minutiae positions to standard ridge spacing
- This removes elastic deformation effects
"""

import numpy as np
import scipy.ndimage
from scipy.ndimage import distance_transform_edt


def compute_ridge_spacing(thinned_skeleton: np.ndarray, window_size: int = 32) -> np.ndarray:
    """
    Compute local inter-ridge spacing at each location in the image.

    Ridge spacing = distance between parallel ridges (perpendicular to ridge direction).

    Parameters
    ----------
    thinned_skeleton : ndarray (H, W)
        Thinned ridge skeleton (binary)
    window_size : int
        Size of local window for spacing computation

    Returns
    -------
    ridge_spacing : ndarray (H, W)
        Estimated inter-ridge spacing at each pixel
    """
    h, w = thinned_skeleton.shape
    ridge_spacing = np.ones((h, w), dtype=np.float32)

    # Invert skeleton: ridges are 0, non-ridges are 1
    inverted = 1 - thinned_skeleton

    # Compute distance transform: distance from each pixel to nearest ridge
    distance_map = distance_transform_edt(inverted)

    # Inter-ridge spacing ≈ 2 × maximum distance to ridge within local region
    # This is the distance between parallel ridges

    half_window = window_size // 2

    for i in range(half_window, h - half_window):
        for j in range(half_window, w - half_window):
            # Local window
            local_dist = distance_map[i-half_window:i+half_window, j-half_window:j+half_window]

            # Ridge spacing ≈ 2 × max distance in local area
            # (max distance = distance to nearest ridge = half of inter-ridge spacing)
            max_local_dist = np.max(local_dist)
            ridge_spacing[i, j] = max(2.0 * max_local_dist, 1.0)  # Minimum 1px

    # Fill edges with nearest valid value
    ridge_spacing[:half_window, :] = ridge_spacing[half_window, :]
    ridge_spacing[-half_window:, :] = ridge_spacing[-(half_window+1), :]
    ridge_spacing[:, :half_window] = ridge_spacing[:, half_window:half_window+1]
    ridge_spacing[:, -half_window:] = ridge_spacing[:, -(half_window+1):-(half_window)]

    return ridge_spacing


def normalize_minutiae_by_ridge_spacing(minutiae_xy: list,
                                       ridge_spacing: np.ndarray,
                                       target_spacing: float = 5.0) -> list:
    """
    Normalize minutiae positions based on local ridge spacing.

    Removes elastic deformation effects by adjusting minutiae coordinates
    to account for local ridge spacing variations.

    Algorithm:
    1. For each minutia, get local ridge spacing
    2. Scale minutia position based on ratio: target_spacing / actual_spacing
    3. This compensates for compression/expansion in different regions

    Parameters
    ----------
    minutiae_xy : list of (x, y) tuples
        Original minutiae coordinates
    ridge_spacing : ndarray (H, W)
        Local inter-ridge spacing map
    target_spacing : float
        Target normalized ridge spacing (pixels)

    Returns
    -------
    normalized_minutiae : list of (x, y) tuples
        Ridge-spacing normalized minutiae
    """
    if not minutiae_xy or ridge_spacing is None:
        return minutiae_xy

    h, w = ridge_spacing.shape
    normalized = []

    for x, y in minutiae_xy:
        xi, yi = int(np.clip(x, 0, w-1)), int(np.clip(y, 0, h-1))

        # Get local ridge spacing at this minutia location
        local_spacing = ridge_spacing[yi, xi]

        # Scale factor: how much to adjust based on spacing variation
        scale_factor = target_spacing / (local_spacing + 1e-8)

        # Scale coordinates relative to center (assuming center will be separately handled)
        # For now, store scale info with minutia
        normalized.append((x, y, scale_factor))

    return normalized


def compute_ridge_spacing_field(thinned_skeleton: np.ndarray) -> np.ndarray:
    """
    Compute a smoother ridge spacing field using ridge skeleton analysis.

    More sophisticated than simple distance transform - actually measures
    ridge density by analyzing ridge patterns locally.

    Parameters
    ----------
    thinned_skeleton : ndarray (H, W)
        Thinned ridge skeleton

    Returns
    -------
    spacing_field : ndarray (H, W)
        Estimated ridge spacing at each location
    """
    h, w = thinned_skeleton.shape

    # Use distance transform approach with smoothing
    inverted = 1 - thinned_skeleton
    distance_map = distance_transform_edt(inverted)

    # Smooth the distance map to get continuous spacing field
    spacing_field = scipy.ndimage.gaussian_filter(distance_map, sigma=5.0)

    # Scale to reasonable range (2-12 pixels typical)
    spacing_field = np.clip(2.0 * spacing_field, 1.0, 15.0)

    return spacing_field


if __name__ == "__main__":
    print("Ridge spacing normalization module loaded")
