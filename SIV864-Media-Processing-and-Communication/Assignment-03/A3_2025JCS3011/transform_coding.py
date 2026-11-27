"""
transform_coding.py
===================

Assignment 3 - Transform Coding (SIV864, Media Processing and Communication).

What this program does
----------------------
It takes an ID photo and runs it through the first half of a transform
coder, and then back again. The steps follow the assignment sheet in the
same order:

    1. Read the ID photo and turn it into a gray scale image with a
       built-in function.
    2. Pad the image, if needed, and cut it into 8x8 blocks.
    3. Apply the Discrete Fourier Transform (DFT) and the Discrete Cosine
       Transform (DCT) to every block.
    4. Quantise. For each block, keep only 50% (32 of 64) or 25% (16 of 64)
       of the coefficients. All the others are set to zero.
    5. Apply the inverse transform and rebuild the image.
    6. Compare DFT and DCT. For each, show the difference image and compute
       the Mean Square Error (MSE) against the original.

Every phase also writes a picture to the output folder, so you can see
what happened at each step. The pictures are numbered in the order that
they are made.

How the coefficients are chosen
-------------------------------
The lecture (session 5) describes a scheme where "M out of N coefficients
are retained" in every block, which fixes the compression rate. This
program uses that scheme. In each block the M coefficients with the largest
magnitude are kept. This is a local threshold, because the cut-off is
worked out again for every block.

How to run
----------
    python transform_coding.py
    python transform_coding.py --image "College ID Photo.jpg" --output output_images

Needs Python 3.8 or newer with: numpy, pillow and matplotlib.
"""

import argparse
import os
import sys

import numpy as np
import matplotlib

# The "Agg" backend draws straight to files. No window is ever opened, so
# the program also works on a machine with no screen.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

# ---------------------------------------------------------------------------
# Settings. These come straight from the assignment sheet.
# ---------------------------------------------------------------------------
BLOCK = 8                      # Size of each sub image (8 x 8).
TOTAL_COEFFS = BLOCK * BLOCK   # 64 coefficients in a block.
KEEP_FRACTIONS = (0.50, 0.25)  # Keep 50% and 25% of the coefficients.
TRANSFORMS = ("DFT", "DCT")    # The two transforms to compare.


# ===========================================================================
# Phase 1 and 2: loading, gray scale, padding and blocks
# ===========================================================================
def load_color_image(path):
    """Open the picture file and return it as an RGB PIL image."""
    if not os.path.isfile(path):
        sys.exit("Cannot find the image file: " + path)
    return Image.open(path).convert("RGB")


def to_gray(color_image):
    """
    Turn the colour picture into a gray scale picture.

    This uses the built-in conversion of the Pillow library (mode "L"),
    which is what the assignment asks for. Pillow weights the colours as
    0.299 R + 0.587 G + 0.114 B. The result is a 2D float array with values
    from 0 to 255.
    """
    return np.asarray(color_image.convert("L"), dtype=np.float64)


def pad_to_block_multiple(gray):
    """
    Add extra rows at the bottom and extra columns on the right so that the
    height and the width are both exact multiples of 8.

    The new pixels copy the nearest edge pixel ("edge" padding). That is
    better than padding with black, because a sudden black border would
    make a sharp edge inside the last blocks and waste coefficients on it.

    Returns the padded image and the number of rows and columns added.
    """
    height, width = gray.shape
    extra_rows = (-height) % BLOCK
    extra_cols = (-width) % BLOCK
    padded = np.pad(gray, ((0, extra_rows), (0, extra_cols)), mode="edge")
    return padded, extra_rows, extra_cols


def split_into_blocks(image):
    """
    Cut an image (H x W) into non-overlapping 8x8 blocks.

    The result has shape (number_of_blocks, 8, 8). Blocks are in reading
    order: left to right, then top to bottom.
    """
    height, width = image.shape
    rows, cols = height // BLOCK, width // BLOCK
    blocks = image.reshape(rows, BLOCK, cols, BLOCK).swapaxes(1, 2)
    return blocks.reshape(rows * cols, BLOCK, BLOCK)


def merge_blocks(blocks, height, width):
    """Put the blocks back together. This undoes split_into_blocks."""
    rows, cols = height // BLOCK, width // BLOCK
    grid = blocks.reshape(rows, cols, BLOCK, BLOCK).swapaxes(1, 2)
    return grid.reshape(height, width)


# ===========================================================================
# Phase 3: the transforms
# ===========================================================================
def dct_matrix(n=BLOCK):
    """
    Build the n x n orthonormal DCT matrix C.

    C[u, x] = a(u) * cos( (2x + 1) * u * pi / (2n) )
    with a(0) = sqrt(1/n) and a(u) = sqrt(2/n) for u > 0.

    The 2D transform of a block B is then  C @ B @ C.T, because the 2D DCT
    can be split into one pass over the rows and one pass over the columns.
    """
    u = np.arange(n).reshape(-1, 1)
    x = np.arange(n).reshape(1, -1)
    matrix = np.cos((2 * x + 1) * u * np.pi / (2 * n))
    matrix *= np.sqrt(2.0 / n)
    matrix[0, :] = np.sqrt(1.0 / n)
    return matrix


def dft_matrix(n=BLOCK):
    """
    Build the n x n unitary DFT matrix F.

    F[u, x] = exp( -j * 2 * pi * u * x / n ) / sqrt(n)

    The 1/sqrt(n) factor is split evenly between the forward and the
    inverse transform. That keeps the energy the same on both sides and
    makes DFT and DCT coefficients easy to compare. The values are complex.
    """
    u = np.arange(n).reshape(-1, 1)
    x = np.arange(n).reshape(1, -1)
    return np.exp(-2j * np.pi * u * x / n) / np.sqrt(n)


def forward_transform(blocks, name):
    """Apply the 2D DFT or 2D DCT to every block at once."""
    if name == "DCT":
        c = dct_matrix()
        return c @ blocks @ c.T
    f = dft_matrix()
    return f @ blocks @ f.T


def inverse_transform(coeffs, name):
    """
    Apply the inverse 2D transform to every block.

    For the DCT the matrix is real and orthonormal, so its inverse is just
    the transpose. For the DFT the inverse uses the conjugate transpose.
    The DFT result may carry a tiny imaginary part (rounding noise, or the
    effect of keeping only one of two mirrored coefficients), and the real
    part is the picture, so only the real part is returned.
    """
    if name == "DCT":
        c = dct_matrix()
        return c.T @ coeffs @ c
    f = dft_matrix()
    return np.real(f.conj().T @ coeffs @ f.conj())


# ===========================================================================
# Phase 4: quantisation (keep M of N coefficients in each block)
# ===========================================================================
def keep_largest(coeffs, keep_count):
    """
    In every block keep the `keep_count` coefficients with the largest
    magnitude and set the rest to zero.

    Returns the quantised coefficients and a boolean mask (True = kept).
    The order is decided per block, so this is a local threshold. A stable
    sort is used so that equal magnitudes are always handled the same way.
    """
    count = coeffs.shape[0]
    magnitude = np.abs(coeffs).reshape(count, TOTAL_COEFFS)
    order = np.argsort(-magnitude, axis=1, kind="stable")
    mask = np.zeros((count, TOTAL_COEFFS), dtype=bool)
    rows = np.arange(count).reshape(-1, 1)
    mask[rows, order[:, :keep_count]] = True
    mask = mask.reshape(count, BLOCK, BLOCK)
    return np.where(mask, coeffs, 0), mask


# ===========================================================================
# Phase 5 and 6: reconstruction and error
# ===========================================================================
def finish_image(blocks, padded_shape, original_shape):
    """
    Join the blocks, cut away the padding, and round to whole pixel values
    between 0 and 255, just like a real 8-bit image.
    """
    full = merge_blocks(blocks, *padded_shape)
    height, width = original_shape
    return np.clip(np.rint(full[:height, :width]), 0, 255)


def mean_square_error(original, rebuilt):
    """MSE = average of (original - rebuilt)^2 over all pixels."""
    return float(np.mean((original - rebuilt) ** 2))


# ===========================================================================
# Helpers for the pictures
# ===========================================================================
def log_view(coeffs):
    """Squash coefficient magnitudes with log(1 + |c|) so small ones show."""
    return np.log1p(np.abs(coeffs))


def save_plain(array, path):
    """Save a 2D array (0..255) as a plain gray PNG with no decoration."""
    Image.fromarray(np.clip(array, 0, 255).astype(np.uint8)).save(path)


def finish_figure(fig, folder, name):
    """Save a figure into the output folder and release its memory."""
    path = os.path.join(folder, name)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("  saved", name)


def annotate_cells(ax, values, fmt, threshold_color_from=None):
    """Write the number of each cell on top of an 8x8 picture."""
    peak = np.max(np.abs(values)) if threshold_color_from is None else threshold_color_from
    for r in range(values.shape[0]):
        for c in range(values.shape[1]):
            shade = "white" if abs(values[r, c]) < 0.5 * peak else "black"
            ax.text(c, r, fmt(values[r, c]), ha="center", va="center",
                    fontsize=6, color=shade)


def pick_busy_block(blocks):
    """Choose the block with the biggest spread of pixel values."""
    return int(np.argmax(blocks.reshape(len(blocks), -1).var(axis=1)))


# ===========================================================================
# The interim pictures, one function per phase
# ===========================================================================
def figure_original_and_gray(color_image, gray, folder):
    """Pictures 01 and 02: the input and its gray scale version."""
    fig, ax = plt.subplots(figsize=(4, 5.2))
    ax.imshow(color_image)
    ax.set_title("01  Original ID photo (%d x %d)" % color_image.size)
    ax.axis("off")
    finish_figure(fig, folder, "01_original_colour.png")

    fig, ax = plt.subplots(figsize=(4, 5.2))
    ax.imshow(gray, cmap="gray", vmin=0, vmax=255)
    ax.set_title("02  Gray scale image (%d x %d)" % (gray.shape[1], gray.shape[0]))
    ax.axis("off")
    finish_figure(fig, folder, "02_grayscale.png")


def figure_padding(padded, orig_shape, folder):
    """Picture 03: the padded image, with the padded strip marked in red."""
    height, width = orig_shape
    ph, pw = padded.shape
    fig, ax = plt.subplots(figsize=(4, 5.2))
    ax.imshow(padded, cmap="gray", vmin=0, vmax=255)
    ax.plot([width - 0.5, width - 0.5], [-0.5, ph - 0.5], color="red", lw=1)
    ax.plot([-0.5, pw - 0.5], [height - 0.5, height - 0.5], color="red", lw=1)
    ax.set_title("03  Padded to %d x %d\n(red lines: edge of the original, "
                 "%d row(s) and %d column(s) added)"
                 % (pw, ph, ph - height, pw - width), fontsize=8)
    ax.axis("off")
    finish_figure(fig, folder, "03_padded_image.png")


def figure_block_grid(padded, chosen, folder):
    """Picture 04: the 8x8 grid over the image, with one block highlighted."""
    ph, pw = padded.shape
    cols = pw // BLOCK
    fig, ax = plt.subplots(figsize=(4.6, 6))
    ax.imshow(padded, cmap="gray", vmin=0, vmax=255)
    for x in range(0, pw + 1, BLOCK):
        ax.axvline(x - 0.5, color="cyan", lw=0.3)
    for y in range(0, ph + 1, BLOCK):
        ax.axhline(y - 0.5, color="cyan", lw=0.3)
    r, c = divmod(chosen, cols)
    ax.add_patch(plt.Rectangle((c * BLOCK - 0.5, r * BLOCK - 0.5), BLOCK, BLOCK,
                               fill=False, edgecolor="red", lw=1.5))
    ax.set_title("04  Division into %d x %d blocks: %d x %d = %d blocks\n"
                 "(red: the block studied in pictures 05 and 07)"
                 % (BLOCK, BLOCK, ph // BLOCK, cols, (ph // BLOCK) * cols), fontsize=8)
    ax.axis("off")
    finish_figure(fig, folder, "04_block_grid.png")


def figure_selected_block(block, dct_block, dft_block, folder):
    """Picture 05: one block in the pixel domain and after each transform."""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.3))
    panels = [
        (block, "Pixel values", "gray", lambda v: "%d" % v),
        (np.abs(dct_block), "DCT  |coefficient|", "viridis", lambda v: "%d" % v),
        (np.abs(dft_block), "DFT  |coefficient|", "viridis", lambda v: "%d" % v),
    ]
    for ax, (data, title, cmap, fmt) in zip(axes, panels):
        ax.imshow(data, cmap=cmap)
        annotate_cells(ax, data, fmt)
        ax.set_title(title)
        ax.set_xticks(range(BLOCK))
        ax.set_yticks(range(BLOCK))
    fig.suptitle("05  The selected 8x8 block, before and after the transforms "
                 "(top-left cell is the DC term)")
    finish_figure(fig, folder, "05_selected_block_transforms.png")


def figure_coefficient_mosaics(dct_all, dft_all, padded_shape, folder):
    """Picture 06: all transformed blocks put side by side, on a log scale."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 6.5))
    for ax, data, name in ((axes[0], dft_all, "DFT"), (axes[1], dct_all, "DCT")):
        mosaic = merge_blocks(log_view(data), *padded_shape)
        ax.imshow(mosaic, cmap="magma")
        ax.set_title(name + " coefficients of every block")
        ax.axis("off")
    fig.suptitle("06  log(1 + |coefficient|) of all blocks. Each 8x8 tile has "
                 "its DC term at the top-left corner.", fontsize=9)
    finish_figure(fig, folder, "06_coefficient_mosaics.png")


def figure_selected_block_masks(masks, quantised, chosen, folder):
    """Picture 07: which coefficients of the selected block survive."""
    fig, axes = plt.subplots(2, 2, figsize=(8.5, 8.5))
    for row, name in enumerate(("DFT", "DCT")):
        for col, frac in enumerate(KEEP_FRACTIONS):
            ax = axes[row, col]
            key = (name, frac)
            mask = masks[key][chosen]
            ax.imshow(mask, cmap="Greens", vmin=0, vmax=1.4)
            values = np.abs(quantised[key][chosen])
            annotate_cells(ax, values, lambda v: "%d" % v if v else "", 1e9)
            ax.set_title("%s, keep %d%% (%d of %d)"
                         % (name, int(frac * 100), mask.sum(), TOTAL_COEFFS))
            ax.set_xticks(range(BLOCK))
            ax.set_yticks(range(BLOCK))
    fig.suptitle("07  Quantisation of the selected block: green cells are kept "
                 "(number = magnitude), white cells are set to zero")
    finish_figure(fig, folder, "07_selected_block_masks.png")


def figure_quantised_mosaics(quantised, padded_shape, folder):
    """Picture 08: every block after quantisation, in the same layout as 06."""
    fig, axes = plt.subplots(2, 2, figsize=(10, 13))
    for row, name in enumerate(("DFT", "DCT")):
        for col, frac in enumerate(KEEP_FRACTIONS):
            ax = axes[row, col]
            mosaic = merge_blocks(log_view(quantised[(name, frac)]), *padded_shape)
            ax.imshow(mosaic, cmap="magma")
            ax.set_title("%s, %d%% of coefficients kept" % (name, int(frac * 100)))
            ax.axis("off")
    fig.suptitle("08  Coefficients after quantisation (log scale)")
    finish_figure(fig, folder, "08_quantised_mosaics.png")


def figure_kept_position_maps(masks, folder):
    """
    Picture 09: for each position in the 8x8 block, the share of blocks that
    kept that position. It shows where each transform puts its energy.
    """
    fig, axes = plt.subplots(2, 2, figsize=(8, 7.5))
    for row, name in enumerate(("DFT", "DCT")):
        for col, frac in enumerate(KEEP_FRACTIONS):
            ax = axes[row, col]
            share = masks[(name, frac)].mean(axis=0) * 100
            im = ax.imshow(share, cmap="viridis", vmin=0, vmax=100)
            annotate_cells(ax, share, lambda v: "%d" % round(v), 100)
            ax.set_title("%s, keep %d%%" % (name, int(frac * 100)))
            ax.set_xticks(range(BLOCK))
            ax.set_yticks(range(BLOCK))
            fig.colorbar(im, ax=ax, fraction=0.046, label="% of blocks")
    fig.suptitle("09  How often each coefficient position was kept")
    finish_figure(fig, folder, "09_kept_position_maps.png")


def figure_reconstructions(gray, rebuilt, errors, folder):
    """Picture 10: the original beside the four reconstructions."""
    fig, axes = plt.subplots(1, 5, figsize=(17, 5))
    axes[0].imshow(gray, cmap="gray", vmin=0, vmax=255)
    axes[0].set_title("Original")
    for ax, key in zip(axes[1:], rebuilt):
        ax.imshow(rebuilt[key], cmap="gray", vmin=0, vmax=255)
        ax.set_title("%s, keep %d%%\nMSE = %.2f" % (key[0], int(key[1] * 100), errors[key]))
    for ax in axes:
        ax.axis("off")
    fig.suptitle("10  Reconstructed images")
    finish_figure(fig, folder, "10_reconstructions.png")


def figure_differences(diffs, errors, folder):
    """Picture 11: |original - reconstructed| with one shared colour scale."""
    top = max(d.max() for d in diffs.values())
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 12))
    for row, name in enumerate(("DFT", "DCT")):
        for col, frac in enumerate(KEEP_FRACTIONS):
            ax = axes[row, col]
            key = (name, frac)
            im = ax.imshow(diffs[key], cmap="inferno", vmin=0, vmax=top)
            ax.set_title("%s, keep %d%%   (MSE = %.2f)" % (name, int(frac * 100), errors[key]))
            ax.axis("off")
    fig.colorbar(im, ax=axes, fraction=0.03, label="absolute difference (gray levels)")
    fig.suptitle("11  Difference images |original - reconstructed| (same colour scale)")
    finish_figure(fig, folder, "11_difference_images.png")


def figure_mse_chart(errors, folder):
    """Picture 12: a bar chart of the four MSE values."""
    fig, ax = plt.subplots(figsize=(6, 4.2))
    width = 0.35
    for i, name in enumerate(("DFT", "DCT")):
        vals = [errors[(name, f)] for f in KEEP_FRACTIONS]
        bars = ax.bar(np.arange(2) + (i - 0.5) * width, vals, width, label=name)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, "%.2f" % v,
                    ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(2))
    ax.set_xticklabels(["%d%% kept" % int(f * 100) for f in KEEP_FRACTIONS])
    ax.set_ylabel("Mean Square Error")
    ax.set_title("12  MSE of DFT and DCT (lower is better)")
    ax.legend()
    finish_figure(fig, folder, "12_mse_comparison.png")


# ===========================================================================
# Self check
# ===========================================================================
def self_check(blocks):
    """
    Three quick tests that prove the maths is right before the real run.

    1. The matrix DFT must agree with numpy's own FFT (orthonormal scaling).
    2. Going forward and back with every coefficient kept must give the
       same blocks again, for both transforms.
    3. The DCT matrix must be orthonormal (C times C-transpose is identity).
    """
    sample = blocks[: min(50, len(blocks))]
    ours = forward_transform(sample, "DFT")
    theirs = np.fft.fft2(sample, norm="ortho")
    assert np.allclose(ours, theirs), "DFT does not match numpy FFT"
    for name in TRANSFORMS:
        back = inverse_transform(forward_transform(sample, name), name)
        assert np.allclose(back, sample), name + " round trip failed"
    c = dct_matrix()
    assert np.allclose(c @ c.T, np.eye(BLOCK)), "DCT matrix is not orthonormal"
    print("Self check passed: DFT matches FFT, both transforms invert exactly.")


# ===========================================================================
# Main program
# ===========================================================================
def main():
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Assignment 3: transform coding with DFT and DCT.")
    parser.add_argument("--image", default=os.path.join(here, "College ID Photo.jpg"),
                        help="path of the ID photo (default: College ID Photo.jpg next to this script)")
    parser.add_argument("--output", default=os.path.join(here, "output_images"),
                        help="folder for the pictures (default: output_images next to this script)")
    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)

    print("Phase 1: load the photo and convert it to gray scale")
    color = load_color_image(args.image)
    gray = to_gray(color)
    figure_original_and_gray(color, gray, args.output)

    print("Phase 2: pad and divide into %dx%d blocks" % (BLOCK, BLOCK))
    padded, extra_rows, extra_cols = pad_to_block_multiple(gray)
    blocks = split_into_blocks(padded)
    chosen = pick_busy_block(blocks)
    print("  image %dx%d -> padded %dx%d (%d rows, %d columns added), %d blocks"
          % (gray.shape[1], gray.shape[0], padded.shape[1], padded.shape[0],
             extra_rows, extra_cols, len(blocks)))
    figure_padding(padded, gray.shape, args.output)
    figure_block_grid(padded, chosen, args.output)
    self_check(blocks)

    print("Phase 3: transform every block with the DFT and the DCT")
    coeffs = {name: forward_transform(blocks, name) for name in TRANSFORMS}
    figure_selected_block(blocks[chosen], coeffs["DCT"][chosen], coeffs["DFT"][chosen], args.output)
    figure_coefficient_mosaics(coeffs["DCT"], coeffs["DFT"], padded.shape, args.output)

    print("Phase 4: quantise (keep the largest coefficients in each block)")
    quantised, masks = {}, {}
    for name in TRANSFORMS:
        for frac in KEEP_FRACTIONS:
            keep = int(round(frac * TOTAL_COEFFS))
            quantised[(name, frac)], masks[(name, frac)] = keep_largest(coeffs[name], keep)
    figure_selected_block_masks(masks, quantised, chosen, args.output)
    figure_quantised_mosaics(quantised, padded.shape, args.output)
    figure_kept_position_maps(masks, args.output)

    print("Phase 5: inverse transform and reconstruction")
    rebuilt = {}
    for key, q in quantised.items():
        spatial = inverse_transform(q, key[0])
        rebuilt[key] = finish_image(spatial, padded.shape, gray.shape)
        save_plain(rebuilt[key], os.path.join(
            args.output, "reconstructed_%s_%d.png" % (key[0].lower(), int(key[1] * 100))))
    figure_reconstructions(gray, rebuilt, {k: mean_square_error(gray, v) for k, v in rebuilt.items()}, args.output)

    print("Phase 6: error comparison")
    diffs = {k: np.abs(gray - v) for k, v in rebuilt.items()}
    errors = {k: mean_square_error(gray, v) for k, v in rebuilt.items()}
    for key, d in diffs.items():
        save_plain(d, os.path.join(args.output, "difference_%s_%d.png" % (key[0].lower(), int(key[1] * 100))))
    figure_differences(diffs, errors, args.output)
    figure_mse_chart(errors, args.output)

    lines = ["Transform  Kept        Coefficients/block   MSE"]
    for frac in KEEP_FRACTIONS:
        for name in TRANSFORMS:
            lines.append("%-10s %3d%%        %2d of %d             %9.4f"
                         % (name, int(frac * 100), int(round(frac * TOTAL_COEFFS)),
                            TOTAL_COEFFS, errors[(name, frac)]))
    report = "\n".join(lines)
    print("\n" + report)
    with open(os.path.join(args.output, "mse_results.txt"), "w") as handle:
        handle.write(report + "\n")
    print("\nDone. All pictures are in:", args.output)


if __name__ == "__main__":
    main()
