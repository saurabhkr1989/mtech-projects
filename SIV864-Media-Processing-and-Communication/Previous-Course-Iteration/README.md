# SIV864 / CSM011 — Special Module on Multimedia Processing and Communication

Solutions, implementations, and reports for all five assignments of this
course. Each assignment folder is self-contained:

```
Assignment N/
    Assignment.pdf          <- original assignment (as given)
    [reference paper].pdf   <- supplied reading material, where applicable
    Report.docx             <- full written solution / answers (M.Tech level)
    implementation/         <- runnable code + its own README.md
```

## Assignment index

| Folder | Topic | Type | Report | Code |
|---|---|---|---|---|
| `Assignment 1` | Sampling and Huffman Coding | Problems (3 questions) | `Report.docx` | `implementation/huffman_and_sampling.py` |
| `Assignment 2` | Huffman Coding — reading of Huffman's 1952 paper | Reading Q&A (3 questions) | `Report.docx` | `implementation/nary_huffman.py` |
| `Assignment 3` | Run Length Coding and Predictive Coding | Problems (2 questions) | `Report.docx` | `implementation/rle_and_predictive_coding.py` |
| `Assignment 4` | JPEG (Assignment 3A) — reading of Wallace's JPEG paper | Reading exercise | `Report.docx` | `implementation/mini_jpeg_pipeline.py` |
| `Assignment 5` | Transform Coding (Assignment 3B) — DFT vs DCT | Implementation required | `Report.docx` | `implementation/transform_coding_dft_dct.py` |

(Note: the assignment PDFs were provided under folder names 1-5, but their
internal titles are "Assignment 3A" for the JPEG reading exercise, held in
the `Assignment 4` folder, and "Assignment 3B" for transform coding, held
in the `Assignment 5` folder — the folder numbering and internal assignment
numbering do not match, this index maps between them.)

## How to run any implementation
Each `implementation/` subfolder has its own `README.md` with exact run
instructions. In general:
```bash
cd "Assignment N/implementation"
pip install numpy pillow matplotlib --break-system-packages   # only where needed
python3 <script_name>.py
```
All scripts are self-contained (synthetic/deterministic test data where an
image or number was not supplied), reproducible, and print/save the results
referenced in that assignment's `Report.docx`.

## Summary of key results
- **Assignment 1**: Bandwidth = 8 bps (Q1); Image B needs 2x the storage of
  Image A (Q2); Huffman coding of the contact-number-derived message
  achieves 20 bits vs 30 bits fixed-length (1.5x compression) (Q3).
- **Assignment 2**: Confirms Huffman's generalization to D-ary codes (D >= 2)
  by reproducing the paper's own D=4 example exactly, then building a
  working ternary (D=3) Huffman coder.
- **Assignment 3**: RLE achieves ~5x compression on a realistic bilevel
  document-style image; DPCM demonstrated lossless (bit-exact) vs lossy
  (quantized-residual, MSE grows with quantizer step size) reconstruction.
- **Assignment 4**: 16 points from the Wallace JPEG paper not typically
  covered in introductory lectures, backed by a working Baseline-style
  JPEG encoder/decoder (20x compression, PSNR 38.5 dB at standard
  quantization).
- **Assignment 5**: DCT consistently outperforms DFT at every tested
  coefficient-retention budget (e.g. K=16/64: DCT PSNR 24.8 dB vs DFT
  21.1 dB), confirming DCT's superior energy compaction for image data —
  the reason JPEG uses DCT rather than DFT.

## Assumptions / personalization
- Assignment 1 Q3 uses the contact number `0703888598` (as provided by the
  student) for the Huffman coding example.
- Synthetic test images/signals were generated where the assignment did not
  supply source data (Assignments 4 and 5), documented in each script.

## Author
Saurabh (jcs253011@iitd.ac.in)
