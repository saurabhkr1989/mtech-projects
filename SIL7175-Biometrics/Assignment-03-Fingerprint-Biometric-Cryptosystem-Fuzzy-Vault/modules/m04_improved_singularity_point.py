"""
m04_improved_singularity_point.py - Biological Core Detection and PCA Alignment
"""

import numpy as np
import cv2
import math

def estimate_orientation_map(image: np.ndarray, block_size: int = 16) -> np.ndarray:
    image_f = image.astype(np.float32) / 255.0
    grad_x = cv2.Sobel(image_f, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(image_f, cv2.CV_32F, 0, 1, ksize=3)
    gxx = cv2.GaussianBlur(grad_x * grad_x, (0, 0), block_size // 2)
    gyy = cv2.GaussianBlur(grad_y * grad_y, (0, 0), block_size // 2)
    gxy = cv2.GaussianBlur(grad_x * grad_y, (0, 0), block_size // 2)
    orientation = 0.5 * np.arctan2(2.0 * gxy, gxx - gyy + 1e-8)
    orientation = (orientation + np.pi) % np.pi
    return orientation

def build_foreground_mask(enhanced_image: np.ndarray) -> np.ndarray:
    _, binary = cv2.threshold(enhanced_image, 127, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    return (closed > 0).astype(np.uint8)

def _compute_singularity_map(orientation_map: np.ndarray, mask: np.ndarray):
    cos_2theta = np.cos(2.0 * orientation_map)
    sin_2theta = np.sin(2.0 * orientation_map)
    kernel_size = 31
    blur_cos = cv2.GaussianBlur(cos_2theta, (kernel_size, kernel_size), 0)
    blur_sin = cv2.GaussianBlur(sin_2theta, (kernel_size, kernel_size), 0)
    coherence = np.sqrt(blur_cos**2 + blur_sin**2)
    singularity_score = 1.0 - coherence
    dist_map = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
    max_dist = dist_map.max()
    if max_dist > 0:
        safe_mask = (dist_map > (0.1 * max_dist)).astype(np.uint8)
    else:
        safe_mask = mask.copy()
    singularity_score = singularity_score * safe_mask
    hotspot = cv2.GaussianBlur(singularity_score, (15, 15), 0)
    return hotspot, dist_map, max_dist

def detect_singular_point(orientation_map: np.ndarray, mask: np.ndarray) -> tuple:
    hotspot, _, _ = _compute_singularity_map(orientation_map, mask)
    _, max_val, _, max_loc = cv2.minMaxLoc(hotspot)
    if max_val > 0.05:
        return max_loc
    M = cv2.moments(mask)
    if M["m00"] != 0:
        return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
    return (mask.shape[1] // 2, mask.shape[0] // 2)

def detect_multiple_singular_points(orientation_map: np.ndarray, mask: np.ndarray, max_candidates: int = 5) -> list:
    hotspot, _, _ = _compute_singularity_map(orientation_map, mask)
    candidates = []
    temp_map = hotspot.copy()
    for _ in range(max_candidates):
        _, max_val, _, max_loc = cv2.minMaxLoc(temp_map)
        if max_val < 0.03: break
        candidates.append(max_loc)
        cv2.circle(temp_map, max_loc, 40, 0, -1)
    M = cv2.moments(mask)
    if M["m00"] != 0:
        centroid = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
        if centroid not in candidates:
            candidates.append(centroid)
            
    return candidates

def compute_pca_matrix(skeleton: np.ndarray, center_point: tuple = None, local_radius: int = 120) -> np.ndarray:
    y_skel, x_skel = np.where(skeleton > 0)
    all_pts = np.stack([x_skel, y_skel], axis=1).astype(np.float32)
    if len(all_pts) < 50: return np.eye(2, dtype=np.float32)
    if center_point is not None:
        cx, cy = float(center_point[0]), float(center_point[1])
        dists = np.hypot(all_pts[:, 0] - cx, all_pts[:, 1] - cy)
        local_mask = dists <= local_radius
        A = all_pts[local_mask]
        if len(A) < 50: A = all_pts
    else:
        A = all_pts
    mean_A = np.mean(A, axis=0)
    A_centered = A - mean_A
    cov_matrix = (A_centered.T @ A_centered) / (len(A) - 1)
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
    idx = eigenvalues.argsort()[::-1]
    U = eigenvectors[:, idx].astype(np.float32)
    if U[1, 0] < 0: U[:, 0] *= -1
    if np.linalg.det(U) < 0: U[:, 1] *= -1
    return U

def compute_pca_angle(U: np.ndarray) -> float:
    ux, uy = U[0, 0], U[1, 0]
    return math.degrees(math.atan2(uy, ux)) % 360

def align_minutiae(minutiae_xy: list, singular_point: tuple, pca_matrix: np.ndarray) -> np.ndarray:
    if len(minutiae_xy) == 0: return np.zeros((0, 2), dtype=np.float32)
    arr = np.array(minutiae_xy, dtype=np.float32)
    sx, sy = singular_point
    centered = arr - np.array([sx, sy], dtype=np.float32)
    return centered @ pca_matrix.T

def detect_biological_core(orientation_map: np.ndarray, mask: np.ndarray) -> tuple:
    return detect_singular_point(orientation_map, mask)
