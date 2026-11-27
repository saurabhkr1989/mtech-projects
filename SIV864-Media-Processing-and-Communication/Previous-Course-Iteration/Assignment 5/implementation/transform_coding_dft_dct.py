"""
SIV864/CSM011 - Assignment 3B: Transform Coding
M.Tech level implementation.

Implements every required sub-part:
  1. Convert image to grayscale using an in-built function (PIL Image.convert('L')).
  2. Divide image into 8x8 blocks (sub-images).
  3. Transform each block: 2D DFT and 2D DCT.
  4. Truncation/quantization: retain only the K most significant
     (energy-ranked, i.e. zig-zag/low-frequency-first) coefficients out
     of 64 per block; two retention strategies are demonstrated.
  5. Inverse transform + reconstruct the image from retained coefficients.
  6. Compare DFT vs DCT reconstruction error (MSE, PSNR) for the SAME
     number of retained coefficients.

Author: Saurabh
"""

import numpy as np
from PIL import Image, ImageDraw
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


BLOCK = 8


# ---------------------------------------------------------------------------
# 0. Test image generation + grayscale conversion (in-built function)
# ---------------------------------------------------------------------------
def make_source_image(size=256) -> Image.Image:
    """Create a synthetic color test image (since none was supplied with
    the assignment) with enough structure (edges, gradients, texture) to
    make transform-coding truncation effects visible."""
    img = Image.new("RGB", (size, size), (30, 30, 60))
    draw = ImageDraw.Draw(img)
    for i in range(0, size, 8):
        shade = int(255 * i / size)
        draw.line([(i, 0), (i, size)], fill=(shade, 60, 255 - shade), width=2)
    draw.ellipse([size * 0.2, size * 0.2, size * 0.8, size * 0.8], outline=(255, 220, 0), width=6)
    draw.rectangle([size * 0.35, size * 0.35, size * 0.65, size * 0.65], outline=(0, 255, 120), width=4)
    for i in range(0, size, 16):
        draw.line([(0, i), (size, i)], fill=(200, 200, 200), width=1)
    return img


def to_grayscale(img: Image.Image) -> np.ndarray:
    """Uses PIL's built-in ITU-R 601-2 luma transform: L = 0.299R+0.587G+0.114B"""
    gray = img.convert("L")  # <-- in-built grayscale conversion, as required
    return np.array(gray, dtype=np.float64)


# ---------------------------------------------------------------------------
# 1. Block splitting
# ---------------------------------------------------------------------------
def split_blocks(gray: np.ndarray, block=BLOCK):
    H, W = gray.shape
    H2, W2 = (H // block) * block, (W // block) * block
    gray = gray[:H2, :W2]
    blocks = {}
    for by in range(0, H2, block):
        for bx in range(0, W2, block):
            blocks[(by, bx)] = gray[by:by + block, bx:bx + block]
    return blocks, (H2, W2)


def merge_blocks(blocks: dict, shape, block=BLOCK) -> np.ndarray:
    out = np.zeros(shape)
    for (by, bx), b in blocks.items():
        out[by:by + block, bx:bx + block] = b
    return out


# ---------------------------------------------------------------------------
# 2. Transforms: 2D DCT-II (separable, matrix form) and 2D DFT (numpy.fft)
# ---------------------------------------------------------------------------
def _dct_basis(N=BLOCK):
    n = np.arange(N)
    k = n.reshape(-1, 1)
    basis = np.cos((2 * n + 1) * k * np.pi / (2 * N))
    c = np.ones(N)
    c[0] = 1 / np.sqrt(2)
    return basis, c

_BASIS, _C = _dct_basis(BLOCK)


def dct2(block):
    tmp = _BASIS @ block @ _BASIS.T
    return 0.25 * np.outer(_C, _C) * tmp


def idct2(coeff):
    scaled = np.outer(_C, _C) * coeff
    return 0.25 * (_BASIS.T @ scaled @ _BASIS)


def dft2(block):
    return np.fft.fft2(block)


def idft2(coeff):
    return np.fft.ifft2(coeff).real


# ---------------------------------------------------------------------------
# 3. Truncation / retention masks (low-frequency-first, "zig-zag" style)
# ---------------------------------------------------------------------------
ZIGZAG_ORDER = sorted(
    [(i, j) for i in range(BLOCK) for j in range(BLOCK)],
    key=lambda ij: (ij[0] + ij[1], ij[1] if (ij[0] + ij[1]) % 2 else -ij[1])
)


def zigzag_mask(k_retained: int) -> np.ndarray:
    """Boolean mask keeping the first k coefficients in zig-zag (low-freq
    first) order -- the classic JPEG-style truncation strategy."""
    mask = np.zeros((BLOCK, BLOCK), dtype=bool)
    for (i, j) in ZIGZAG_ORDER[:k_retained]:
        mask[i, j] = True
    return mask


def magnitude_mask(coeff: np.ndarray, k_retained: int) -> np.ndarray:
    """Alternative strategy: keep the k coefficients of LARGEST magnitude
    (energy-based truncation) -- generally better for DFT since its energy
    is not as concentrated at (0,0) as DCT's for non-periodic content."""
    flat_idx = np.argsort(-np.abs(coeff).flatten())[:k_retained]
    mask = np.zeros(coeff.size, dtype=bool)
    mask[flat_idx] = True
    return mask.reshape(coeff.shape)


# ---------------------------------------------------------------------------
# 4. Full experiment: encode -> truncate -> decode -> measure error
# ---------------------------------------------------------------------------
def transform_and_truncate(blocks: dict, transform, inverse, k_retained: int,
                            strategy="zigzag"):
    recon_blocks = {}
    for pos, block in blocks.items():
        shifted = block - 128.0
        coeff = transform(shifted)
        if strategy == "zigzag":
            mask = zigzag_mask(k_retained)
        else:
            mask = magnitude_mask(coeff, k_retained)
        truncated = np.where(mask, coeff, 0)
        recon = inverse(truncated) + 128.0
        recon_blocks[pos] = recon
    return recon_blocks


def mse(a, b):
    return float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))


def psnr(a, b):
    m = mse(a, b)
    return float("inf") if m == 0 else 10 * np.log10(255 ** 2 / m)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    src_img = make_source_image(256)
    gray = to_grayscale(src_img)
    src_img.save("source_color.png")
    Image.fromarray(gray.astype(np.uint8)).save("source_gray.png")

    blocks, shape = split_blocks(gray)
    print(f"Grayscale image: {gray.shape}, split into {len(blocks)} blocks of {BLOCK}x{BLOCK}")

    retained_counts = [2, 4, 8, 16, 24, 32, 48, 64]
    results = {"k": retained_counts, "dft_mse": [], "dct_mse": [],
               "dft_psnr": [], "dct_psnr": []}

    for k in retained_counts:
        dft_blocks = transform_and_truncate(blocks, dft2, idft2, k, strategy="zigzag")
        dct_blocks = transform_and_truncate(blocks, dct2, idct2, k, strategy="zigzag")

        dft_img = np.clip(merge_blocks(dft_blocks, shape), 0, 255)
        dct_img = np.clip(merge_blocks(dct_blocks, shape), 0, 255)

        m_dft, m_dct = mse(gray, dft_img), mse(gray, dct_img)
        p_dft, p_dct = psnr(gray, dft_img), psnr(gray, dct_img)
        results["dft_mse"].append(m_dft)
        results["dct_mse"].append(m_dct)
        results["dft_psnr"].append(p_dft)
        results["dct_psnr"].append(p_dct)

        print(f"K={k:2d}/64 retained | DFT: MSE={m_dft:8.3f} PSNR={p_dft:6.2f} dB "
              f"| DCT: MSE={m_dct:8.3f} PSNR={p_dct:6.2f} dB "
              f"| DCT better by {m_dft - m_dct:8.3f} MSE")

        if k == 16:
            Image.fromarray(dft_img.astype(np.uint8)).save("reconstructed_dft_k16.png")
            Image.fromarray(dct_img.astype(np.uint8)).save("reconstructed_dct_k16.png")

    # ---- Plot: error vs number of retained coefficients ----
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].plot(results["k"], results["dft_mse"], "o-", label="DFT")
    axes[0].plot(results["k"], results["dct_mse"], "s-", label="DCT")
    axes[0].set_xlabel("Coefficients retained per 8x8 block (out of 64)")
    axes[0].set_ylabel("MSE (reconstructed vs original)")
    axes[0].set_title("Reconstruction Error: DFT vs DCT")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    axes[1].plot(results["k"], results["dft_psnr"], "o-", label="DFT")
    axes[1].plot(results["k"], results["dct_psnr"], "s-", label="DCT")
    axes[1].set_xlabel("Coefficients retained per 8x8 block (out of 64)")
    axes[1].set_ylabel("PSNR (dB)")
    axes[1].set_title("PSNR: DFT vs DCT")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig("dft_vs_dct_error.png", dpi=130)
    print("\nSaved: source_color.png, source_gray.png, reconstructed_dft_k16.png,")
    print("       reconstructed_dct_k16.png, dft_vs_dct_error.png")
