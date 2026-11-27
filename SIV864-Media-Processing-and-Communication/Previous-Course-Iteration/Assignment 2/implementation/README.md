# Assignment 2 — Implementation

This assignment is primarily a reading/analysis exercise on Huffman's 1952
paper. To make the answer to "can binary Huffman coding be extended to
D > 2 digits (e.g. ternary: 0,1,2)?" concrete rather than purely descriptive,
`nary_huffman.py` implements a from-scratch **generalized D-ary Huffman
coder** and validates it two ways.

## Contents
- `nary_huffman.py` — generalized (D-ary) Huffman tree builder + encoder.

## How to run
```bash
python3 nary_huffman.py
```

## What it does
1. **Validation against the paper itself** — reproduces Huffman's own D=4
   worked example (Table III of the paper, 8 messages with probabilities
   0.22 ... 0.02) and confirms the average code length obtained by this
   implementation (1.470 quaternary digits/symbol) exactly matches the
   paper's Table III result.
2. **Ternary (D=3) demo** — encodes the same message used in Assignment 1
   Q3 (digit-quotients of the contact number) using ternary digits
   {0,1,2} instead of binary, showing the identical greedy-merge procedure
   works unchanged for D=3, only the merge group size and dummy-symbol
   padding rule change.

## Key implementation detail
A D-ary Huffman tree needs `(N - 1) % (D - 1) == 0` (N = number of source
symbols) for every merge step to combine exactly D nodes. When this doesn't
hold, zero-probability "dummy" symbols are added until it does — this is the
standard generalization of the n0-symbol first merge described in the
paper's "Generalization of the Method" section.
