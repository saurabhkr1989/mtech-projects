# Assignment 3 — Implementation

Run Length Coding (RLC) for binary images, and Lossless vs Lossy Predictive
Coding (DPCM), implemented in `rle_and_predictive_coding.py` (Python 3 +
NumPy).

## Contents
- `rle_and_predictive_coding.py` — RLE encode/decode + lossless/lossy DPCM.

## How to run
```bash
pip install numpy --break-system-packages   # if not already installed
python3 rle_and_predictive_coding.py
```

## What it does
1. **Q1 — Run Length Coding.** Encodes a small illustrative 6x10
   Black/White image row-by-row as `(value, run-length)` pairs, decodes it
   back and asserts an exact (lossless) match. It then repeats the exercise
   on a larger, more realistic 30x400 "scanned document" style bilevel
   image (sparse black text blocks on a white background) to show the
   ~5x compression RLE achieves when runs are genuinely long — this is
   the regime bilevel image/fax coding (e.g. CCITT Group 3) is designed
   for; the small toy example is included to honestly show that RLE can
   *lose* on very short/noisy runs (overhead of storing the run length).
2. **Q2 — Lossless vs Lossy Predictive Coding (DPCM).** Implements a
   first-order predictor `x_hat[n] = x[n-1]` on a synthetic smoothly
   varying test signal:
   - *Lossless DPCM*: the residual `e[n] = x[n] - x_hat[n]` is kept at
     full integer precision and entropy-coded as-is → perfect
     reconstruction (verified by assertion).
   - *Lossy DPCM*: the residual is uniformly quantized (step sizes 1, 4,
     12) inside a **closed feedback loop** (predictor uses the previously
     *reconstructed* sample, not the original) so quantization error does
     not accumulate unboundedly — the standard DPCM architecture. MSE vs
     the original signal grows with the quantizer step size, demonstrating
     the fundamental lossless/lossy trade-off.
