"""
m09_vault_encoder.py - Fingerprint Enrollment Pipeline (no cache)

Steps:
1. Load image → segment foreground
2. Gabor enhancement → thin to skeleton
3. Extract minutiae → filter spurious ones
4. Detect singular point + PCA matrix from ridge skeleton
5. Align minutiae → quantize to 8-bit grid
6. Generate 128-bit secret → RS-encode into polynomial coefficients
7. Build vault: for each minutia (x,y):
     u_i = x XOR y          (8-bit public XOR index, per spec)
     v_i = (x<<8)|y         (16-bit evaluation point, stored privately)
     store (u_i, v_i, P(v_i))
   Vault is deduplicated by u_i (spec: V is a set).
   v_i is retained internally so verification can do exact bin matching
   without drowning in XOR-collision false candidates.
"""

import hashlib
import os
import secrets
import sys
import numpy as np
import math
from typing import Dict, Any, List, Optional
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.utilities import config
from modules.utilities.logger import log_section, log_step, log_data, log_success, log_warning
from modules.utilities.progress_tracker import EnrollmentProgressTracker
from modules.m01_image_preprocessing import _load_as_grayscale, _segment_by_block_variance, thin_ridges_to_skeleton
from modules.m03_minutiae_processor import extract_minutiae
from modules.m04_feature_normalization import align_minutiae, quantize_to_8bit, normalize_scale
from modules.m04_improved_singularity_point import (
    estimate_orientation_map,
    build_foreground_mask,
    detect_singular_point,
    compute_pca_matrix
)
from modules.m06_cryptographic_codec import rs_encode, evaluate_polynomial
import fingerprint_enhancer

# Shared Gabor enhancer instance (avoids recomputing kernels per image)
_GABOR_ENHANCER = None


def _get_gabor_enhancer():
    global _GABOR_ENHANCER
    if _GABOR_ENHANCER is None:
        _GABOR_ENHANCER = fingerprint_enhancer.fingerprint_image_enhancer.FingerprintImageEnhancer(
            ridge_segment_thresh=0.07
        )
    return _GABOR_ENHANCER


def enroll(fingerprint_image_path, secret_key_bytes=None, quiet=False,
           use_cache=None, phase_cache_decision=None):
    """
    Enroll a fingerprint and return a vault dict.

    Returns
    -------
    dict with keys:
        enrollment_successful (bool)
        vault_points  : list of [u_i, v_i, P(v_i)] triples
        coord_min, coord_max : quantization bounds
        secret_key_bytes : hex string of the 128-bit key
        secret_key_hash  : SHA-256 hex of the key (for verification)
        singular_point   : [sx, sy]
        pca_matrix_U     : [[a,b],[c,d]]
        image_path       : original path
        vault_size       : number of vault points
    """
    if not quiet:
        log_section(f"ENROLLMENT  ->  {os.path.basename(fingerprint_image_path)}")

    tracker = EnrollmentProgressTracker(os.path.basename(fingerprint_image_path))

    try:
        # ------------------------------------------------------------------
        # Step 1-2: Load + segment
        # ------------------------------------------------------------------
        grayscale = _load_as_grayscale(fingerprint_image_path)
        h, w = grayscale.shape
        tracker.update_step(1, "OK", f"{h}x{w}")

        foreground_mask = _segment_by_block_variance(grayscale,
                                                     top_margin_px=20,
                                                     bottom_margin_px=20)
        foreground_count = int(np.count_nonzero(foreground_mask))
        tracker.update_step(2, "OK", f"{foreground_count} pixels")

        # ------------------------------------------------------------------
        # Step 3: Gabor enhancement
        # ------------------------------------------------------------------
        enhancer = _get_gabor_enhancer()
        enhanced_bool = enhancer.enhance(grayscale)
        enhanced_uint8 = (enhanced_bool * 255).astype(np.uint8)

        if enhanced_uint8.shape != grayscale.shape:
            resampled = np.zeros_like(grayscale)
            bh = min(grayscale.shape[0], enhanced_uint8.shape[0])
            bw = min(grayscale.shape[1], enhanced_uint8.shape[1])
            resampled[:bh, :bw] = enhanced_uint8[:bh, :bw]
            enhanced_uint8 = resampled

        enhanced_uint8[~foreground_mask] = 0
        tracker.update_step(3, "OK", "Gabor enhancement applied")

        # ------------------------------------------------------------------
        # Step 4: Thin to skeleton
        # ------------------------------------------------------------------
        thinned_skeleton = thin_ridges_to_skeleton(enhanced_uint8)
        skeleton_ridge_pixels = int(np.count_nonzero(thinned_skeleton))
        tracker.update_step(4, "OK", f"{skeleton_ridge_pixels} ridge pixels")

        # ------------------------------------------------------------------
        # Step 5: Detect core point via orientation-coherence singularity
        # ------------------------------------------------------------------
        orient_map = estimate_orientation_map(grayscale)
        fp_mask = build_foreground_mask(enhanced_uint8)
        singular_point = detect_singular_point(orient_map, fp_mask)
        tracker.update_step(5, "OK", f"Core at ({singular_point[0]:.1f}, {singular_point[1]:.1f})")

        # ------------------------------------------------------------------
        # Step 6: Extract minutiae with integrated false minutiae removal
        # ------------------------------------------------------------------
        minutiae_points = extract_minutiae(
            skeleton=thinned_skeleton,
            roi_mask=foreground_mask,
            core_point=singular_point,
            edge_margin_px=20,
            cluster_distance_px=10,
            keep_range=(8, 200)
        )
        minutiae_count = len(minutiae_points)
        tracker.update_step(6, "OK", f"{minutiae_count} minutiae extracted & filtered")

        if minutiae_count < config.MIN_MINUTIAE_COUNT:
            msg = f"Only {minutiae_count} minutiae (need {config.MIN_MINUTIAE_COUNT})"
            log_warning(msg)
            tracker.update_step(7, "FAIL", "Insufficient minutiae")
            if not quiet:
                tracker.display_table()
            return {"enrollment_successful": False, "error": msg}

        # Convert MinutiaPoint objects to (x, y) tuples for alignment
        cleaned_minutiae = [(m.x, m.y) for m in minutiae_points]
        removed_count = 0
        removal_pct = 0.0

        # ------------------------------------------------------------------
        # Step 7: Compute PCA matrix for rotation alignment
        # ------------------------------------------------------------------
        pca_matrix = compute_pca_matrix(thinned_skeleton, center_point=singular_point)
        tracker.update_step(7, "OK", "PCA matrix computed")

        # ------------------------------------------------------------------
        # Step 8: Align + scale-normalize + quantize
        # ------------------------------------------------------------------
        aligned = align_minutiae(cleaned_minutiae, singular_point, pca_matrix)
        scaled, ridge_frequency = normalize_scale(aligned, ridge_mask=enhanced_uint8)
        tracker.update_step(8, "OK",
                            f"{len(scaled)} minutiae aligned (ridge_freq={ridge_frequency:.3f})")

        quantized, coord_min, coord_max = quantize_to_8bit(scaled)
        
        # Align angles: subtract PCA dominant axis to become rotation-invariant
        angles = np.array([m.angle_deg for m in minutiae_points])
        pca_angle_deg = math.degrees(math.atan2(pca_matrix[1, 0], pca_matrix[0, 0]))
        aligned_angles = (angles - pca_angle_deg) % 360

        tracker.update_step(9, "OK",
                            f"Quantized to [{coord_min:.2f}, {coord_max:.2f}] with angles")

        # ------------------------------------------------------------------
        # Step 10: Generate secret key
        # ------------------------------------------------------------------
        if secret_key_bytes is None:
            secret_key_bytes = secrets.token_bytes(16)

        if not quiet:
            secret_hex = secret_key_bytes.hex() if isinstance(secret_key_bytes, bytes) else secret_key_bytes
            secret_hash = hashlib.sha256(
                secret_key_bytes if isinstance(secret_key_bytes, bytes) else bytes.fromhex(secret_key_bytes)
            ).hexdigest()
            log_data("[DEBUG] Generated secret", secret_hex)
            log_data("[DEBUG] Secret SHA256", secret_hash[:16] + "...")

        tracker.update_step(10, "OK", "128-bit key generated")

        # ------------------------------------------------------------------
        # Step 11: RS-encode secret → polynomial coefficients
        #   data_symbols = 8 x 16-bit chunks of the 128-bit secret
        #   rs_codeword  = [s0..s7, parity] (9 symbols) over GF(2^16)
        #   poly_coeffs  = rs_codeword  (ascending: c0=constant, c8=x^8)
        # ------------------------------------------------------------------
        data_symbols = [
            int.from_bytes(secret_key_bytes[i:i+2], 'big')
            for i in range(0, 16, 2)
        ]
        rs_codeword = rs_encode(data_symbols, config.RS_PARITY_SYMBOLS)
        poly_coeffs = rs_codeword
        tracker.update_step(11, "OK",
                            f"RS({len(rs_codeword)},{len(data_symbols)}) encoded")

        # ------------------------------------------------------------------
        # Step 12: Build vault
        #
        # Per assignment spec:
        #   u_i = x_i XOR y_i          8-bit public XOR index
        #   v_i = (x_i << 8) | y_i    16-bit polynomial evaluation point
        #   Store (u_i, P(v_i))
        #   Vault V is a SET (no duplicates)
        #
        # We ALSO store v_i privately (as a 3-tuple) so the verifier can do
        # EXACT bin matching without suffering from XOR-collision false matches.
        #
        # Deduplication: Keep one entry per unique (x,y) position only.
        # This maintains the SET property while preserving all minutiae for
        # better geometric matching during verification.
        # ------------------------------------------------------------------
        seen_positions = set()
        vault_points  = []

        for (px, py), ang in zip(quantized, aligned_angles):
            # Scale coordinates into 6-bit grid (0-63) to allow 4 bits for Angle
            x_6b = int(px) >> 2
            y_6b = int(py) >> 2
            theta_bucket = int(ang / 22.5) % 16

            pos = (x_6b, y_6b, theta_bucket)
            if pos in seen_positions:
                continue
            seen_positions.add(pos)

            u_i = x_6b ^ y_6b
            v_i = (x_6b << 10) | (y_6b << 4) | theta_bucket
            p_vi = evaluate_polynomial(poly_coeffs, v_i)
            # 3-tuple: [u_i, v_i, P(v_i)]
            vault_points.append([u_i, v_i, p_vi])

        # ------------------------------------------------------------------
        # Step 13: Add Chaff Points (Noise) to secure the vault
        #
        # Security against impostors relies on the presence of many "chaff"
        # points that are not on the polynomial P(x).  An impostor picking
        # 9 random points from the vault will likely pick many chaff points,
        # leading to a failed RS/Hash reconstruction.
        # ------------------------------------------------------------------
        num_chaff_needed = getattr(config, "VAULT_CHAFF_POINTS", 0)
        if num_chaff_needed > 0:
            chaff_added = 0
            attempts = 0
            while chaff_added < num_chaff_needed and attempts < num_chaff_needed * 10:
                attempts += 1
                # Pick random position in the 6-bit quantization grid and a random 4-bit angle
                rx = secrets.randbelow(64)
                ry = secrets.randbelow(64)
                rt = secrets.randbelow(16)
                
                # Check if this bin is already occupied by a genuine point or chaff
                rv_i = (rx << 10) | (ry << 4) | rt
                if any(p[1] == rv_i for p in vault_points):
                    continue
                
                # Pick a random y value that is NOT on the polynomial
                # (to prevent accidental genuine match)
                p_real = evaluate_polynomial(poly_coeffs, rv_i)
                r_p = secrets.randbelow(65536)
                if r_p == p_real:
                    continue
                
                # Add chaff point: [u_i, v_i, random_P]
                ru_i = rx ^ ry
                vault_points.append([ru_i, rv_i, r_p])
                chaff_added += 1
            
            if not quiet:
                log_data("[DEBUG] Chaff points added", chaff_added)

        if not quiet:
            log_data("[DEBUG] Vault format", "3-tuple [u_i, v_i, P(v_i)]")
            log_data("[DEBUG] Total vault entries", len(vault_points))
            # Show first 5 vault entries so we can verify P(v_i) values during verification
            for idx, entry in enumerate(vault_points[:5]):
                u_i_val, v_i_val, p_vi_val = entry
                log_data(f"[DEBUG] Vault Entry {idx}", f"u_i={u_i_val:3d}, v_i={v_i_val:5d}, P(v_i)={p_vi_val}")

        tracker.update_step(12, "OK", f"{len(vault_points)} vault points created")

        if not quiet:
            tracker.display_table()

        return {
            "enrollment_successful": True,
            "vault_points":   vault_points,      # [[u_i, v_i, P(v_i)], ...]
            "coord_min":      float(coord_min),
            "coord_max":      float(coord_max),
            "ridge_frequency": float(ridge_frequency),  # ✓ SCALE NORMALIZATION
            "secret_key_bytes":  secret_key_bytes.hex(),
            "secret_key_hash":   hashlib.sha256(secret_key_bytes).hexdigest(),
            "singular_point":    list(singular_point),
            "pca_matrix_U":      pca_matrix.tolist(),
            "image_path":        fingerprint_image_path,
            "vault_size":        len(vault_points),
            # ---- legacy detail block (used by CSV exporter) ----
            "detailed_stats": {
                "enroll_file":          os.path.basename(fingerprint_image_path),
                "image_height":         h,
                "image_width":          w,
                "foreground_pixels":    foreground_count,
                "skeleton_ridge_pixels": skeleton_ridge_pixels,
                "singular_point_x":     singular_point[0],
                "singular_point_y":     singular_point[1],
                "raw_minutiae":         minutiae_count,
                "cleaned_minutiae":     minutiae_count,
                "spurious_removed":     removed_count,
                "removal_percentage":   removal_pct,
                "coord_min":            f"{coord_min:.4f}",
                "coord_max":            f"{coord_max:.4f}",
                "quantized_count":      len(quantized),
                "secret_key_hex":       secret_key_bytes.hex(),
                "rs_codeword_length":   len(rs_codeword),
                "vault_points":         len(vault_points),
                "polynomial_degree":    config.POLYNOMIAL_DEGREE,
            },
        }

    except Exception as e:
        import traceback
        log_warning(f"Enrollment failed: {e}\n{traceback.format_exc()}")
        return {"enrollment_successful": False, "error": str(e)}
