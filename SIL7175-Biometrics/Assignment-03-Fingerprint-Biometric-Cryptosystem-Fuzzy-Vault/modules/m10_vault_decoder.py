"""
m10_vault_decoder.py - Fingerprint Vault Decoder (Multi-Core Retry)

Verifies a probe fingerprint against an enrolled vault.

Usage:
    is_genuine, secret, stats = verify(probe_image_path, enrollment_data, quiet=False)

Returns a 3-tuple:
    is_genuine (bool)          : True if hash check passed
    secret     (None)          : placeholder (secret stays hidden inside vault)
    stats      (dict)          : matched_points, verdict, lagrange_combos_tried
"""

import numpy as np
import cv2
import hashlib
import math
from modules.m01_image_preprocessing import (
    _load_as_grayscale,
    _segment_by_block_variance,
    thin_ridges_to_skeleton
)
from modules.m04_improved_singularity_point import (
    estimate_orientation_map, build_foreground_mask,
    detect_multiple_singular_points, compute_pca_matrix
)
from modules.m04_feature_normalization import normalize_scale, quantize_to_8bit, align_minutiae
from modules.m03_minutiae_processor import extract_minutiae
from modules.m06_cryptographic_codec import (
    rs_decode, lagrange_interpolate_coefficients
)
from modules.utilities import config


def _make_stats(verdict, matched_points=0, combos_tried=0, rs_check="FAIL", hash_check="FAIL"):
    return {
        "verdict": verdict,
        "matched_points": matched_points,
        "max_hits": matched_points,  # Alias for evaluator compatibility
        "lagrange_combos_tried": combos_tried,
        "rs_pass": rs_check == "PASS",  # Boolean for display: True = PASS, False = FAIL
        "hash_pass": hash_check == "PASS",  # Boolean for display: True = PASS, False = FAIL
    }


def verify(probe_image_path, enrollment_data, quiet=False):
    """
    Verify a probe fingerprint against an enrolled vault.

    Parameters
    ----------
    probe_image_path : str
        Path to the probe fingerprint image.
    enrollment_data : dict
        The dict returned by enroll() — contains vault_points, ridge_frequency,
        secret_key_hash, coord_min, coord_max, etc.
    quiet : bool
        Suppress console output.

    Returns
    -------
    (is_genuine, None, stats)  —  3-tuple
        is_genuine (bool)
        None       (secret is never exposed)
        stats      (dict)  keys: verdict, matched_points, lagrange_combos_tried
    """
    try:
        enrolled_freq = enrollment_data.get("ridge_frequency", 1.0)
        secret_hash   = enrollment_data.get("secret_key_hash")

        # ------------------------------------------------------------------
        # 1. Preprocess probe
        # ------------------------------------------------------------------
        grayscale = _load_as_grayscale(probe_image_path)
        mask      = _segment_by_block_variance(grayscale)

        from modules.m09_vault_encoder import _get_gabor_enhancer
        enhancer      = _get_gabor_enhancer()
        enhanced_bool = enhancer.enhance(grayscale)
        enhanced_uint8 = (enhanced_bool * 255).astype(np.uint8)

        if enhanced_uint8.shape != grayscale.shape:
            resampled = np.zeros_like(grayscale)
            bh = min(grayscale.shape[0], enhanced_uint8.shape[0])
            bw = min(grayscale.shape[1], enhanced_uint8.shape[1])
            resampled[:bh, :bw] = enhanced_uint8[:bh, :bw]
            enhanced_uint8 = resampled

        enhanced_uint8[~mask] = 0
        thinned = thin_ridges_to_skeleton(enhanced_uint8)

        # ------------------------------------------------------------------
        # 2. Detect core candidates (multi-core retry for robustness)
        # ------------------------------------------------------------------
        orient_map      = estimate_orientation_map(grayscale)
        fp_mask         = build_foreground_mask(enhanced_uint8)
        core_candidates = detect_multiple_singular_points(
            orient_map, fp_mask, max_candidates=config.MAX_CORE_CANDIDATES
        )

        best_result = (False, None, _make_stats("REJECT (No Hits)"))

        for probe_core in core_candidates:
            # --------------------------------------------------------------
            # 3. Extract minutiae around this candidate core
            # --------------------------------------------------------------
            minutiae_objs = extract_minutiae(
                skeleton=thinned,
                roi_mask=mask,
                core_point=probe_core,
                edge_margin_px=config.BORDER_EXCLUSION_MARGIN_PX,
                keep_range=(8, 200)   # match encoder's keep_range
            )
            if not minutiae_objs:
                continue

            unaligned_pts    = [(m.x, m.y) for m in minutiae_objs]
            unaligned_angles = np.array([m.angle_deg for m in minutiae_objs])

            # --------------------------------------------------------------
            # 4. Compute PCA for this core
            # --------------------------------------------------------------
            pca_matrix_orig = compute_pca_matrix(thinned, center_point=probe_core)
            pca_angle_deg   = math.degrees(
                math.atan2(pca_matrix_orig[1, 0], pca_matrix_orig[0, 0])
            )

            # --------------------------------------------------------------
            # 5. Try both PCA orientations + small angular perturbations
            #    This handles cases where probe PCA flip differs from enroll.
            # --------------------------------------------------------------
            angles_to_try = [-5, 0, 5]

            for flip in [False, True]:
                pca_matrix_base = -pca_matrix_orig if flip else pca_matrix_orig
                pa_deg = math.degrees(
                    math.atan2(pca_matrix_base[1, 0], pca_matrix_base[0, 0])
                )

                for angle_deg in angles_to_try:
                    theta   = math.radians(angle_deg)
                    cos_t, sin_t = math.cos(theta), math.sin(theta)
                    perturb = np.array([[cos_t, -sin_t], [sin_t, cos_t]],
                                       dtype=np.float32)
                    final_rot = pca_matrix_base @ perturb

                    # align_minutiae from m04_feature_normalization:
                    #   aligned = (P - core) @ U   (same as encoder)
                    aligned_pts = align_minutiae(unaligned_pts, probe_core, final_rot)

                    # Scale-normalize using enrolled ridge frequency
                    scaled_pts, _ = normalize_scale(
                        aligned_pts,
                        ridge_mask=enhanced_uint8,
                        enrolled_ridge_freq=enrolled_freq
                    )

                    # Quantize with same fixed window as enrollment
                    quant_probe, _, _ = quantize_to_8bit(scaled_pts)

                    # Align angles: subtract net rotation
                    total_angle = pa_deg + angle_deg
                    aligned_angles = (unaligned_angles - total_angle) % 360
                    probe_with_angles = list(zip(quant_probe, aligned_angles))

                    # ------------------------------------------------------
                    # 6. Attempt vault decode
                    # ------------------------------------------------------
                    result = _try_decoding(
                        enrollment_data, probe_with_angles, secret_hash,
                        config.VAULT_MATCHING_RADIUS, quiet
                    )

                    if result[0]:          # is_genuine
                        return result
                    # Keep track of best (highest matched_points) rejection
                    if result[2]["matched_points"] > best_result[2]["matched_points"]:
                        best_result = result

        return best_result

    except Exception as exc:
        if not quiet:
            import traceback
            print(f"[Decoder Error] {exc}\n{traceback.format_exc()}")
        return (False, None, _make_stats(f"ERROR: {exc}"))


def _try_decoding(enrollment_data, probe_with_angles, secret_hash,
                  vault_matching_radius, quiet):
    """
    Attempt to reconstruct the polynomial from vault + probe matches.

    Returns 3-tuple  (is_genuine, None, stats_dict).
    """
    vault_points = enrollment_data.get("vault_points", [])
    if not vault_points:
        vault_points = enrollment_data.get("vault", [])

    # Build lookup: u_i -> list of (v_i, P(v_i))
    vault_u_map = {}
    for entry in vault_points:
        u_i, v_i, p_vi = int(entry[0]), int(entry[1]), entry[2]
        vault_u_map.setdefault(u_i, []).append((v_i, p_vi))

    # ------------------------------------------------------------------
    # Fuzzy spatial match in 6-bit grid (same format as encoder)
    # v_i = (x_6b << 10) | (y_6b << 4) | theta_bucket
    # u_i = x_6b ^ y_6b
    #
    # Sort key = d2 * 10 + |dt| + flip_penalty
    # Genuine hits typically: d2=0, dt=0, no flip  → key=0  (best)
    # Chaff/uncertain hits:   d2>0 or |dt|>0 or flip → higher keys
    # This pushes most-confident hits to the front so the first
    # Lagrange combination tried is likely the correct one.
    # ------------------------------------------------------------------
    grid_radius = 2   # ±2 6-bit cells = ±16 image pixels tolerance

    # found_points: (v_i, p_vi, sort_key)
    found_points = []

    for (px, py), p_ang in probe_with_angles:
        px_6b     = int(px) >> 2
        py_6b     = int(py) >> 2
        pt_bucket = int(p_ang / 22.5) % 16

        best_match  = None
        best_key    = float('inf')

        for dx in range(-grid_radius, grid_radius + 1):
            for dy in range(-grid_radius, grid_radius + 1):
                nx = px_6b + dx
                ny = py_6b + dy
                if not (0 <= nx < 64 and 0 <= ny < 64):
                    continue

                u_cand = nx ^ ny
                if u_cand not in vault_u_map:
                    continue

                d2 = dx * dx + dy * dy

                # Allow ±1 angle bucket AND per-point 180° flip.
                # Ridge direction has inherent 180° ambiguity; the outer
                # loop handles global PCA flip, this handles per-minutia
                # ambiguity. Flip is penalised in the sort key so genuine
                # non-flip matches still rank above flip matches.
                for base_t in [pt_bucket, (pt_bucket + 8) % 16]:
                    flip_penalty = 0 if base_t == pt_bucket else 9
                    for dt in [-1, 0, 1]:
                        nt     = (base_t + dt) % 16
                        v_cand = (nx << 10) | (ny << 4) | nt
                        sort_key = d2 * 10 + abs(dt) + flip_penalty

                        if sort_key >= best_key:
                            continue

                        for v_enroll, p_vi in vault_u_map[u_cand]:
                            if v_enroll == v_cand:
                                best_key   = sort_key
                                best_match = (v_cand, p_vi, sort_key)
                                break   # v_i values are unique in vault_u_map

        if best_match:
            found_points.append(best_match)

    # Deduplicate: keep the match with the best (lowest) sort_key per vault entry
    unique = {}
    for v_c, p_vi, sk in found_points:
        if v_c not in unique or sk < unique[v_c][1]:
            unique[v_c] = (p_vi, sk)

    hits = [(v_c, vals[0]) for v_c, vals in unique.items()]
    n_hits = len(hits)

    p = config.POLYNOMIAL_DEGREE
    k = p + 1   # minimum points for Lagrange (degree+1)

    if n_hits < k:
        return (False, None, _make_stats(f"REJECT (Hits={n_hits})", n_hits, 0, "FAIL", "FAIL"))

    # Sort by confidence (lowest sort_key = most likely genuine)
    # This ensures the valid 9-point combination (all genuine) is tried early.
    hits_sorted = sorted(
        [(v_c, pv, unique[v_c][1]) for v_c, pv in hits],
        key=lambda t: t[2]
    )
    top_candidates = [(t[0], t[1]) for t in hits_sorted[:config.MAX_LAGRANGE_CANDIDATES]]

    from itertools import combinations
    combos_tried = 0
    rs_check_failed = False
    hash_check_failed = False

    for combo in combinations(top_candidates, k):
        combos_tried += 1
        if combos_tried > config.MAX_LAGRANGE_COMBINATIONS_TO_TRY:
            break

        xs = [pt[0] for pt in combo]
        ys = [pt[1] for pt in combo]

        poly_coeffs = lagrange_interpolate_coefficients(
            [(x, y) for x, y in zip(xs, ys)], p
        )
        if poly_coeffs is None:
            continue

        try:
            raw_symbols = rs_decode(poly_coeffs, silent=True)
            if raw_symbols is None:
                rs_check_failed = True
                continue

            # RS decode succeeded
            rs_check_status = "PASS"

            secret_candidate = b"".join(
                [int(s).to_bytes(2, 'big') for s in raw_symbols]
            )
            candidate_hash = hashlib.sha256(secret_candidate).hexdigest()

            if candidate_hash == secret_hash:
                return (True, None, _make_stats("GENUINE", n_hits, combos_tried, rs_check_status, "PASS"))
            else:
                hash_check_failed = True

        except Exception:
            continue

    # Determine which check failed last for rejection reason
    if rs_check_failed and not hash_check_failed:
        return (False, None, _make_stats("REJECT (Decode Fail)", n_hits, combos_tried, "FAIL", "FAIL"))
    elif hash_check_failed:
        return (False, None, _make_stats("REJECT (Hash Mismatch)", n_hits, combos_tried, "PASS", "FAIL"))
    else:
        return (False, None, _make_stats("REJECT (Decode Fail)", n_hits, combos_tried, "FAIL", "FAIL"))
