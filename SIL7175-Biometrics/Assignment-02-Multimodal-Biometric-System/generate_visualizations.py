"""
generate_visualizations.py
--------------------------
Generates all process-demonstration figures for the report.
Figures are saved to visualizations/ directory.

Usage:
    python generate_visualizations.py

Outputs (in visualizations/):
    fig1_face_roi_samples.png     - 15 landmark-centered 30x30 ROI patches
    fig2_iris_normalized_strip.png - Rubber-sheet + 10 overlapping strip breakdown
    fig3_signature_pipeline.png   - Raw -> Binarized -> Centered signature
    fig4_roc_aggregated.png       - Copies of results/ aggregated ROC curves (no recompute)
    fig5_modality_eer_bar.png     - Bar chart of per-modality EER across datasets
"""

import os
import sys
import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

# Add project root to sys.path so src imports work
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.config import Config
Config.setup_directories()
VISUALS_DIR = Config.VISUALS_DIR

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _first_file(directory, extensions=(".jpg", ".jpeg", ".png", ".bmp", ".tif")):
    """Return the first found file in `directory` matching `extensions`."""
    for root, dirs, files in os.walk(directory):
        dirs.sort()
        for fname in sorted(files):
            if fname.lower().endswith(extensions):
                return os.path.join(root, fname)
    return None


def _style_ax(ax, title="", xlabel="", ylabel=""):
    ax.set_title(title, fontsize=9, fontweight="bold", pad=4)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=7)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=7)
    ax.tick_params(labelsize=6)


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1 — Face ROI Samples (15 landmark-centered 30×30 patches)
# ─────────────────────────────────────────────────────────────────────────────

def fig1_face_roi_samples():
    """
    Shows:
      Left  : original face image with 15 landmark points and ROI boxes overlaid
      Right : the 15 individual 30×30 ROIs after Histogram Equalization, arranged 3×5
    """
    try:
        import dlib
    except ImportError:
        print("[fig1] dlib not importable – skipping fig1.")
        return

    predictor_path = os.path.join(BASE_DIR, "resources", "shape_predictor_68_face_landmarks.dat")
    if not os.path.exists(predictor_path):
        print("[fig1] shape_predictor_68_face_landmarks.dat not found – skipping fig1.")
        return

    # Try LFW (RGB, easiest for dlib HOG)
    lfw_file = _first_file(Config.LFW_DIR)
    if lfw_file is None:
        print("[fig1] No LFW image found – skipping fig1.")
        return

    detector  = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(predictor_path)

    img_bgr  = cv2.imread(lfw_file)
    gray     = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    img_rgb  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    faces = detector(gray, 1)
    if len(faces) == 0:
        print("[fig1] No face detected in chosen LFW image – skipping fig1.")
        return

    face_rect = faces[0]
    shape     = predictor(gray, face_rect)

    key_indices = [36, 39, 42, 45, 27, 30, 31, 35, 48, 51, 54, 57, 0, 8, 16]
    half = Config.FACE_ROI_SIZE // 2
    h, w = gray.shape[:2]

    rois_eq   = []
    overlay   = img_rgb.copy()
    landmarks = []

    for idx in key_indices:
        pt      = shape.part(idx)
        x, y    = pt.x, pt.y
        landmarks.append((x, y))

        x1 = max(0, x - half)
        y1 = max(0, y - half)
        x2 = min(w,  x + half)
        y2 = min(h,  y + half)

        crop = gray[y1:y2, x1:x2]
        if crop.size == 0:
            crop = np.zeros((Config.FACE_ROI_SIZE, Config.FACE_ROI_SIZE), dtype=np.uint8)
        crop = cv2.resize(crop, (Config.FACE_ROI_SIZE, Config.FACE_ROI_SIZE))
        eq   = cv2.equalizeHist(crop)
        rois_eq.append(eq)

        # Draw box on overlay
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 80, 80), 1)

    # Draw landmark dots
    for (x, y) in landmarks:
        cv2.circle(overlay, (x, y), 2, (255, 220, 0), -1)

    # ── Layout ──────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(12, 5))
    fig.patch.set_facecolor("#1a1a2e")

    gs = gridspec.GridSpec(3, 7, figure=fig, wspace=0.06, hspace=0.12,
                           left=0.02, right=0.98, top=0.88, bottom=0.05)

    # Face with overlay (spans 3 rows × 2 cols)
    ax_face = fig.add_subplot(gs[:, :2])
    ax_face.imshow(overlay)
    ax_face.axis("off")
    ax_face.set_title("Face with 15 Landmark\nROI Boxes Overlaid", color="white",
                       fontsize=9, fontweight="bold")

    # 15 ROI patches in 3 rows × 5 cols
    landmark_labels = [
        "L-Eye L", "L-Eye R", "R-Eye L", "R-Eye R", "Nose Bridge",
        "Nose Tip", "Nose L", "Nose R", "Mouth L", "Mouth Top",
        "Mouth R", "Mouth Bot", "Jaw L", "Jaw Centre", "Jaw R"
    ]
    for i, roi in enumerate(rois_eq):
        row = i // 5
        col = 2 + (i % 5)
        ax = fig.add_subplot(gs[row, col])
        ax.imshow(roi, cmap="gray", vmin=0, vmax=255)
        ax.axis("off")
        ax.set_title(landmark_labels[i], color="#aaaaee", fontsize=6, pad=2)

    fig.suptitle("Figure 1 — Face ROI Samples: 15 Landmark-Centered 30×30 Patches"
                 "\nafter Histogram Equalization",
                 color="white", fontsize=11, fontweight="bold", y=0.97)

    out = os.path.join(VISUALS_DIR, "fig1_face_roi_samples.png")
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[fig1] Saved → {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2 — Normalized Iris Strips
# ─────────────────────────────────────────────────────────────────────────────

def fig2_iris_strips():
    """
    Shows:
      Top    : original iris image with pupil and sclera circles drawn
      Middle : the 512×64 rubber-sheet (full unrolled band)
      Bottom : all 10 overlapping 32×512 strips stacked with stride labels
    """
    from src.preprocessing.iris_preprocessor import IrisPreprocessor

    iitd_file = _first_file(Config.IITD_DIR, (".bmp", ".png", ".jpg"))
    if iitd_file is None:
        print("[fig2] No IITD iris image found – skipping fig2.")
        return

    proc  = IrisPreprocessor()
    img   = cv2.imread(iitd_file, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("[fig2] Could not load IITD image – skipping fig2.")
        return

    try:
        pupil, iris_b = proc.find_pupil_and_iris(img)
    except ValueError as e:
        print(f"[fig2] Segmentation failed: {e} – skipping fig2.")
        return

    normalized = proc.daugman_rubber_sheet(img, pupil, iris_b)

    # Build 10 strips
    strips = []
    start_y = 0
    for i in range(Config.NUM_IRIS_STRIPS):
        y1 = start_y
        y2 = start_y + Config.IRIS_STRIP_H
        if y2 > Config.IRIS_NORM_H:
            y2 = Config.IRIS_NORM_H
            y1 = y2 - Config.IRIS_STRIP_H
        strip = normalized[y1:y2, :]
        eq, _ = proc.enhance_strip(strip)
        strips.append((eq, y1, y2))
        start_y += Config.IRIS_STRIP_STRIDE

    # Overlay circles on a copy of the original
    overlay_img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    px, py, pr = pupil
    ix, iy, ir = iris_b
    cv2.circle(overlay_img, (px, py), pr, (80, 200, 255), 2)   # pupil  – cyan
    cv2.circle(overlay_img, (ix, iy), ir, (255, 160, 60), 2)   # sclera – amber

    # ── Layout ──────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(14, 10))
    fig.patch.set_facecolor("#1a1a2e")

    outer_gs = gridspec.GridSpec(3, 1, figure=fig,
                                 height_ratios=[2.8, 1.6, 5],
                                 hspace=0.40,
                                 left=0.06, right=0.98,
                                 top=0.91, bottom=0.04)

    # ── Row 1: original with circles ────────────────────────────────────────
    ax_orig = fig.add_subplot(outer_gs[0])
    ax_orig.imshow(overlay_img)
    ax_orig.axis("off")
    ax_orig.set_title(
        "Original Iris Image — Pupil (cyan) & Sclera (amber) boundaries detected via\n"
        "adaptive Hough Circle Transform",
        color="white", fontsize=9, fontweight="bold")

    # ── Row 2: full rubber-sheet ─────────────────────────────────────────────
    ax_rs = fig.add_subplot(outer_gs[1])
    ax_rs.imshow(normalized, cmap="gray", aspect="auto")
    ax_rs.set_title("Daugman Rubber-Sheet — Full 512×64 px Unrolled Iris Band",
                    color="white", fontsize=9, fontweight="bold")
    ax_rs.set_xlabel("θ  (0 → 2π)", color="#aaaaee", fontsize=7)
    ax_rs.set_ylabel("r  (pupil→sclera)", color="#aaaaee", fontsize=7)
    ax_rs.tick_params(colors="#888888", labelsize=6)
    for spine in ax_rs.spines.values():
        spine.set_edgecolor("#444466")

    # ── Row 3: 10 strips ─────────────────────────────────────────────────────
    inner_gs = gridspec.GridSpecFromSubplotSpec(
        10, 2, subplot_spec=outer_gs[2],
        width_ratios=[18, 1], wspace=0.02, hspace=0.05)

    for i, (strip_eq, y1, y2) in enumerate(strips):
        ax_s  = fig.add_subplot(inner_gs[i, 0])
        ax_s.imshow(strip_eq, cmap="gray", aspect="auto", vmin=0, vmax=255)
        ax_s.set_xticks([])
        ax_s.set_yticks([])
        for spine in ax_s.spines.values():
            spine.set_edgecolor("#334466")

        ax_lbl = fig.add_subplot(inner_gs[i, 1])
        ax_lbl.axis("off")
        ax_lbl.text(0.1, 0.5,
                    f"S{i+1:02d}\ny={y1}–{y2}",
                    color="#99ccff", fontsize=5.5, va="center", ha="left")

    # Row 3 super-title
    sub_ax = fig.add_subplot(outer_gs[2])
    sub_ax.axis("off")
    sub_ax.set_title(
        "10 Overlapping 32×512 px Horizontal Strips  (4-pixel stride, after Histogram Equalization)",
        color="white", fontsize=9, fontweight="bold", pad=8, loc="left", x=0.0)

    fig.suptitle("Figure 2 — Iris Preprocessing Pipeline: Rubber-Sheet Normalization & Strip Decomposition",
                 color="white", fontsize=11, fontweight="bold", y=0.98)

    out = os.path.join(VISUALS_DIR, "fig2_iris_normalized_strip.png")
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[fig2] Saved → {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3 — Binarized and Centered Signature
# ─────────────────────────────────────────────────────────────────────────────

def fig3_signature_pipeline():
    """
    Shows the 3-stage pipeline:
      Stage A : Raw grayscale scan
      Stage B : After Otsu binarization & inversion (ink=white, bg=black)
      Stage C : After CoM centering & resize to 170×242
    """
    from src.preprocessing.signature_preprocessor import SignaturePreprocessor
    from PIL import Image

    sig_file = _first_file(Config.BHSIG_BENGALI_DIR, (".tif", ".png", ".jpg", ".bmp"))
    if sig_file is None:
        print("[fig3] No BHSig Bengali signature found – skipping fig3.")
        return

    # ── Raw image ────────────────────────────────────────────────────────────
    try:
        pil_img = Image.open(sig_file).convert("L")
        raw_arr = np.array(pil_img, dtype=np.uint8)
    except Exception as e:
        print(f"[fig3] Load error: {e} – skipping fig3.")
        return

    # ── Otsu binarization + inversion ───────────────────────────────────────
    _, binary = cv2.threshold(raw_arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inverted  = cv2.bitwise_not(binary)

    # ── Center of Mass alignment + resize ───────────────────────────────────
    ink_map = (inverted > 0).astype(np.uint8)
    M = cv2.moments(ink_map)
    if M["m00"] != 0:
        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])
    else:
        cX, cY = ink_map.shape[1] // 2, ink_map.shape[0] // 2

    shift_x = ink_map.shape[1] // 2 - cX
    shift_y = ink_map.shape[0] // 2 - cY
    T = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
    centered = cv2.warpAffine(ink_map, T, (ink_map.shape[1], ink_map.shape[0]))
    resized  = cv2.resize(
        centered,
        (Config.SIG_RESIZE_W, Config.SIG_RESIZE_H),
        interpolation=cv2.INTER_NEAREST
    )

    # ── Annotate CoM on inverted ─────────────────────────────────────────────
    inv_rgb    = cv2.cvtColor(inverted, cv2.COLOR_GRAY2RGB)
    com_radius = max(8, min(inv_rgb.shape[:2]) // 30)
    cv2.circle(inv_rgb, (cX, cY), com_radius, (255, 80, 80), 2)
    cv2.drawMarker(inv_rgb, (cX, cY), (255, 80, 80),
                   markerType=cv2.MARKER_CROSS, markerSize=com_radius * 2, thickness=1)

    arrow_text = (f"CoM = ({cX}, {cY})\n"
                  f"Shift = ({shift_x:+d}, {shift_y:+d})")

    # ── Layout ───────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(13, 5),
                             gridspec_kw={"wspace": 0.14})
    fig.patch.set_facecolor("#1a1a2e")

    panels = [
        (raw_arr,   "gray",   "A — Raw Grayscale Scan\n(original scanner output)"),
        (inv_rgb,   None,     f"B — After Otsu Binarization & Inversion\n{arrow_text}"),
        (resized * 255, "gray", f"C — Centered & Resized\n({Config.SIG_RESIZE_H}×{Config.SIG_RESIZE_W} px, Nearest-Neighbour)"),
    ]

    for ax, (img_data, cmap, title) in zip(axes, panels):
        if cmap:
            ax.imshow(img_data, cmap=cmap, vmin=0, vmax=255)
        else:
            ax.imshow(img_data)
        ax.axis("off")
        ax.set_title(title, color="white", fontsize=8.5, fontweight="bold",
                     pad=6, linespacing=1.45)

        # Dimension annotation
        h_, w_ = (img_data.shape[:2] if isinstance(img_data, np.ndarray)
                  else (img_data.height, img_data.width))
        ax.annotate(
            f"{w_}×{h_} px",
            xy=(0.5, 0.01), xycoords="axes fraction",
            ha="center", va="bottom",
            color="#88aacc", fontsize=7,
            bbox=dict(boxstyle="round,pad=0.2", fc="#1a1a2e", alpha=0.7, ec="none")
        )

        for spine in ax.spines.values():
            spine.set_edgecolor("#334466")

    # Arrows between panels
    for x_pos in [0.345, 0.655]:
        fig.text(x_pos, 0.5, "→", ha="center", va="center",
                 fontsize=22, color="#5588cc", transform=fig.transFigure)

    fig.suptitle("Figure 3 — Offline Signature Preprocessing Pipeline:\n"
                 "Otsu Binarization → Center-of-Mass Alignment → 170×242 px Canvas",
                 color="white", fontsize=11, fontweight="bold", y=1.01)

    out = os.path.join(VISUALS_DIR, "fig3_signature_pipeline.png")
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[fig3] Saved → {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 4 — Copy of Aggregated ROC Curves (no recomputation)
# ─────────────────────────────────────────────────────────────────────────────

def fig4_roc_panel():
    """
    Copies (or re-embeds) the two aggregated ROC PNG files side-by-side.
    Avoids any SVM or model inference.
    """
    import shutil
    from PIL import Image as PILImage

    roc_d1 = os.path.join(Config.RESULTS_DIR, "Dataset_1_aggregated_roc.png")
    roc_d2 = os.path.join(Config.RESULTS_DIR, "Dataset_2_aggregated_roc.png")

    if not os.path.exists(roc_d1) or not os.path.exists(roc_d2):
        print("[fig4] Aggregated ROC PNGs not found in results/ – skipping fig4.")
        return

    img1 = np.array(PILImage.open(roc_d1).convert("RGB"))
    img2 = np.array(PILImage.open(roc_d2).convert("RGB"))

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("#1a1a2e")

    titles = [
        "Dataset 1 — Aggregated 5-Fold ROC\n(CASIA-NIR Face + IITD Iris + BHSig Bengali Sig)",
        "Dataset 2 — Aggregated 5-Fold ROC\n(LFW-RGB Face + IITD Iris + BHSig Hindi Sig)",
    ]
    for ax, img, title in zip(axes, [img1, img2], titles):
        ax.imshow(img)
        ax.axis("off")
        ax.set_title(title, color="white", fontsize=9, fontweight="bold", pad=6)

    fig.suptitle("Figure 4 — Aggregated ROC Curves: All Modalities & Fusion Strategies",
                 color="white", fontsize=11, fontweight="bold", y=0.99)

    out = os.path.join(VISUALS_DIR, "fig4_roc_aggregated.png")
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[fig4] Saved → {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 5 — Modality EER Comparison Bar Chart
# ─────────────────────────────────────────────────────────────────────────────

def fig5_eer_bar():
    """
    Grouped bar chart comparing EER across modalities for Dataset 1 vs Dataset 2.
    Values sourced from the summary CSV (or hardcoded from the report table).
    """
    import csv

    summary_csv = os.path.join(Config.RESULTS_DIR, "summary_accuracy_eer.csv")

    # ── Try to load from CSV ─────────────────────────────────────────────────
    data_d1 = {}
    data_d2 = {}

    if os.path.exists(summary_csv):
        with open(summary_csv, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    dataset = row.get("Dataset", "").strip()
                    modality = row.get("Modality", "").strip()
                    eer = float(row.get("Mean_EER", row.get("EER", 0)))
                    if "1" in dataset:
                        data_d1[modality] = eer
                    elif "2" in dataset:
                        data_d2[modality] = eer
                except (ValueError, KeyError):
                    continue

    # ── Fallback to report-table values if CSV missing or empty ─────────────
    if not data_d1:
        data_d1 = {
            "Face Tex (ULBP)": 0.082,
            "Face Deep (SE-Alex)": 0.079,
            "Sig Deep (WI-Alex)": 0.018,
            "Decision Fusion": 0.159,
            "Feature Fusion": 0.114,
        }
    if not data_d2:
        data_d2 = {
            "Face Tex (ULBP)": 0.173,
            "Face Deep (SE-Alex)": 0.351,
            "Iris Deep (SE-Alex)": 0.264,
            "Sig Deep (WI-Alex)": 0.048,
            "Decision Fusion": 0.273,
        }

    # ── Union of modalities ─────────────────────────────────────────────────
    all_modalities = list(dict.fromkeys(list(data_d1.keys()) + list(data_d2.keys())))
    x = np.arange(len(all_modalities))
    width = 0.36

    fig, ax = plt.subplots(figsize=(13, 5.5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#12122a")

    vals1 = [data_d1.get(m, 0) for m in all_modalities]
    vals2 = [data_d2.get(m, 0) for m in all_modalities]

    bars1 = ax.bar(x - width / 2, vals1, width, label="Dataset 1 (CASIA/Bengali)",
                   color="#4a9eff", alpha=0.85, zorder=3)
    bars2 = ax.bar(x + width / 2, vals2, width, label="Dataset 2 (LFW/Hindi)",
                   color="#ff7b4a", alpha=0.85, zorder=3)

    # Value labels
    for bar in list(bars1) + list(bars2):
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2., h + 0.006,
                    f"{h:.3f}", ha="center", va="bottom",
                    color="white", fontsize=7, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(all_modalities, color="#ccccee", fontsize=8, rotation=12, ha="right")
    ax.set_ylabel("Equal Error Rate (EER) ↓ lower is better", color="#aaaacc", fontsize=9)
    ax.set_ylim(0, max(max(vals1), max(vals2)) * 1.22)
    ax.tick_params(colors="#888888", labelsize=8)
    ax.yaxis.grid(True, color="#2a2a4a", linestyle="--", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_edgecolor("#334466")

    legend = ax.legend(fontsize=9, facecolor="#22224a", edgecolor="#445588",
                       labelcolor="white", framealpha=0.9)

    # Annotate the best modality
    best_idx = int(np.argmin(vals1))
    ax.annotate("★ Best",
                xy=(x[best_idx] - width / 2, vals1[best_idx]),
                xytext=(x[best_idx] - width / 2 + 0.5, vals1[best_idx] + 0.04),
                color="#ffe066", fontsize=8, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="#ffe066", lw=1.2))

    ax.set_title("Figure 5 — Per-Modality EER Comparison: Dataset 1 vs Dataset 2\n"
                 "(Lower EER = Better Verification Performance)",
                 color="white", fontsize=11, fontweight="bold", pad=10)

    out = os.path.join(VISUALS_DIR, "fig5_modality_eer_bar.png")
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[fig5] Saved → {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 6 — Pipeline Block Diagram (no real images needed)
# ─────────────────────────────────────────────────────────────────────────────

def fig6_pipeline_diagram():
    """
    Text-box flow diagram showing the 6-phase pipeline end-to-end.
    Pure matplotlib, no image data required.
    """
    fig, ax = plt.subplots(figsize=(14, 3.8))
    fig.patch.set_facecolor("#0d0d1a")
    ax.set_facecolor("#0d0d1a")
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 4)
    ax.axis("off")

    phases = [
        ("Phase 1\nChimeric\nMapping", "#2255aa", "100 Virtual\nUsers"),
        ("Phase 2\nBiological\nNormalization", "#225588", "Face/Iris/Sig\nPreprocessing"),
        ("Phase 3\nULBP Texture\nExtraction", "#1a6655", "59-bin hist\nper block"),
        ("Phase 3/4\nDeep Feature\nExtraction", "#556611", "4096-dim\nSE/WI-AlexNet"),
        ("Phase 5\nSVM\nVerification", "#884422", "1:3 pos/neg\nRBF kernel"),
        ("Phase 6\nFusion &\nEvaluation", "#662255", "EER · ROC\n5-Fold CV"),
    ]

    box_w = 1.9
    box_h = 2.4
    gap   = 0.44
    y_top = 3.2

    for i, (label, color, sub) in enumerate(phases):
        x0 = 0.25 + i * (box_w + gap)
        rect = mpatches.FancyBboxPatch(
            (x0, y_top - box_h), box_w, box_h,
            boxstyle="round,pad=0.12",
            linewidth=1.5, edgecolor="#aaccff",
            facecolor=color, alpha=0.88, zorder=2
        )
        ax.add_patch(rect)
        ax.text(x0 + box_w / 2, y_top - box_h / 2 + 0.42,
                label, ha="center", va="center",
                color="white", fontsize=8, fontweight="bold",
                zorder=3, linespacing=1.4)
        ax.text(x0 + box_w / 2, y_top - box_h / 2 - 0.55,
                sub, ha="center", va="center",
                color="#ccddff", fontsize=6.5,
                zorder=3, linespacing=1.35)

        if i < len(phases) - 1:
            arr_x = x0 + box_w + 0.04
            arr_y = y_top - box_h / 2
            ax.annotate("", xy=(arr_x + gap - 0.08, arr_y),
                        xytext=(arr_x, arr_y),
                        arrowprops=dict(arrowstyle="-|>", color="#6688cc",
                                        lw=1.5, mutation_scale=14),
                        zorder=1)

    ax.set_title("Figure 6 — End-to-End Pipeline Block Diagram (6-Phase Architecture)",
                 color="white", fontsize=11, fontweight="bold", pad=8)

    out = os.path.join(VISUALS_DIR, "fig6_pipeline_diagram.png")
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[fig6] Saved → {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Biometric Visualization Generator")
    print("=" * 60)

    fig6_pipeline_diagram()   # no external data needed — always runs first
    fig3_signature_pipeline() # lightweight, PIL only
    fig5_eer_bar()            # lightweight, CSV or hardcoded values
    fig4_roc_panel()          # re-embeds existing PNGs
    fig2_iris_strips()        # needs IITD + IrisPreprocessor
    fig1_face_roi_samples()   # needs LFW + dlib + predictor (heaviest)

    print("\nDone. Check the visualizations/ folder.")
