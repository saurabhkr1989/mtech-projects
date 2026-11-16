"""
m13_visualizer.py - Visualization and Plotting Module

This module generates all visualization outputs for the Chaff-Free Fuzzy Vault
system evaluation. The outputs are designed to provide clear insight into:
  1. The preprocessing pipeline (what happens to fingerprints)
  2. System performance across databases (accuracy metrics)
  3. Summary results (GAR, FAR, EER in tabular form)

Visualization Outputs
=====================

A. PIPELINE STEP VISUALIZATION (4-Panel Diagram)
Purpose: Show the complete preprocessing pipeline on one sample fingerprint.

  Panel 1: Original Grayscale Image
  - Raw fingerprint as captured by scanner
  - Shows natural ridge patterns and noise/artifacts

  Panel 2: Thinned Ridge Skeleton
  - Result of Gabor enhancement + Zhang-Suen thinning
  - Ridge patterns reduced to 1-pixel-wide white lines
  - Ridge endings and bifurcations now visible as endpoints/junctions

  Panel 3: PCA-Aligned Minutiae
  - Red X markers: Cleaned minutiae after spurious removal
  - Yellow circle: Singular point (reference for alignment)
  - Overlaid on skeleton to show that minutiae are at ridge features
  - Demonstrates alignment invariance to rotation

  Panel 4: Quantized 8-Bit Grid
  - Hot colormap showing vault point distribution
  - X,Y axes in [0,255] quantized coordinate space
  - Visualization of minutiae after quantization (vault input)
  - Shows density and clustering of vault points

  Purpose: Helps readers understand what happens "under the hood" during
           fingerprint processing. Included in project report.

B. PER-DATABASE ROC CURVE
Purpose: Show system performance for one database.

  X-axis: FAR (False Acceptance Rate) in %
  Y-axis: GAR (Genuine Acceptance Rate) in %

  Plot Elements:
  - Diagonal dashed line: FAR = FRR line (Equal Error Rate reference)
  - Red dot: Operating point (GAR, FAR) for this database
  - Annotation: EER value at that operating point

  Generated for each of the 3 databases (FVC2002_DB1, FVC2002_DB2, FVC2004_DB1)

  Note: Since fuzzy vault is binary (vault opens or not), the plot is a single
        point, not a curve. The "ROC" terminology is conventional.

C. COMBINED ROC CURVE (All 3 Databases)
Purpose: Compare system performance across databases on one figure.

  Similar to per-database ROC but shows all 3 operating points:
  - FVC2002_DB1: Blue dot
  - FVC2002_DB2: Orange dot
  - FVC2004_DB1: Green dot

  Helps identify if performance varies across datasets (e.g., quality differences)

D. RESULTS TABLE IMAGE
Purpose: Tabular summary of accuracy metrics (for report inclusion).

  Columns: Database | p (degree) | GAR (%) | FAR (%) | FRR (%) | EER (%)
  Rows: One per database

  Professional formatting:
  - Dark blue header row
  - Alternating white/light blue data rows
  - All values to appropriate precision

  Useful for: Direct inclusion in research reports (matplotlib table rendering)

Export Formats
==============
All visualizations are saved as PNG images:
  - Pipeline steps: outputs/step_visuals/pipeline_<filename>.png
  - Per-DB ROC: outputs/plots/roc_FVC2002_DB1_p8.png (etc)
  - Combined ROC: outputs/plots/roc_combined_p8.png
  - Results table: outputs/plots/results_table_p8.png
"""

import os
import sys

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.utilities import config
from modules.utilities.logger import log_step, log_success, log_data
from modules.m01_image_preprocessing import (
    _load_as_grayscale,
    _segment_by_block_variance,
    enhance_and_binarize,
    thin_ridges_to_skeleton,
)
from modules.m03_minutiae_processor  import extract_minutiae
from modules.m04_feature_normalization import (
    align_minutiae,
    quantize_to_8bit,
)
from modules.m04_improved_singularity_point import (
    estimate_orientation_map,
    build_foreground_mask,
    detect_singular_point,
    compute_pca_matrix
)


# ---------------------------------------------------------------------------
# A. Pipeline step visualization
# ---------------------------------------------------------------------------

def visualize_pipeline_steps(
    image_path: str,
    save_path: str,
) -> None:
    """
    Run the preprocessing pipeline on one fingerprint and save a 3-panel figure.

    Panels:
        1. Original grayscale image
        2. PCA-aligned minutiae overlaid on skeleton
        3. Quantized 8-bit grid locations (enlarged dots for visibility)

    Parameters
    ----------
    image_path : Path to a fingerprint image (.tif or .bmp).
    save_path  : Destination .png file path.
    """
    log_step(f"Generating pipeline visualization for: {os.path.basename(image_path)}")

    import cv2

    # --- Run pipeline ---
    original_gray    = _load_as_grayscale(image_path)
    h, w = original_gray.shape

    # Segment foreground — same parameters as enrollment pipeline
    foreground_mask = _segment_by_block_variance(original_gray, top_margin_px=20, bottom_margin_px=20)

    binary_image     = enhance_and_binarize(image_path)

    # Apply foreground mask before thinning (same as enrollment/verification)
    # so the skeleton does not extend into scanner-edge noise regions.
    import numpy as np
    binary_uint8 = (binary_image * 255).astype(np.uint8)
    if binary_uint8.shape != original_gray.shape:
        padded = np.zeros(original_gray.shape, dtype=np.uint8)
        eh, ew = binary_uint8.shape[:2]
        padded[:eh, :ew] = binary_uint8
        binary_uint8 = padded
    binary_uint8[~foreground_mask] = 0
    thinned_skeleton = thin_ridges_to_skeleton(binary_uint8)

    # Detect singular point (core) via orientation coherence
    orient_map = estimate_orientation_map(original_gray)
    fp_mask = build_foreground_mask(binary_uint8)
    singular_point = detect_singular_point(orient_map, fp_mask)

    # Extract minutiae with integrated filtering — same parameters as enrollment/verification
    minutiae_points = extract_minutiae(
        skeleton=thinned_skeleton,
        roi_mask=foreground_mask,
        core_point=singular_point,
        edge_margin_px=20,
        cluster_distance_px=10,
        keep_range=(8, 200)
    )

    # Convert to (x, y) tuples for alignment
    cleaned_minutiae = [(m.x, m.y) for m in minutiae_points]

    # Core-anchored PCA — same as enrollment/verification
    pca_rotation_matrix_U = compute_pca_matrix(thinned_skeleton)
    aligned_minutiae      = align_minutiae(cleaned_minutiae, singular_point, pca_rotation_matrix_U)
    quantized_minutiae, coord_min, coord_max = quantize_to_8bit(aligned_minutiae)

    # --- Build 3-panel figure (Thinned Skeleton removed as redundant with PCA panel) ---
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(
        f"Fingerprint Pipeline -- {os.path.basename(image_path)}",
        fontsize=14, fontweight="bold",
    )

    # Panel 1: Original grayscale
    axes[0].imshow(original_gray, cmap="gray")
    axes[0].set_title("1. Original Image", fontweight="bold")
    axes[0].axis("off")

    # Panel 2: Cleaned & Aligned minutiae overlaid on skeleton
    skeleton_uint8 = (thinned_skeleton.astype(np.uint8) * 255)
    axes[1].imshow(skeleton_uint8, cmap="gray")
    if len(aligned_minutiae) > 0:
        # Transform aligned minutiae back to image space for visualization
        # Reverse PCA: m_original = m_aligned @ U^T + singular_point
        sx, sy = singular_point
        pca_matrix_inv = pca_rotation_matrix_U.T  # For orthogonal matrix, transpose = inverse
        minutiae_in_image_space = aligned_minutiae @ pca_matrix_inv
        minutiae_in_image_space[:, 0] += sx  # Add singular point offset
        minutiae_in_image_space[:, 1] += sy

        axes[1].scatter(
            minutiae_in_image_space[:, 0],
            minutiae_in_image_space[:, 1],
            c="red", s=20, marker="x", linewidths=1.5,
            label=f"{len(aligned_minutiae)} genuine minutiae (filtered)",
        )
        axes[1].scatter([sx], [sy], c="yellow", s=60, marker="o", label="Singular point")
        axes[1].legend(fontsize=7, loc="lower right")
    axes[1].set_title("2. Cleaned & PCA-Aligned Minutiae", fontweight="bold")
    axes[1].axis("off")

    # Panel 3: Quantized 8-bit grid locations with ENLARGED dots for visibility
    grid_image = np.zeros((256, 256, 3), dtype=np.uint8)  # RGB for colored dots
    for (qx, qy) in quantized_minutiae:
        qx, qy = int(qx), int(qy)
        if 0 <= qx < 256 and 0 <= qy < 256:
            # Draw a circle with radius 3 pixels around each quantized point
            # This makes the dots much more visible than single pixels
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    nx, ny = qx + dx, qy + dy
                    if 0 <= nx < 256 and 0 <= ny < 256 and dx*dx + dy*dy <= 9:
                        grid_image[ny, nx] = [0, 255, 0]  # Green dots

    axes[2].imshow(grid_image)
    axes[2].set_title(
        f"3. Quantized Grid [{len(quantized_minutiae)} pts]",
        fontweight="bold",
    )
    axes[2].set_xlabel("x (8-bit)")
    axes[2].set_ylabel("y (8-bit)")

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    log_success(f"Pipeline visualization saved: {save_path}")


# ---------------------------------------------------------------------------
# B. Per-database ROC curve
# ---------------------------------------------------------------------------

def plot_roc_curve(
    database_name: str,
    gar_pct: float,
    far_pct: float,
    eer_pct: float,
    save_path: str,
) -> None:
    """
    Plot the ROC curve (GAR vs FAR) for one database.

    Because this is a binary cryptosystem with a single operating point,
    the ROC 'curve' is a single point.  We mark the EER diagonal and
    annotate the operating point.

    Parameters
    ----------
    database_name : Label for the plot title.
    gar_pct       : Genuine Acceptance Rate in [0, 100].
    far_pct       : False Acceptance Rate in [0, 100].
    eer_pct       : Equal Error Rate in [0, 100].
    save_path     : Destination .png file path.
    """
    log_step(f"Plotting ROC curve for {database_name}")

    fig, ax = plt.subplots(figsize=(7, 6))

    # EER diagonal: GAR = 1 - FAR  (i.e., FRR = FAR)
    diagonal_far_values = np.linspace(0, 100, 200)
    diagonal_gar_values = 100 - diagonal_far_values
    ax.plot(
        diagonal_far_values, diagonal_gar_values,
        color="gray", linestyle="--", linewidth=1, label="EER line (FRR = FAR)",
    )

    # Operating point
    ax.scatter(
        [far_pct], [gar_pct],
        color="red", s=120, zorder=5,
        label=f"Operating point\nGAR={gar_pct:.2f}%  FAR={far_pct:.2f}%",
    )

    # Annotate EER
    ax.annotate(
        f"EER ~= {eer_pct:.3f}%",
        xy=(far_pct, gar_pct),
        xytext=(far_pct + 5, gar_pct - 8),
        fontsize=9, color="darkred",
        arrowprops=dict(arrowstyle="->", color="darkred"),
    )

    ax.set_xlabel("FAR -- False Acceptance Rate (%)", fontsize=11)
    ax.set_ylabel("GAR -- Genuine Acceptance Rate (%)", fontsize=11)
    ax.set_title(f"ROC Curve -- {database_name}  (p=8)", fontsize=13, fontweight="bold")
    ax.set_xlim(0, 105)
    ax.set_ylim(0, 105)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    log_success(f"ROC curve saved: {save_path}")


# ---------------------------------------------------------------------------
# C. Combined ROC curve (all 3 databases)
# ---------------------------------------------------------------------------

def plot_combined_roc(
    all_results: dict,
    save_path: str,
) -> None:
    """
    Plot all three database operating points on one ROC figure.

    Parameters
    ----------
    all_results : Dict returned by m12_evaluator.run_full_evaluation().
    save_path   : Destination .png file path.
    """
    log_step("Plotting combined ROC curve (all databases)")

    _color_palette = ["royalblue", "darkorange", "forestgreen", "crimson", "purple"]

    fig, ax = plt.subplots(figsize=(8, 7))

    # EER diagonal
    diagonal_far_values = np.linspace(0, 100, 200)
    diagonal_gar_values = 100 - diagonal_far_values
    ax.plot(
        diagonal_far_values, diagonal_gar_values,
        color="gray", linestyle="--", linewidth=1, label="EER line (FRR = FAR)",
    )

    for db_idx, (database_name, metrics) in enumerate(all_results.items()):
        gar_pct = metrics["gar_pct"]
        far_pct = metrics["far_pct"]
        eer_pct = metrics["eer_pct"]
        point_color = _color_palette[db_idx % len(_color_palette)]

        ax.scatter(
            [far_pct], [gar_pct],
            color=point_color, s=140, zorder=5,
            label=f"{database_name}  (GAR={gar_pct:.2f}%, FAR={far_pct:.2f}%, EER={eer_pct:.3f}%)",
        )

    ax.set_xlabel("FAR -- False Acceptance Rate (%)", fontsize=11)
    ax.set_ylabel("GAR -- Genuine Acceptance Rate (%)", fontsize=11)
    ax.set_title("Combined ROC -- All Databases  (p=8)", fontsize=13, fontweight="bold")
    ax.set_xlim(0, 105)
    ax.set_ylim(0, 105)
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    log_success(f"Combined ROC saved: {save_path}")


# ---------------------------------------------------------------------------
# D. Results table image
# ---------------------------------------------------------------------------

def save_results_table_image(
    all_results: dict,
    polynomial_degree: int,
    save_path: str,
) -> None:
    """
    Render the accuracy results as a matplotlib table figure and save as PNG.
    Suitable for direct inclusion in the project report.

    Parameters
    ----------
    all_results       : Dict returned by m12_evaluator.run_full_evaluation().
    polynomial_degree : Polynomial degree used (shown in table header).
    save_path         : Destination .png file path.
    """
    log_step("Generating results table image")

    column_labels = ["Database", "p", "GAR (%)", "FAR (%)", "FRR (%)", "EER (%)"]
    table_data = []

    for database_name, metrics in all_results.items():
        table_data.append([
            database_name,
            str(polynomial_degree),
            f"{metrics['gar_pct']:.2f}",
            f"{metrics['far_pct']:.2f}",
            f"{metrics['frr_pct']:.2f}",
            f"{metrics['eer_pct']:.4f}",
        ])

    fig, ax = plt.subplots(figsize=(11, 2.5))
    ax.axis("off")

    rendered_table = ax.table(
        cellText=table_data,
        colLabels=column_labels,
        cellLoc="center",
        loc="center",
    )
    rendered_table.auto_set_font_size(False)
    rendered_table.set_fontsize(11)
    rendered_table.scale(1.2, 2.0)

    # Style the header row
    for col_idx in range(len(column_labels)):
        header_cell = rendered_table[(0, col_idx)]
        header_cell.set_facecolor("#2c5f8a")
        header_cell.set_text_props(color="white", fontweight="bold")

    # Alternating row colors
    for row_idx in range(1, len(table_data) + 1):
        row_color = "#e8f4fd" if row_idx % 2 == 0 else "#ffffff"
        for col_idx in range(len(column_labels)):
            rendered_table[(row_idx, col_idx)].set_facecolor(row_color)

    ax.set_title(
        f"Chaff-Free Fuzzy Vault -- Evaluation Results (p = {polynomial_degree})",
        fontsize=12, fontweight="bold", pad=20,
    )

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    log_success(f"Results table image saved: {save_path}")


# ---------------------------------------------------------------------------
# Convenience: generate all visualization outputs from one call
# ---------------------------------------------------------------------------

def generate_all_visualizations(
    enrollment_images_with_db: list,
    all_results: dict,
    polynomial_degree: int = config.POLYNOMIAL_DEGREE,
) -> None:
    """
    Generate every required visualization output in one call.

    Parameters
    ----------
    enrollment_images_with_db : List of tuples (image_path, database_name) for pipeline visualizations.
    all_results               : Dict from m12_evaluator.run_full_evaluation().
    polynomial_degree         : Polynomial degree used.
    """
    # A. Pipeline steps for all enrollment images
    for image_path, database_name in enrollment_images_with_db:
        if os.path.exists(image_path):
            image_basename = os.path.splitext(os.path.basename(image_path))[0]
            pipeline_vis_path = os.path.join(
                config.STEP_VISUALS_OUTPUT_DIR,
                f"{database_name}_pipeline_{image_basename}.png",
            )
            visualize_pipeline_steps(image_path, pipeline_vis_path)

    # B. Per-database ROC
    for database_name, metrics in all_results.items():
        roc_path = os.path.join(
            config.PLOTS_OUTPUT_DIR,
            f"roc_{database_name}_p{polynomial_degree}.png",
        )
        plot_roc_curve(
            database_name=database_name,
            gar_pct=metrics["gar_pct"],
            far_pct=metrics["far_pct"],
            eer_pct=metrics["eer_pct"],
            save_path=roc_path,
        )

    # C. Combined ROC
    combined_roc_path = os.path.join(
        config.PLOTS_OUTPUT_DIR,
        f"roc_combined_p{polynomial_degree}.png",
    )
    plot_combined_roc(all_results, combined_roc_path)

    # D. Results table image
    table_image_path = os.path.join(
        config.PLOTS_OUTPUT_DIR,
        f"results_table_p{polynomial_degree}.png",
    )
    save_results_table_image(all_results, polynomial_degree, table_image_path)
