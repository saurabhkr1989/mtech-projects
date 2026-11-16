"""
config.py -- Single source of truth for all tunable parameters.

Every magic number in the system lives here. To tune the system,
edit only this file. No other module should contain hard-coded values.
"""

import os

# ---------------------------------------------------------------------------
# Cryptographic parameters
# ---------------------------------------------------------------------------

# Degree of the encoding polynomial P(x) -- fixed at 8 by the assignment 
POLYNOMIAL_DEGREE = 8

# The secret key we are protecting, in bits
SECRET_KEY_BITS = 128

# Each polynomial coefficient is a 16-bit GF(2^16) element
COEFFICIENT_BITS = 16

# Number of polynomial coefficients = degree + 1  (c0 through c8)
NUM_POLY_COEFFICIENTS = POLYNOMIAL_DEGREE + 1  # 9

# Number of 16-bit data symbols that make up the raw secret
RS_DATA_SYMBOLS = SECRET_KEY_BITS // COEFFICIENT_BITS  # 8

# Total RS codeword length = data symbols + parity symbols
RS_TOTAL_SYMBOLS = NUM_POLY_COEFFICIENTS  # 9

# Derived: how many parity (error-correction) symbols the RS code adds
RS_PARITY_SYMBOLS = RS_TOTAL_SYMBOLS - RS_DATA_SYMBOLS  # 1

# Number of chaff points added to the vault (minimum 200 per assignment specs)
VAULT_CHAFF_POINTS = 0

# Search neighborhood radius for minutiae matching (balanced for stability)
VAULT_MATCHING_RADIUS = 3

# ---------------------------------------------------------------------------
# Galois Field GF(2^16)
# ---------------------------------------------------------------------------

GF_FIELD_SIZE = 2 ** 16  # 65536

# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------

GABOR_FILTER_ORIENTATIONS = 8
GABOR_FILTER_FREQUENCY = 0.1
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID_SIZE = (8, 8)
MIN_MINUTIAE_COUNT = NUM_POLY_COEFFICIENTS  # 9
BORDER_EXCLUSION_MARGIN_PX = 20
VERIFICATION_MATCHING_THRESHOLD = 11
SPUR_PRUNE_LENGTH = 20
MIN_MINUTIAE_PAIR_DIST = 15

# ---------------------------------------------------------------------------
# Quantization
# ---------------------------------------------------------------------------

QUANTIZATION_MAX_VALUE = 255  # 8-bit: [0, 255]
# --- Quantization and Radius ---
QUANTIZATION_STEP = 1
NEIGHBORHOOD_RADIUS = 15

# --- Multi-Alignment ---
MAX_CORE_CANDIDATES = 2

# ---------------------------------------------------------------------------
# Lagrange decoding
# ---------------------------------------------------------------------------

MAX_LAGRANGE_CANDIDATES = 20
MAX_LAGRANGE_COMBINATIONS_TO_TRY = 50000

# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

# Dataset root: normalize path from modules/utilities/ to project root/Dataset
_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))  # modules/utilities/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_CONFIG_DIR))  # project root
DATASET_ROOT = os.path.join(_PROJECT_ROOT, "Dataset")

DATABASES = {
    "FVC2002_DB1": {
        "subdir": "FVC2002_DB1",
        "num_impressions": 2,
        "num_impressions_for_evaluation": 2,
    },
    "FVC2002_DB2": {
        "subdir": "FVC2002_DB2",
        "num_impressions": 2,
        "num_impressions_for_evaluation": 2,
    },
    "FVC2004_DB1": {
        "subdir": "FVC2004_DB1",
        "num_impressions": 2,
        "num_impressions_for_evaluation": 2,
    },
}

# ---------------------------------------------------------------------------
# Evaluation protocol
# ---------------------------------------------------------------------------

ENROLLMENT_IMPRESSION = 1
GENUINE_PROBE_IMPRESSION = 2
IMPOSTOR_PROBE_IMPRESSION = 1

NUM_GENUINE_COMPARISONS_SUBSET   = 10
NUM_IMPOSTOR_COMPARISONS_SUBSET  = 45

# ---------------------------------------------------------------------------
# Output directories
# ---------------------------------------------------------------------------

# Output root: use project root
OUTPUT_ROOT = os.path.join(_PROJECT_ROOT, "outputs")
METRICS_OUTPUT_DIR = os.path.join(OUTPUT_ROOT, "metrics")
PLOTS_OUTPUT_DIR = os.path.join(OUTPUT_ROOT, "plots")
STEP_VISUALS_OUTPUT_DIR = os.path.join(OUTPUT_ROOT, "step_visuals")
