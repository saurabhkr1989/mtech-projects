"""
SIV864/CSM011 - Assignment 3: Run Length Coding and Predictive Coding
M.Tech level implementation.

Q1: Run Length Coding (RLC) of a binary (B/W) image.
Q2: Lossless vs Lossy Predictive Coding (DPCM), demonstrated on a real signal.

Author: Saurabh
"""

import numpy as np


# ---------------------------------------------------------------------------
# Q1: Run Length Coding for a binary image
# ---------------------------------------------------------------------------
def rle_encode_1d(sequence) -> list:
    """Classic (value, run-length) RLE for a 1-D sequence of 0/1 pixels."""
    if len(sequence) == 0:
        return []
    encoded = []
    prev = sequence[0]
    run = 1
    for px in sequence[1:]:
        if px == prev:
            run += 1
        else:
            encoded.append((prev, run))
            prev = px
            run = 1
    encoded.append((prev, run))
    return encoded


def rle_decode_1d(encoded: list) -> list:
    out = []
    for value, run in encoded:
        out.extend([value] * run)
    return out


def rle_encode_image(binary_image: np.ndarray) -> list:
    """Row-by-row RLE of a 2D binary image (0=Black,1=White). Each row is
    independently run-length coded (as commonly done for fax/bilevel
    images, e.g. CCITT Group 3)."""
    return [rle_encode_1d(row.tolist()) for row in binary_image]


def rle_decode_image(encoded_rows: list, width: int) -> np.ndarray:
    rows = [rle_decode_1d(row) for row in encoded_rows]
    return np.array(rows, dtype=np.uint8)


def bits_for_raw_image(binary_image: np.ndarray) -> int:
    return binary_image.size * 1  # 1 bit/pixel raw


def bits_for_rle(encoded_rows: list, run_length_bits: int = 8) -> int:
    """Assume 1 bit for the value + `run_length_bits` bits for the run
    length of each run (a simplification; real codecs use variable-length
    / Huffman codes for run lengths, see JPEG/CCITT Group 3)."""
    total_runs = sum(len(row) for row in encoded_rows)
    return total_runs * (1 + run_length_bits)


# ---------------------------------------------------------------------------
# Q2: Lossless vs Lossy Predictive Coding (DPCM)
# ---------------------------------------------------------------------------
def dpcm_lossless_encode(signal: np.ndarray) -> tuple:
    """Simple first-order predictor: predict x_hat[n] = x[n-1].
    Residual e[n] = x[n] - x_hat[n] is encoded EXACTLY (integer, no
    quantization) -> lossless. Perfect reconstruction is guaranteed."""
    signal = signal.astype(np.int64)
    pred = np.zeros_like(signal)
    pred[1:] = signal[:-1]
    residual = signal - pred
    return residual, pred


def dpcm_lossless_decode(residual: np.ndarray) -> np.ndarray:
    n = len(residual)
    recon = np.zeros(n, dtype=np.int64)
    recon[0] = residual[0]
    for i in range(1, n):
        recon[i] = recon[i - 1] + residual[i]
    return recon


def uniform_quantizer(x: np.ndarray, step: int) -> np.ndarray:
    """Quantize to nearest multiple of `step` (many-to-one, lossy)."""
    return np.round(x / step).astype(np.int64) * step


def dpcm_lossy_encode(signal: np.ndarray, step: int) -> tuple:
    """Predictive coding with a QUANTIZED residual (closed-loop DPCM: the
    predictor uses the previously RECONSTRUCTED sample, not the original,
    so quantization error does not accumulate without bound)."""
    signal = signal.astype(np.int64)
    n = len(signal)
    recon = np.zeros(n, dtype=np.int64)
    quantized_residuals = np.zeros(n, dtype=np.int64)
    pred_prev = 0
    for i in range(n):
        pred = pred_prev
        e = signal[i] - pred
        eq = uniform_quantizer(np.array([e]), step)[0]
        quantized_residuals[i] = eq
        recon[i] = pred + eq
        pred_prev = recon[i]
    return quantized_residuals, recon


def dpcm_lossy_decode(quantized_residuals: np.ndarray) -> np.ndarray:
    n = len(quantized_residuals)
    recon = np.zeros(n, dtype=np.int64)
    pred_prev = 0
    for i in range(n):
        recon[i] = pred_prev + quantized_residuals[i]
        pred_prev = recon[i]
    return recon


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("Q1: Run Length Coding of a binary (Black=0 / White=1) image")
    print("=" * 70)
    # A small illustrative 6x10 binary image (e.g. a scanned document/fax
    # line pattern) with long runs, typical of bilevel images.
    binary_image = np.array([
        [1,1,1,1,1,0,0,0,1,1],
        [1,1,1,0,0,0,0,0,1,1],
        [1,1,0,0,0,0,0,0,0,1],
        [1,0,0,0,0,0,0,0,0,0],
        [1,1,0,0,0,0,0,0,1,1],
        [1,1,1,1,1,1,1,1,1,1],
    ], dtype=np.uint8)

    print("Original binary image (0=Black, 1=White):")
    print(binary_image)

    encoded_rows = rle_encode_image(binary_image)
    print("\nRow-wise RLE encoding, (value, run-length) pairs:")
    for i, row_code in enumerate(encoded_rows):
        print(f"  row {i}: {row_code}")

    decoded_image = rle_decode_image(encoded_rows, binary_image.shape[1])
    assert np.array_equal(binary_image, decoded_image), "RLE round-trip failed!"
    print("\nDecoded image matches original exactly (lossless): ", np.array_equal(binary_image, decoded_image))

    raw_bits = bits_for_raw_image(binary_image)
    rle_bits = bits_for_rle(encoded_rows, run_length_bits=4)
    print(f"\nRaw bits (1 bpp): {raw_bits}")
    print(f"RLE bits (1-bit value + 4-bit run length per run): {rle_bits}")
    print(f"Compression ratio: {raw_bits / rle_bits:.2f}x  "
          f"(small toy image: per-run overhead dominates)")

    # A larger, more realistic bilevel "scanned document" style image with
    # long horizontal runs -- this is where RLE genuinely wins, as it does
    # for real fax/CCITT Group 3 pages.
    rng_doc = np.random.default_rng(7)
    width_doc = 400
    height_doc = 30
    doc_image = np.ones((height_doc, width_doc), dtype=np.uint8)  # mostly white
    for r in range(height_doc):
        # scatter a few black text-like blocks per row
        n_blocks = rng_doc.integers(2, 6)
        for _ in range(n_blocks):
            start = rng_doc.integers(0, width_doc - 20)
            length = rng_doc.integers(5, 20)
            doc_image[r, start:start + length] = 0

    encoded_doc = rle_encode_image(doc_image)
    decoded_doc = rle_decode_image(encoded_doc, width_doc)
    assert np.array_equal(doc_image, decoded_doc)
    raw_bits_doc = bits_for_raw_image(doc_image)
    rle_bits_doc = bits_for_rle(encoded_doc, run_length_bits=9)  # 9 bits covers runs up to 400
    print(f"\nRealistic {height_doc}x{width_doc} bilevel 'document' image:")
    print(f"  Raw bits (1 bpp)                         : {raw_bits_doc}")
    print(f"  RLE bits (1-bit value + 9-bit run length) : {rle_bits_doc}")
    print(f"  Compression ratio                        : {raw_bits_doc / rle_bits_doc:.2f}x")

    print()
    print("=" * 70)
    print("Q2: Lossless vs Lossy Predictive Coding (DPCM) on a test signal")
    print("=" * 70)
    rng = np.random.default_rng(42)
    n = 40
    # A smoothly varying signal (typical of natural image rows / audio),
    # so that neighboring-sample prediction is effective.
    t = np.arange(n)
    signal = (128 + 40 * np.sin(2 * np.pi * t / 20) + rng.normal(0, 2, n)).round().astype(np.int64)
    signal = np.clip(signal, 0, 255)

    # --- Lossless DPCM ---
    residual, pred = dpcm_lossless_encode(signal)
    recon_lossless = dpcm_lossless_decode(residual)
    lossless_perfect = np.array_equal(signal, recon_lossless)
    print(f"Lossless DPCM: perfect reconstruction = {lossless_perfect}")
    print(f"  Original signal[:10]      : {signal[:10].tolist()}")
    print(f"  Residual e[n]=x[n]-x[n-1][:10]: {residual[:10].tolist()}")
    print(f"  Reconstructed[:10]        : {recon_lossless[:10].tolist()}")
    print(f"  Max |signal - residual dynamic range| helps entropy coding "
          f"(std(signal)={signal.std():.2f} vs std(residual)={residual.std():.2f})")

    # --- Lossy DPCM ---
    for step in (1, 4, 12):
        q_res, recon_lossy = dpcm_lossy_encode(signal, step=step)
        recon_lossy2 = dpcm_lossy_decode(q_res)
        assert np.array_equal(recon_lossy, recon_lossy2)
        mse = np.mean((signal - recon_lossy) ** 2)
        print(f"\nLossy DPCM, quantizer step={step}:")
        print(f"  Reconstructed[:10]: {recon_lossy[:10].tolist()}")
        print(f"  MSE vs original   : {mse:.3f}  (0 => lossless when step=1 rounds to no change)")
