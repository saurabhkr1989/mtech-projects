# Assignment 1 — Implementation

Sampling bandwidth calculation, image storage comparison, and Huffman coding,
implemented in `huffman_and_sampling.py` (pure Python 3, no external
dependencies).

## Contents
- `huffman_and_sampling.py` — solves Q1 (bandwidth), Q2 (storage comparison),
  and Q3 (Huffman coding of the digit-quotient message derived from the
  10-digit contact number `0703888598`).

## How to run
```bash
python3 huffman_and_sampling.py
```

## What it does
1. **Q1** — Computes the Nyquist sampling rate (`2 x f_N`) and multiplies by
   `log2(16) = 4` bits/sample to get the distortion-free channel bandwidth in
   bits per second.
2. **Q2** — Computes total bits for Image A (100x100 @ 8 bpp) and Image B
   (200x200 @ 4 bpp) and reports which needs more storage.
3. **Q3** — Builds the message by taking each digit of the contact number,
   integer-dividing by 2, then runs a from-scratch binary Huffman coder
   (min-heap based, standard greedy merge of the two least-probable nodes)
   to produce an optimal prefix code, the encoded bitstream, and a
   comparison against fixed-length coding.

Sample output (for contact number `0703888598`) is reproduced in the
assignment `Report.docx` in the parent folder.
