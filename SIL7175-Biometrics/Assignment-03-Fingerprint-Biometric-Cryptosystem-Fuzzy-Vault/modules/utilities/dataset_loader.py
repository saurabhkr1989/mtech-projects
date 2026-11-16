"""
dataset_loader.py - FVC Fingerprint Dataset Management

This module handles loading FVC2002 and FVC2004 fingerprint datasets and
generating evaluation pair sets for 1-vs-1 matching protocol.

FVC Dataset Structure
=====================
The FVC (Fingerprint Verification Competition) datasets contain fingerprints
from multiple subjects, each with multiple impressions captured on different
occasions or sessions.

Naming Convention
-----------------
FVC files follow a consistent naming pattern: {subject_id}_{impression_id}.tif

  - subject_id: Integer from 1-100 (identifies unique person)
  - impression_id: Integer from 1-8 (different capture instances, same finger)
  - Extension: .tif (Tagged Image Format)

Examples:
  - 001_1.tif: Subject 1, first impression
  - 001_8.tif: Subject 1, eighth impression
  - 100_1.tif: Subject 100, first impression

Directory Structure
-------------------
Expected layout (configured via config.DATASET_ROOT):

  Dataset/
    FVC2002_DB1/
      1_1.tif, 1_2.tif, ..., 1_8.tif
      2_1.tif, 2_2.tif, ..., 2_8.tif
      ...
      100_1.tif, 100_2.tif, ..., 100_8.tif
    FVC2002_DB2/
      [same structure]
    FVC2004_DB1/
      [same structure]

Total: 3 databases × 100 subjects × 8 impressions = 2,400 fingerprint images

Evaluation Protocol (1-vs-1 Matching)
======================================
The assignment mandates the 1-vs-1 protocol: each subject's enrollment comes
from one impression, and verification uses a different impression.

Genuine Pairs (100 per database):
  Purpose: Measure system's ability to recognize authorized users
  Pair composition: (enrollment_image, probe_from_same_subject)

  For each subject i from 1 to 100:
    Enrollment: Subject i, impression 1
    Probe:      Subject i, impression 2
    Pair:       (i_1.tif, i_2.tif)

  Total: 100 genuine pairs per database
  Expected outcome: Most pairs should MATCH (open the vault)

Impostor Pairs (4,950 per database):
  Purpose: Measure system's security against false acceptance
  Pair composition: (enrollment_from_subject_i, probe_from_different_subject_j)

  For all unordered pairs (i, j) where i < j, with 1 ≤ i,j ≤ 100:
    Enrollment: Subject i, impression 1
    Probe:      Subject j, impression 1
    Pair:       (i_1.tif, j_1.tif)

  Total: C(100, 2) = 100×99/2 = 4,950 impostor pairs per database
  Expected outcome: Most pairs should NOT MATCH (vault stays locked)

Metrics Computed
================
From 100 genuine + 4,950 impostor pairs:
  - GAR: How many genuine pairs matched (goal: maximize, ~95%)
  - FAR: How many impostor pairs wrongly matched (goal: minimize, <1%)
  - EER: Geometric mean of error rates (lower is better, goal: <1%)

This Protocol Ensures
- Realistic evaluation: Multiple impressions capture sensor and presentation variation
- Security measurement: Large impostor set (4,950) provides solid FAR estimate
- Fairness: Same enrollment/probe procedure for all subjects
"""

import os
import sys
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.utilities import config
from modules.utilities.logger import log_section, log_step, log_data, log_warning, log_error

# Image formats recognised when scanning a database directory.
# Add entries here to support additional formats without touching any other code.
SUPPORTED_EXTENSIONS = (".tif", ".tiff", ".jpg", ".jpeg", ".bmp", ".png")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_database(database_name: str) -> dict[int, list[str]]:
    """
    Load one FVC database and return a mapping from subject ID to image paths.

    Parameters
    ----------
    database_name : Key from config.DATABASES, e.g. "FVC2002_DB1".

    Returns
    -------
    subject_to_impressions : dict mapping subject_id (int) ->
                             list of 8 absolute image paths, sorted by impression index.
                             subject_to_impressions[1][0] = path to subject 1, impression 1
                             subject_to_impressions[1][1] = path to subject 1, impression 2
                             ... etc.

    Raises
    ------
    KeyError      : If database_name is not in config.DATABASES.
    FileNotFoundError : If the database directory does not exist.
    """
    log_section(f"Loading dataset: {database_name}")

    if database_name not in config.DATABASES:
        raise KeyError(
            f"Unknown database '{database_name}'. "
            f"Valid names: {list(config.DATABASES.keys())}"
        )

    db_config = config.DATABASES[database_name]
    database_directory = os.path.join(config.DATASET_ROOT, db_config["subdir"])

    if not os.path.isdir(database_directory):
        raise FileNotFoundError(
            f"Dataset directory not found: {database_directory}\n"
            f"Please download the FVC datasets and place them under "
            f"DATASET_ROOT = '{config.DATASET_ROOT}' as described in main.py."
        )

    log_step(f"Directory: {database_directory}")

    num_impressions = db_config["num_impressions"]
    # For evaluation, only warn about missing impressions needed for 1-vs-1 protocol
    num_impressions_needed = db_config.get("num_impressions_for_evaluation", num_impressions)

    # Auto-discover subject IDs by scanning for fingerprint image files.
    # Works for both the 10-subject "B" subset (IDs 101-110) and the
    # full 100-subject "A" set (IDs 1-100) without any config change.
    discovered_subject_ids = set()
    for filename in os.listdir(database_directory):
        name, ext = os.path.splitext(filename)
        if ext.lower() in SUPPORTED_EXTENSIONS:
            parts = name.split("_")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                discovered_subject_ids.add(int(parts[0]))

    if not discovered_subject_ids:
        log_warning(f"No supported image files found in {database_directory}")
        log_warning(f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
        return {}

    log_data("Auto-discovered subject IDs", sorted(discovered_subject_ids))

    subject_to_impressions: dict[int, list[str]] = {}
    missing_file_count = 0

    for subject_id in sorted(discovered_subject_ids):
        impression_paths = []
        for impression_id in range(1, num_impressions + 1):
            # Try each supported extension to find the actual file
            found_path = None
            for ext in SUPPORTED_EXTENSIONS:
                candidate = os.path.join(database_directory, f"{subject_id}_{impression_id}{ext}")
                if os.path.isfile(candidate):
                    found_path = candidate
                    break

            if found_path is None:
                if impression_id <= num_impressions_needed:
                    log_warning(f"Missing: {subject_id}_{impression_id}.*")
                missing_file_count += 1
                impression_paths.append(None)
            else:
                impression_paths.append(found_path)

        subject_to_impressions[subject_id] = impression_paths

    log_data("Subjects loaded", len(subject_to_impressions))
    if num_impressions_needed < num_impressions:
        log_data("Missing files (required for evaluation)",
                 sum(1 for sid, paths in subject_to_impressions.items()
                     if any(p is None for p in paths[:num_impressions_needed])))

    return subject_to_impressions


def get_genuine_pairs(
    subject_to_impressions: dict[int, list[str]],
) -> list[tuple[str, str]]:
    """
    Build the list of 100 genuine (enrollment, probe) image path pairs.

    Enrollment = impression 1 (index 0)
    Probe      = impression 2 (index 1)

    Skips any subject where either image is missing (with a warning).

    Returns
    -------
    genuine_pairs : List of (enrollment_path, probe_path) tuples.
    """
    n = len(subject_to_impressions)
    log_step(f"Building genuine pairs (impression 1 vs impression 2) — {n} subjects")

    enrollment_impression_index = config.ENROLLMENT_IMPRESSION - 1   # 0-based
    genuine_probe_impression_index = config.GENUINE_PROBE_IMPRESSION - 1

    genuine_pairs = []

    for subject_id, impression_paths in sorted(subject_to_impressions.items()):
        enrollment_path = impression_paths[enrollment_impression_index]
        probe_path      = impression_paths[genuine_probe_impression_index]

        if enrollment_path is None or probe_path is None:
            log_warning(f"Subject {subject_id}: skipping genuine pair (missing image)")
            continue

        genuine_pairs.append((enrollment_path, probe_path))

    log_data("Genuine pairs built", len(genuine_pairs))
    return genuine_pairs


def get_impostor_pairs(
    subject_to_impressions: dict[int, list[str]],
) -> list[tuple[str, str]]:
    """
    Build all impostor (enrollment, probe) image path pairs.

    For each unordered pair of subjects {i, j} where i < j:
        Enrollment = impression 1 of subject i
        Probe      = impression 1 of subject j

    The total count is C(n, 2) = n*(n-1)/2, where n is the number of subjects.
    Skips any pair where either image is missing.

    Returns
    -------
    impostor_pairs : List of (enrollment_path, impostor_probe_path) tuples.
    """
    n = len(subject_to_impressions)
    expected_pairs = n * (n - 1) // 2
    log_step(f"Building impostor pairs  (C({n},2) = {expected_pairs} pairs)")

    enrollment_impression_index = config.ENROLLMENT_IMPRESSION - 1        # 0-based
    impostor_probe_impression_index = config.IMPOSTOR_PROBE_IMPRESSION - 1

    all_subject_ids = sorted(subject_to_impressions.keys())

    impostor_pairs = []

    for subject_i_id, subject_j_id in combinations(all_subject_ids, 2):
        enrollment_path = subject_to_impressions[subject_i_id][enrollment_impression_index]
        impostor_probe_path = subject_to_impressions[subject_j_id][impostor_probe_impression_index]

        if enrollment_path is None or impostor_probe_path is None:
            continue  # silently skip -- missing files already warned in load_database

        impostor_pairs.append((enrollment_path, impostor_probe_path))

    log_data("Impostor pairs built", len(impostor_pairs))
    return impostor_pairs
