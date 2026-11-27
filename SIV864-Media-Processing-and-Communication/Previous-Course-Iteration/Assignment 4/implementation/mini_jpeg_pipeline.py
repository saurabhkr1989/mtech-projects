"""
SIV864 - Assignment 3A (folder "Assignment 4"): JPEG
M.Tech level implementation.

The assignment itself asks only for a *reading* exercise (list points from
Wallace's JPEG paper not covered in lectures). To turn the reading into a
concrete, verifiable artifact, this script implements a small but
functionally complete "Baseline-style" JPEG-like encoder/decoder pipeline,
directly following the processing steps described in the paper (Sections
4.1 - 4.4, 7.1 - 7.3):

    8x8 blocks -> level shift -> FDCT -> Quantization -> zig-zag ->
    DPCM of DC -> (RUNLENGTH,SIZE)/(AMPLITUDE) intermediate symbols for AC ->
    Huffman entropy coding -> [reverse for decode] -> IDCT -> reconstruction

This is intentionally a *teaching* implementation (single-component /
grayscale, one quantization table, one adaptively-built Huffman table,
no interchange-format headers/markers) -- exactly the "essentials of
DCT-based compression" the paper describes in Section 4.

Author: Saurabh
"""

import numpy as np
import heapq
from collections import Counter
from itertools import count as _count

# ---------------------------------------------------------------------------
# 0. Synthetic test image (since no source image was supplied with the
#    assignment). Deterministic / reproducible.
# ---------------------------------------------------------------------------
def make_test_image(size=256) -> np.ndarray:
    y, x = np.mgrid[0:size, 0:size]
    gradient = (x / size) * 120
    circle = 80 * np.exp(-(((x - size / 2) ** 2 + (y - size / 2) ** 2) / (2 * (size / 5) ** 2)))
    checker = 25 * (((x // 16) + (y // 16)) % 2)
    img = 60 + gradient + circle + checker
    rng = np.random.default_rng(0)
    img += rng.normal(0, 3, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# 1. 8x8 block FDCT / IDCT (Wallace eq. 1 and 2, vectorized)
# ---------------------------------------------------------------------------
def _dct_basis(N=8):
    n = np.arange(N)
    k = n.reshape(-1, 1)
    basis = np.cos((2 * n + 1) * k * np.pi / (2 * N))
    c = np.ones(N)
    c[0] = 1 / np.sqrt(2)
    return basis, c

_BASIS8, _C8 = _dct_basis(8)


def fdct2(block: np.ndarray) -> np.ndarray:
    """2D separable 8x8 FDCT: F = (1/4) C * (B f B^T) * C^T (JPEG normalization)."""
    B = _BASIS8
    tmp = B @ block @ B.T
    return 0.25 * np.outer(_C8, _C8) * tmp


def idct2(coeff: np.ndarray) -> np.ndarray:
    B = _BASIS8
    scaled = np.outer(_C8, _C8) * coeff
    return 0.25 * (B.T @ scaled @ B)


# Standard JPEG luminance quantization table (Annex K / Wallace paper Fig. 10c)
Q_LUMA = np.array([
    [16, 11, 10, 16, 24, 40, 51, 61],
    [12, 12, 14, 19, 26, 58, 60, 55],
    [14, 13, 16, 24, 40, 57, 69, 56],
    [14, 17, 22, 29, 51, 87, 80, 62],
    [18, 22, 37, 56, 68, 109, 103, 77],
    [24, 35, 55, 64, 81, 104, 113, 92],
    [49, 64, 78, 87, 103, 121, 120, 101],
    [72, 92, 95, 98, 112, 100, 103, 99],
], dtype=np.float64)

ZIGZAG_INDEX = sorted(
    [(i, j) for i in range(8) for j in range(8)],
    key=lambda ij: (ij[0] + ij[1], ij[1] if (ij[0] + ij[1]) % 2 else -ij[1])
)


def zigzag(block: np.ndarray) -> list:
    return [block[i, j] for i, j in ZIGZAG_INDEX]


def inv_zigzag(seq: list) -> np.ndarray:
    block = np.zeros((8, 8))
    for (i, j), v in zip(ZIGZAG_INDEX, seq):
        block[i, j] = v
    return block


# ---------------------------------------------------------------------------
# 2. Huffman entropy coder (clean binary-tree Node implementation, same
#    design as used in Assignment 1/2)
# ---------------------------------------------------------------------------
class _HNode:
    __slots__ = ("freq", "symbol", "left", "right")

    def __init__(self, freq, symbol=None, left=None, right=None):
        self.freq = freq
        self.symbol = symbol
        self.left = left
        self.right = right

    def is_leaf(self):
        return self.left is None and self.right is None


def huffman_codebook(symbols: list) -> dict:
    freq = Counter(symbols)
    tie = _count()
    heap = [(f, next(tie), _HNode(f, symbol=s)) for s, f in freq.items()]
    heapq.heapify(heap)

    if len(heap) == 1:
        only_symbol = heap[0][2].symbol
        return {only_symbol: "0"}

    while len(heap) > 1:
        f1, _, n1 = heapq.heappop(heap)
        f2, _, n2 = heapq.heappop(heap)
        merged = _HNode(f1 + f2, left=n1, right=n2)
        heapq.heappush(heap, (merged.freq, next(tie), merged))

    root = heap[0][2]
    codebook = {}

    def walk(node, prefix):
        if node.is_leaf():
            codebook[node.symbol] = prefix or "0"
            return
        walk(node.left, prefix + "0")
        walk(node.right, prefix + "1")

    walk(root, "")
    return codebook


def encode_symbols(symbols: list) -> tuple:
    cb = huffman_codebook(symbols)
    bits = "".join(cb[s] for s in symbols)
    return bits, cb


# ---------------------------------------------------------------------------
# 3. Full pipeline: encode + decode an entire image
# ---------------------------------------------------------------------------
def jpeg_like_encode(img: np.ndarray, quality_scale: float = 1.0):
    H, W = img.shape
    assert H % 8 == 0 and W % 8 == 0
    shifted = img.astype(np.float64) - 128
    Q = Q_LUMA * quality_scale

    dc_values = []
    ac_symbol1 = []   # (RUNLENGTH, SIZE) style symbols, flattened across all blocks
    ac_symbol2 = []   # AMPLITUDE values (paired 1:1 with ac_symbol1, excluding EOB)
    dequant_blocks = {}

    prev_dc = 0
    for by in range(0, H, 8):
        for bx in range(0, W, 8):
            block = shifted[by:by + 8, bx:bx + 8]
            F = fdct2(block)
            Fq = np.round(F / Q)

            zz = zigzag(Fq)
            dc = zz[0]
            diff = dc - prev_dc
            prev_dc = dc
            dc_values.append(diff)

            # AC run-length symbolization (JPEG Baseline style)
            ac = zz[1:]
            run = 0
            for coeff in ac:
                if coeff == 0:
                    run += 1
                else:
                    size = int(coeff).bit_length()
                    ac_symbol1.append((run, size))
                    ac_symbol2.append(int(coeff))
                    run = 0
            ac_symbol1.append(("EOB",))  # end of block

            dequant_blocks[(by, bx)] = Fq * Q  # keep for reconstruction

    # Entropy coding (separately for the three symbol streams, as JPEG does
    # for DC-size, AC-(run,size), with amplitudes as raw VLI-style ints)
    dc_bits, dc_cb = encode_symbols(dc_values)
    ac1_bits, ac1_cb = encode_symbols(ac_symbol1)

    n_blocks = (H // 8) * (W // 8)
    raw_bits = H * W * 8  # 8 bits/pixel raw
    compressed_bits = len(dc_bits) + len(ac1_bits) + len(ac_symbol2) * 11  # 11-bit amplitude budget
    return {
        "H": H, "W": W, "n_blocks": n_blocks,
        "dequant_blocks": dequant_blocks,
        "raw_bits": raw_bits,
        "compressed_bits": compressed_bits,
        "compression_ratio": raw_bits / compressed_bits,
        "dc_values": dc_values,
        "n_ac_symbols": len(ac_symbol1),
    }


def jpeg_like_decode(encoded: dict) -> np.ndarray:
    H, W = encoded["H"], encoded["W"]
    recon = np.zeros((H, W))
    for (by, bx), Fdq in encoded["dequant_blocks"].items():
        block = idct2(Fdq) + 128
        recon[by:by + 8, bx:bx + 8] = block
    return np.clip(recon, 0, 255)


def psnr(original: np.ndarray, reconstructed: np.ndarray) -> float:
    mse = np.mean((original.astype(np.float64) - reconstructed.astype(np.float64)) ** 2)
    if mse == 0:
        return float("inf")
    return 10 * np.log10(255 ** 2 / mse)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    img = make_test_image(256)
    print("=" * 70)
    print("Mini Baseline-style JPEG pipeline (grayscale, single component)")
    print("=" * 70)
    print(f"Test image: {img.shape[0]}x{img.shape[1]}, 8-bit grayscale (synthetic)")

    for q_scale in (0.5, 1.0, 2.0, 4.0):
        enc = jpeg_like_encode(img, quality_scale=q_scale)
        dec = jpeg_like_decode(enc)
        p = psnr(img, dec)
        bpp = enc["compressed_bits"] / (enc["H"] * enc["W"])
        print(f"\nQuantizer scale = {q_scale}x standard table:")
        print(f"  Compressed size   : {enc['compressed_bits']} bits "
              f"({enc['compressed_bits']/8:.0f} bytes) vs raw {enc['raw_bits']/8:.0f} bytes")
        print(f"  Compression ratio : {enc['compression_ratio']:.2f}x")
        print(f"  Bits per pixel    : {bpp:.3f} bpp")
        print(f"  PSNR (reconstructed vs original): {p:.2f} dB")

    # Save a visual before/after for the report
    from PIL import Image
    enc = jpeg_like_encode(img, quality_scale=1.0)
    dec = jpeg_like_decode(enc)
    Image.fromarray(img).save("original.png")
    Image.fromarray(dec.astype(np.uint8)).save("reconstructed_q1x.png")
    print("\nSaved original.png and reconstructed_q1x.png for visual comparison.")
