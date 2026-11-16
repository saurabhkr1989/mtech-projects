# Chaff-Free Fuzzy Vault: Fingerprint Biometric Cryptosystem

A secure fingerprint-based authentication system using minutiae quantization, Reed-Solomon error correction, and polynomial-based vault encoding for biometric template protection.

**Assignment:** SIL7175 - Fingerprint-Based Biometric Cryptosystem (Assignment 3)

## System Overview

This implementation creates a **fuzzy vault** that protects a 128-bit secret using fingerprint biometrics. The system does not store original fingerprints or patterns, instead:

- Extracts ridge minutiae and aligns them using PCA
- Quantizes coordinates into an 8-bit grid (256×256 position space)
- Encodes the secret into polynomial coefficients via Reed-Solomon (RS)
- Stores vault: encrypted points derived from minutiae positions
- Recovers the secret during verification through Lagrange interpolation

## Key Algorithms

| Component | Method | Details |
|-----------|--------|---------|
| Enhancement | Gabor Filter Bank | 8 orientations, frequency 0.1 |
| Thinning | Zhang-Suen | 1-pixel ridge skeleton |
| Singular Point | Orientation-Coherence | Core point detection via local consistency |
| Feature Extraction | Minutiae | Ridge endings and bifurcations |
| Alignment | PCA | Rotation-invariant coordinate frame |
| Quantization | 8-Bit Grid | 256×256 position space, 16-angle buckets |
| Vault Encoding | Polynomial Evaluation | 8 coefficients, GF(2^16) arithmetic |
| Error Correction | Reed-Solomon | RS(9,8) over GF(2^16) |
| Secret Recovery | Lagrange Interpolation | Reconstruct polynomial from matched points |

## Installation

### Prerequisites
- Python 3.8+
- OpenCV, NumPy, SciPy, Matplotlib
- Optional: CUDA-compatible GPU for Numba JIT compilation

### Setup

```bash
git clone <repository>
cd BIO-A3
pip install -r requirements.txt
```

### Dataset Download (Optional)

For full evaluation, download fingerprint databases:

1. **FVC2002**: http://bias.csr.unibo.it/fvc2002/
2. **FVC2004**: http://bias.csr.unibo.it/fvc2004/

Extract to `Dataset/` directory:
```
Dataset/
  FVC2002_DB1/    (100 subjects × 8 impressions)
  FVC2002_DB2/
  FVC2004_DB1/
```

File naming: `{subject_id}_{impression_id}.tif` (e.g., `001_1.tif`)

## Usage

### 1. Enroll Single Image with Visualization

```bash
python enroll_image.py path/to/fingerprint.tif
```

Outputs:
- Step-by-step visualizations (original → segmented → enhanced → skeleton → singular point → quantized grid)
- CSV with enrollment parameters
- JSON vault file for verification
- All saved with database/image name prefixes

### 2. Match Two Fingerprints

```bash
python match_images.py enrolled.tif probe.tif
```

Outputs:
- GENUINE/IMPOSTOR decision with confidence metrics
- Match ratio (matched points / vault size)
- Lagrange combination count
- Side-by-side comparison image
- Detailed JSON results with all statistics

### 3. Full Database Evaluation

```bash
python main.py --mode evaluate --database FVC2002_DB2
```

Computes:
- **GAR** (Genuine Acceptance Rate): % of genuine pairs accepted
- **FAR** (False Acceptance Rate): % of impostor pairs accepted
- **EER** (Equal Error Rate): intersection of GAR and FRR curves
- ROC curves and performance tables

### 4. Interactive Mode

```bash
python main.py --mode interactive
```

Menu-driven interface for all operations.

## Pipeline Architecture

### Enrollment Pipeline

1. **Load & Preprocess**
   - Load grayscale image
   - Segment foreground (block variance method)

2. **Enhancement**
   - Gabor filter bank (8 orientations)
   - Ridge skeleton via Zhang-Suen thinning

3. **Feature Detection**
   - Estimate orientation map
   - Detect singular point (core) via orientation coherence
   - Extract minutiae (ridge endpoints and bifurcations)
   - Spurious minutiae removal (clustering)

4. **Normalization**
   - PCA-based rotation alignment
   - Scale normalization (ridge frequency matching)
   - Quantize to 8-bit grid (256×256, 16 angle buckets)

5. **Cryptographic Encoding**
   - Generate 128-bit random secret
   - RS-encode into 9 polynomial coefficients (GF(2^16))
   - Evaluate polynomial at minutiae positions
   - Build vault: (u_i, v_i, P(v_i)) triples
   - Add chaff points for security (200+ noise points)

6. **Output**
   - Vault points (public index, private evaluation point, polynomial value)
   - Secret key hash (SHA-256)
   - PCA matrix and singular point (for alignment)
   - Ridge frequency (for scale normalization)

### Verification Pipeline

1. **Probe Preprocessing**
   - Same steps as enrollment (load, enhance, thin, detect features)
   - Multi-core retry: test multiple core candidates for robustness

2. **Feature Matching**
   - 6-bit grid matching (±16 pixel tolerance)
   - Angle-bucket matching (±1 bucket, with 180° flip option)
   - Quality-based sort key: d² × 10 + |Δθ| + flip_penalty

3. **Lagrange Interpolation**
   - Select top 20 candidate matches
   - Try all C(20,9) combinations up to 50,000 tries
   - Reconstruct polynomial coefficients

4. **Hash Verification**
   - RS-decode recovered polynomial
   - Compute SHA-256 hash
   - Compare to enrolled secret hash
   - Decision: GENUINE if hashes match, IMPOSTOR otherwise

## Output Files

All outputs include database name and image name as file prefixes.

### Enrollment Outputs
```
outputs/enrollments/{timestamp}/
  ├── 01_original_grayscale.png
  ├── 02_foreground_mask.png
  ├── 03_gabor_enhanced.png
  ├── 04_thinned_skeleton.png
  ├── 05_singular_point_detected.png
  ├── 06_quantized_grid.png
  ├── enrollment_details.csv
  └── {image_name}_vault.json
```

### Matching Outputs
```
outputs/matches/{timestamp}/
  ├── comparison_images.png
  ├── matching_result.csv
  └── matching_details.json
```

### Evaluation Outputs
```
outputs/plots/
  ├── {DATABASE_NAME}_roc_curve.png
  ├── combined_roc_curves.png
  └── results_summary.png

outputs/metrics/
  └── evaluation_results.csv
```

## Performance Metrics

Expected on FVC databases:

| Database | GAR (%) | FAR (%) | EER (%) |
|----------|---------|---------|---------|
| FVC2002_DB1 | 50-70 | 10-30 | 20-40 |
| FVC2002_DB2 | 50-70 | 10-30 | 20-40 |
| FVC2004_DB1 | 50-70 | 10-30 | 20-40 |

*Note: Performance depends on vault size (minutiae extraction quality), chaff count, and database image quality.*

## Configuration

Edit `config.py` to tune system parameters:

```python
POLYNOMIAL_DEGREE = 8              # Lagrange requires 9 points
SECRET_KEY_BITS = 128              # Secret key length
VAULT_CHAFF_POINTS = 200           # Security: confuse impostors
VAULT_MATCHING_RADIUS = 3          # Grid tolerance (pixels)
MAX_LAGRANGE_COMBINATIONS_TO_TRY = 50000  # Search limit
```

## Project Structure

```
BIO-A3/
├── main.py                    # CLI entry point
├── enroll_image.py           # Single image enrollment with visualization
├── match_images.py           # Two-image matching with detailed output
├── quick_test.py             # Quick FAR/GAR validation
├── config.py                 # Tunable parameters
├── Dataset/                  # Fingerprint databases
├── modules/
│   ├── m01_image_preprocessing.py
│   ├── m03_minutiae_processor.py
│   ├── m04_improved_singularity_point.py
│   ├── m04_feature_normalization.py
│   ├── m06_cryptographic_codec.py
│   ├── m09_vault_encoder.py
│   ├── m10_vault_decoder.py
│   └── utilities/
│       ├── visualizer.py
│       ├── logger.py
│       └── ...
└── outputs/                  # Generated results

```

## Key Files Description

- **m09_vault_encoder.py**: Enrollment pipeline, vault construction
- **m10_vault_decoder.py**: Verification pipeline, Lagrange interpolation
- **m06_cryptographic_codec.py**: Reed-Solomon encoding/decoding, polynomial operations
- **m04_improved_singularity_point.py**: Core point detection via orientation coherence
- **m04_feature_normalization.py**: PCA alignment, scale normalization, quantization

## Testing

Run validation tests:

```bash
# Quick test on one database
python quick_test.py FVC2002_DB2

# Full evaluation on all databases
python main.py --mode evaluate

# Test specific image pair
python match_images.py image1.tif image2.tif
```

## References

- Juels & Sudan. "A Fuzzy Vault Scheme." (2002)
- FVC (Fingerprint Verification Competition): http://bias.csr.unibo.it/
- GF(2^16) Reed-Solomon codes for error correction
- PCA for rotation-invariant biometric alignment

## License

Assignment submission for SIL7175 (2024)

## Contact

For questions regarding this implementation, contact the assignment instructor.
