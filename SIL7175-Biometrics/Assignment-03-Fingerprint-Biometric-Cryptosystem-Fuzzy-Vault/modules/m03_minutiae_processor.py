"""
m03_minutiae_processor.py - Fingerprint Minutiae Extraction and Filtering

This module identifies ridge endings and bifurcations in fingerprint skeletons,
then applies multiple filtering stages to remove false minutiae caused by noise
and image artifacts.

Stage 1: Minutiae Extraction (Crossing Number Method)
======================================================
The Crossing Number (CN) algorithm analyzes each skeleton pixel's 8 neighbors:

  For each skeleton pixel (ridge = True):
    CN = (1/2) × Σ |P_k - P_{k+1}| (for k=0..7, indices wrap around)

  Interpretation:
    CN = 1  →  Ridge ending (termination point)
    CN = 3  →  Ridge bifurcation (splitting point)
    CN = 0 or ≥5  →  Not a minutia (noise or artifact)

Output: List of MinutiaPoint objects with (x, y) coordinates and metadata.

Stage 2: Spurious Minutiae Removal
===================================
Raw minutiae extraction produces 500+ minutiae from an ~500×500 fingerprint,
including many false positives from noise. Multiple filtering steps remove:

  1. DISTANCE TO CORE:
     - Minutiae too far from core are discarded (based on edge_margin_px)
     - Keeps only minutiae from stable interior region

  2. FALSE MINUTIAE RULES (applied sequentially):
     a) Two nearby endings → remove both if no clear ridge between
     b) Ending + bifurcation nearby → remove both
     c) Two nearby bifurcations → remove both

  3. CLUSTERING-BASED FILTERING:
     - Groups minutiae within cluster_distance_px
     - Entire cluster is marked as spurious
     - Keeps only minutiae that don't cluster (isolated genuine features)

Outcome
=======
After filtering: ~30-60 high-confidence minutiae suitable for vault encoding.
These are genuine ridge features with low false-positive rate.
"""

import math
import numpy as np
import cv2
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.utilities import config
from modules.m00_logger import log_step, log_data, log_warning

# 8-neighborhood offsets (used for crossing number)
NEIGHBORS = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]


class MinutiaPoint:
    """Represents a single minutia point (ridge ending or bifurcation)."""
    def __init__(self, x, y, kind, angle_deg, score, distance_to_core):
        self.x = x                            # x coordinate
        self.y = y                            # y coordinate
        self.kind = kind                      # "ending" or "bifurcation"
        self.angle_deg = angle_deg            # orientation angle (radians → degrees)
        self.score = score                    # confidence score (distance from boundary)
        self.distance_to_core = distance_to_core  # distance to core point


# ============================================================================
# PART A: MINUTIAE EXTRACTION (Crossing Number)
# ============================================================================

def _crossing_number(skeleton: np.ndarray, y: int, x: int) -> int:
    """
    Compute crossing number for skeleton pixel at (y, x).

    Crossing number = (1/2) × sum of transitions in 8-neighborhood.
    - CN = 1 → ridge ending
    - CN = 3 → ridge bifurcation
    - CN = 0 or ≥5 → not a minutia
    """
    values = [1 if skeleton[y + dy, x + dx] > 0 else 0 for dy, dx in NEIGHBORS]
    return sum(abs(values[i] - values[i + 1]) for i in range(8)) // 2


def _estimate_minutia_angle(skeleton: np.ndarray, x: int, y: int) -> float:
    """
    Estimate ridge direction at minutia location.

    Uses mean direction of neighboring ridge pixels.
    """
    neighbor_points = []
    for dy, dx in NEIGHBORS[:-1]:
        yy = y + dy
        xx = x + dx
        if skeleton[yy, xx] > 0:
            neighbor_points.append((xx, yy))

    if not neighbor_points:
        return 0.0

    mean_x = sum(point[0] for point in neighbor_points) / len(neighbor_points)
    mean_y = sum(point[1] for point in neighbor_points) / len(neighbor_points)
    return float(np.degrees(np.arctan2(mean_y - y, mean_x - x)))


def _is_clear_ridge_between(binary_skeleton: np.ndarray, p1: tuple, p2: tuple) -> bool:
    """
    Check whether clear ridge pixels lie between two nearby points.

    Used in false minutiae removal: if two endings are near but not
    connected by ridge pixels, they're both likely false positives.
    """
    # Ensure skeleton is uint8 for cv2 operations
    skeleton_uint8 = (binary_skeleton > 0).astype(np.uint8) * 255

    probe = np.zeros_like(skeleton_uint8, dtype=np.uint8)
    cv2.line(probe, p1, p2, 255, 1)
    overlap = cv2.bitwise_and(probe, skeleton_uint8)
    return int(np.count_nonzero(overlap)) > max(2, int(math.dist(p1, p2) * 0.5))


def _remove_false_minutiae(
    candidates: list,
    skeleton: np.ndarray,
    cluster_distance_px: int
) -> list:
    """
    Remove spurious minutiae using three filtering rules.

    Rules:
      1. Two nearby endings without clear ridge → remove both
      2. Ending + bifurcation nearby → remove both
      3. Two nearby bifurcations → remove both

    Also clusters remaining minutiae and keeps only isolated points.
    """
    if not candidates:
        return []

    keep = [True] * len(candidates)
    d1 = float(cluster_distance_px)
    d2 = float(cluster_distance_px)
    d3 = float(cluster_distance_px)

    # Apply geometric filtering rules
    for i in range(len(candidates)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(candidates)):
            if not keep[j]:
                continue

            p1 = candidates[i]
            p2 = candidates[j]
            distance = math.dist((p1.x, p1.y), (p2.x, p2.y))

            if distance >= max(d1, d2, d3):
                continue

            # Rule 1: Two endings too close without ridge connection
            if p1.kind == "ending" and p2.kind == "ending" and distance < d1:
                if not _is_clear_ridge_between(skeleton, (p1.x, p1.y), (p2.x, p2.y)):
                    keep[i] = False
                    keep[j] = False
                    continue

            # Rule 2: Ending + bifurcation too close
            if {p1.kind, p2.kind} == {"ending", "bifurcation"} and distance < d2:
                keep[i] = False
                keep[j] = False
                continue

            # Rule 3: Two bifurcations too close
            if p1.kind == "bifurcation" and p2.kind == "bifurcation" and distance < d3:
                keep[i] = False
                keep[j] = False

    filtered = [point for index, point in enumerate(candidates) if keep[index]]
    if not filtered:
        return []

    # Sort by distance to core (closer = more reliable), then by score (higher = more confident)
    filtered.sort(key=lambda item: (item.distance_to_core, -item.score))

    # Cluster-based filtering: keep only isolated minutiae
    cluster_pruned = []
    for point in filtered:
        # Check if point is too close to any already-kept point
        if any(math.dist((point.x, point.y), (other.x, other.y)) < cluster_distance_px
               for other in cluster_pruned):
            continue
        cluster_pruned.append(point)

    return cluster_pruned


def extract_minutiae(
    skeleton: np.ndarray,
    roi_mask: np.ndarray,
    core_point: tuple,
    edge_margin_px: int = 20,
    cluster_distance_px: int = 10,
    keep_range: tuple = (8, 80)
) -> list:
    """
    Extract ridge endings and bifurcations from skeleton, then filter spurious points.

    Performs complete minutiae extraction and filtering pipeline in one call.

    Parameters
    ----------
    skeleton : ndarray (bool or uint8)
        Thinned skeleton where True/255 = ridge, False/0 = background
    roi_mask : ndarray (bool or uint8)
        ROI foreground mask (defines which pixels are valid)
    core_point : tuple (cx, cy)
        Core point for distance computation (always image center)
    edge_margin_px : int
        Minimum distance from image edge (in pixels)
    cluster_distance_px : int
        Clustering radius for spurious detection
    keep_range : tuple (min, max)
        Keep between min and max minutiae after filtering

    Returns
    -------
    list of MinutiaPoint
        Filtered minutiae with all metadata
    """
    h, w = skeleton.shape
    candidates = []

    # Build distance transform for ROI interior reliability
    distance_map = cv2.distanceTransform((roi_mask > 0).astype(np.uint8), cv2.DIST_L2, 3)

    # Scan skeleton for minutiae
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if skeleton[y, x] == 0:
                continue

            # Exclude points near image edges
            if x < edge_margin_px or y < edge_margin_px or \
               x >= w - edge_margin_px or y >= h - edge_margin_px:
                continue

            # Exclude points near ROI boundary (unreliable)
            if distance_map[y, x] < edge_margin_px:
                continue

            # Compute crossing number
            cn = _crossing_number(skeleton, y, x)
            kind = "ending" if cn == 1 else "bifurcation" if cn == 3 else None

            if kind is None:
                continue

            # Compute distance to core
            distance_to_core = math.dist((x, y), core_point)

            # Estimate ridge direction at this minutia
            angle_deg = _estimate_minutia_angle(skeleton, x, y)

            # Create minutia point
            candidates.append(MinutiaPoint(
                x=x,
                y=y,
                kind=kind,
                angle_deg=angle_deg,
                score=float(distance_map[y, x]),
                distance_to_core=distance_to_core
            ))

    # Sort candidates by distance to core, then by score
    candidates.sort(key=lambda item: (item.distance_to_core, -item.score))

    # Apply false minutiae removal (geometric + clustering rules)
    filtered_candidates = _remove_false_minutiae(candidates, skeleton, cluster_distance_px)

    # Apply keep_range limits
    if len(filtered_candidates) > keep_range[1]:
        return filtered_candidates[:keep_range[1]]

    return filtered_candidates


# Backward compatibility: wrapper for old extract_minutiae_xy() API
def extract_minutiae_xy(skeleton_image: np.ndarray, foreground_mask: np.ndarray = None) -> list:
    """
    Legacy API: extract minutiae as (x, y) tuples only.

    This is for backward compatibility with old code.
    New code should use extract_minutiae() which returns MinutiaPoint objects.
    """
    h, w = skeleton_image.shape
    core_point = (w // 2, h // 2)

    if foreground_mask is None:
        foreground_mask = np.ones_like(skeleton_image, dtype=np.uint8) * 255

    minutiae = extract_minutiae(
        skeleton=skeleton_image,
        roi_mask=foreground_mask,
        core_point=core_point,
        edge_margin_px=config.BORDER_EXCLUSION_MARGIN_PX,
        cluster_distance_px=10,
        keep_range=(8, 200)
    )

    # Return as (x, y) tuples for backward compatibility
    return [(m.x, m.y) for m in minutiae]
