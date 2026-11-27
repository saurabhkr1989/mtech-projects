# Assignment 4 — Implementation (JPEG, Assignment 3A)

The assignment itself asks only for a reading exercise (list points from
Wallace's JPEG paper not covered in lectures). To ground that reading in a
working artifact, `mini_jpeg_pipeline.py` implements a small but functionally
complete "Baseline-style" JPEG encoder/decoder, directly following the
processing steps in the paper (Fig. 1/2, Sections 4.1-4.4, 7.1-7.3):

```
8x8 blocks -> level shift (-128) -> FDCT -> Quantization -> zig-zag ->
DPCM of DC coefficient -> (RUNLENGTH,SIZE)/(AMPLITUDE) symbols for AC ->
Huffman entropy coding -> [decoder reverses] -> Dequantize -> IDCT -> reconstruct
```

## Contents
- `mini_jpeg_pipeline.py` — full encode/decode pipeline + PSNR/compression
  measurement, run at 4 different quantizer scales.

## How to run
```bash
pip install numpy pillow --break-system-packages   # if not already installed
python3 mini_jpeg_pipeline.py
```

Produces `original.png` and `reconstructed_q1x.png` for visual before/after
comparison, and prints compression ratio / bits-per-pixel / PSNR for
quantizer scales 0.5x, 1x, 2x, 4x of the standard JPEG luminance table.

## What it implements (and how it maps to the paper)
- **8x8 block FDCT/IDCT** using the exact separable-cosine formula from the
  paper (Eq. 1 and 2), vectorized with a basis matrix instead of the naive
  4-nested-loop form.
- **Uniform quantization** (Eq. 3) using the actual standard JPEG luminance
  quantization table reproduced in Figure 10(c) of the paper.
- **Zig-zag ordering** of the 64 quantized coefficients (Figure 3).
- **Differential DC coding** across blocks in raster order (Figure 3).
- **AC run-length + size symbolization**: each nonzero AC coefficient is
  represented as `(RUNLENGTH, SIZE)` + `AMPLITUDE`, with an `EOB` (end of
  block) symbol when the remaining coefficients are all zero — exactly the
  Baseline intermediate representation described in Section 7.1.
- **Huffman entropy coding** (built from scratch, same design as
  Assignments 1/2) applied to the DC-difference symbols and the AC
  `(RUNLENGTH,SIZE)` symbols, with amplitude values budgeted at a fixed
  11-bit VLI-style cost (paper Section 7.2/Table 3), since a full VLI
  bit-length table was out of scope for this teaching implementation.

## Notes / simplifications (explicitly out of scope)
- Single grayscale component only (no color-space conversion, no
  chrominance subsampling / interleaving / MCU logic from Section 6).
- No interchange-format headers, markers, or byte-stuffing (Section 10).
- Sequential Baseline mode only — no progressive or hierarchical modes
  (Sections 8-9) and no arithmetic coding alternative (Section 4.4).
These omissions are exactly the kind of "not covered in lectures" material
discussed in the accompanying report.
