# Assignment 5 — Implementation (Assignment 3B: Transform Coding)

Implements every required sub-part of the assignment end-to-end in
`transform_coding_dft_dct.py` (Python 3 + NumPy + Pillow + Matplotlib).

## Contents
- `transform_coding_dft_dct.py` — full pipeline (grayscale conversion,
  blocking, DFT, DCT, truncation, inverse transform, reconstruction,
  error comparison + plots).

## How to run
```bash
pip install numpy pillow matplotlib --break-system-packages
python3 transform_coding_dft_dct.py
```

Outputs (written to this folder):
- `source_color.png`, `source_gray.png` — synthetic 256x256 test image and
  its grayscale conversion (via PIL's built-in `Image.convert('L')`).
- `reconstructed_dft_k16.png`, `reconstructed_dct_k16.png` — reconstructed
  images keeping only 16/64 coefficients per 8x8 block, for DFT and DCT
  respectively (visual side-by-side comparison).
- `dft_vs_dct_error.png` — MSE and PSNR vs number of retained coefficients,
  for both transforms.

## Pipeline (maps directly to the assignment's bullet list)
1. **Grayscale conversion** — `Image.convert('L')` (in-built PIL function,
   ITU-R 601-2 luma weighting).
2. **Block division** — image split into non-overlapping 8x8 sub-images.
3. **Transform of blocks** — both `numpy.fft.fft2` (2D DFT) and a
   from-scratch separable 2D DCT-II (matrix form of the JPEG DCT equation)
   are applied per block, after the standard -128 level shift.
4. **Truncation/quantization** — a zig-zag (low-frequency-first) mask
   retains only the K most significant coefficients out of 64
   (K = 2,4,8,16,24,32,48,64); an alternative magnitude-ranked mask is also
   implemented (`magnitude_mask`) for experimentation.
5. **Inverse transform + reconstruction** — `numpy.fft.ifft2` / custom
   IDCT reconstruct each block from the truncated coefficients; blocks are
   re-assembled into the full image.
6. **DFT vs DCT comparison** — MSE and PSNR are computed for identical K
   across both transforms and plotted together.

## Key result
For every K tested, **DCT reconstruction error is lower than DFT error**
(e.g. at K=16/64: DCT MSE ≈ 214 / PSNR ≈ 24.8 dB vs DFT MSE ≈ 503 / PSNR ≈
21.1 dB). This matches the well-known theoretical property that the DCT has
better **energy compaction** than the DFT for real, non-periodic image
signals — the DCT approximates the Karhunen-Loeve Transform (KLT) for
highly correlated (Markov-1) image data, while the DFT's implicit periodic
extension introduces boundary discontinuities that spread energy into
high-frequency coefficients. This is precisely why JPEG adopted the DCT
rather than the DFT (see Assignment 4 report).
