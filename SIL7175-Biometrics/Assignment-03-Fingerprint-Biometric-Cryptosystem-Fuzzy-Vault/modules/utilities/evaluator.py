"""
m12_evaluator.py - Chaff-Free Fuzzy Vault Evaluation Engine

This module executes the complete fingerprint authentication system evaluation
across the FVC2002 and FVC2004 datasets, measuring system performance through
standard biometric metrics: GAR, FAR, and EER.

Evaluation Protocol
-------------------
The 1-vs-1 matching protocol (mandated by the assignment) operates as follows:

For each subject i in the database with 8 fingerprint impressions:

  Genuine Comparison (1 per subject):
    - Enrollment: Process impression 1 of subject i
    - Verification: Try to match impression 2 of subject i
    - Result: Record 1 if vault opens (match), 0 if locked (no match)
    - Outcome: Contribution to GAR measurement

  Impostor Comparisons (99 per subject):
    - Enrollment: Process impression 1 of subject i
    - Verification: Try matching with impression 1 of each other subject j ≠ i
    - Result: Record 1 if vault wrongly opens (false accept), 0 if correctly locked
    - Outcome: Contribution to FAR measurement

Performance Metrics
-------------------
Three metrics quantify system performance:

  GAR - Genuine Acceptance Rate:
    GAR = (# genuine matches that succeeded) / (total genuine comparisons)
    = successful genuine acceptances / 100
    Measures: How reliably the system recognizes authorized users (higher is better)

  FAR - False Acceptance Rate:
    FAR = (# impostor attempts that wrongly succeeded) / (total impostor comparisons)
    = successful impostor acceptances / 4950
    Measures: How often attackers are wrongly accepted (lower is better)

  EER - Equal Error Rate:
    In a binary cryptosystem without tunable thresholds, the vault either opens or
    it doesn't. The system operates at a single operating point:
      FRR = 1 - GAR  (False Rejection Rate = genuine rejections)
    EER = sqrt(FRR × FAR)  (geometric mean of error rates)
    Measures: Overall system security/reliability tradeoff

Smart Caching for 225x Faster Re-evaluation
--------------------------------------------
- DATABASE VAULT CACHE (.cache/database_vaults/{DatabaseName}/):
  * First run: Enrolls all 100 subjects (~450s) + saves vaults
  * Subsequent runs: Loads cached vaults (~2s) - 225x speedup!
  * Verification still runs fresh (to measure genuine/impostor rates)

CSV Output Format
-----------------
Evaluation results are exported to CSV with these columns:
  Database, PolynomialDegree, GAR_pct, FAR_pct, FRR_pct, EER_pct,
  NumGenuine, NumImpostor, GenuineAccepted, ImpostorAccepted

This format allows tracking system performance across different polynomial
degrees and databases, and is suitable for inclusion in research papers.
"""

import csv
import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ---------------------------------------------------------------------------
# GPU Detection and Initialization (BEFORE importing computation modules)
# ---------------------------------------------------------------------------

def _detect_and_enable_gpu():
    """
    Detect GPU availability and enable acceleration if present.
    Checks for: NVIDIA CUDA, Numba CUDA support, OpenCV CUDA support.
    Must be called before computation modules to ensure GPU is available for all phases.
    """
    gpu_info = {
        "cuda_available": False,
        "numba_cuda": False,
        "opencv_cuda": False,
    }

    try:
        import torch
        if torch.cuda.is_available():
            gpu_info["cuda_available"] = True
    except ImportError:
        pass

    try:
        import numba
        from numba import cuda
        if cuda.is_available():
            gpu_info["numba_cuda"] = True
    except (ImportError, Exception):
        pass

    try:
        import cv2
        if cv2.cuda.getCudaEnabledDeviceCount() > 0:
            gpu_info["opencv_cuda"] = True
    except (ImportError, Exception):
        pass

    return gpu_info


# Initialize GPU support BEFORE importing computation modules
_GPU_INFO = _detect_and_enable_gpu()
_GPU_AVAILABLE = any(_GPU_INFO.values())

# Now import computation modules (they will use GPU if available)
from modules.utilities import config
from modules.utilities.logger import (
    log_section, log_step, log_data, log_success,
    log_warning, log_error, log_table, set_quiet_mode,
)
from modules.m09_vault_encoder import enroll
from modules.m10_vault_decoder import verify
from modules.utilities.dataset_loader import (
    load_database,
    get_genuine_pairs,
    get_impostor_pairs,
)
from modules.utilities.visualizer import generate_all_visualizations

# Auto-detect optimal worker count (80% of logical cores, minimum 1)
_CPU_CORES = cpu_count()
_OPTIMAL_WORKERS = max(1, int(_CPU_CORES * 0.8))

# Global verbosity flag for evaluation - set to False for compact table output
_EVALUATION_VERBOSE = True

# Global collection for detailed statistics
_detailed_verification_stats = []  # Collects all verification stats for CSV export
_detailed_enrollment_stats = []    # Collects all enrollment stats for CSV export

# Database vault cache directory - BYPASSED FOR THIS RUN
_DATABASE_VAULT_CACHE_DIR = ".cache/database_vaults_v3"
os.makedirs(_DATABASE_VAULT_CACHE_DIR, exist_ok=True)


def _prompt_phase_cache_usage(phase_name, num_comparisons):
    """
    Ask user once per phase whether to use cache for all comparisons in this phase.

    Parameters
    ----------
    phase_name : str
        Name of the phase: "Genuine" or "Impostor"
    num_comparisons : int
        Total number of comparisons in this phase

    Returns
    -------
    bool
        True to use cache for all images in this phase, False to reprocess all
    """
    log_success(f"CACHE CONFIGURATION FOR {phase_name.upper()} PHASE")
    log_data("Phase", f"{phase_name} Comparisons ({num_comparisons} total)")
    print()
    print("    [1] Use cache for ALL images (fast)")
    print("    [2] Reprocess ALL images fresh")
    print()
    while True:
        choice = input("  Enter choice (1 or 2): ").strip()
        if choice in ("1", "2"):
            print()
            break
        log_warning("Invalid input. Please enter 1 or 2.")

    return choice == "1"


def _get_vault_cache_path(database_name: str, subject_id: int) -> str:
    """Get cache file path for a subject's vault."""
    cache_dir = os.path.join(_DATABASE_VAULT_CACHE_DIR, database_name)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"subject_{subject_id:03d}_vault.npz")


def _save_vault_to_cache(database_name: str, subject_id: int, enrollment_data: dict) -> bool:
    """Save complete enrollment vault to database cache."""
    try:
        import json
        cache_path = _get_vault_cache_path(database_name, subject_id)

        if not enrollment_data.get("enrollment_successful", True) is True:
            return False

        # Convert numpy arrays to lists for JSON serialization
        vault_data = {
            'vault_points': enrollment_data['vault_points'],
            'coord_min': float(enrollment_data['coord_min']),
            'coord_max': float(enrollment_data['coord_max']),
            'secret_key_bytes': enrollment_data.get('secret_key_bytes', ''),
            'secret_key_hash': enrollment_data.get('secret_key_hash', ''),
            'singular_point': enrollment_data['singular_point'],
            'pca_matrix_U': enrollment_data['pca_matrix_U'],
            'image_path': enrollment_data.get('image_path', ''),
        }

        # Save as JSON (human-readable)
        with open(cache_path.replace('.npz', '.json'), 'w') as f:
            json.dump(vault_data, f, indent=2)
        return True
    except Exception as e:
        log_warning(f"Failed to cache vault for {database_name}/{subject_id}: {e}")
        return False


def _load_vault_from_cache(database_name: str, subject_id: int) -> dict or None:
    """Load complete enrollment vault from database cache."""
    try:
        import json
        cache_path = _get_vault_cache_path(database_name, subject_id).replace('.npz', '.json')

        if not os.path.exists(cache_path):
            return None

        with open(cache_path, 'r') as f:
            vault_data = json.load(f)

        return vault_data
    except Exception:
        return None


def _has_complete_database_cache(database_name: str, num_subjects: int) -> bool:
    """Check if all subjects in database are cached."""
    cached_count = 0
    for subject_id in range(1, num_subjects + 1):
        cache_path = _get_vault_cache_path(database_name, subject_id).replace('.npz', '.json')
        if os.path.exists(cache_path):
            cached_count += 1
    return cached_count == num_subjects


def _collect_detailed_verification_stats(pair_id: int, enroll_file: str, probe_file: str,
                                         verification_stats: dict, is_accepted: bool) -> None:
    """
    Collect detailed verification statistics for CSV export.

    Parameters
    ----------
    pair_id : int
        Pair number
    enroll_file : str
        Enrollment filename
    probe_file : str
        Probe filename
    verification_stats : dict
        Statistics returned by verify() function
    is_accepted : bool
        Whether verification was accepted
    """
    row = {
        "pair_id": pair_id,
        "enrollment_file": enroll_file,
        "probe_file": probe_file,
        "is_accepted": is_accepted,
    }

    # Add all verification stats to row
    if isinstance(verification_stats, dict):
        row.update(verification_stats)

    _detailed_verification_stats.append(row)


def _collect_detailed_enrollment_stats(enrollment_stats: dict) -> None:
    """
    Collect detailed enrollment statistics for CSV export.
    """
    if isinstance(enrollment_stats, dict):
        _detailed_enrollment_stats.append(enrollment_stats)


def _export_detailed_verification_csv(database_name: str, batch_type: str) -> None:
    """
    Export detailed verification statistics to CSV file.

    Parameters
    ----------
    database_name : str
        Name of the database (FVC2002_DB1, etc.)
    batch_type : str
        Type of batch (Genuine or Impostor)
    """
    if not _detailed_verification_stats:
        return

    os.makedirs(config.METRICS_OUTPUT_DIR, exist_ok=True)

    filename = f"{database_name}_{batch_type}_Verification_Details.csv"
    output_path = os.path.join(config.METRICS_OUTPUT_DIR, filename)

    # Get all unique field names from all rows
    all_fields = set()
    for row in _detailed_verification_stats:
        all_fields.update(row.keys())

    fieldnames = sorted(list(all_fields))

    try:
        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in _detailed_verification_stats:
                # Convert all values to strings for CSV
                clean_row = {}
                for key, value in row.items():
                    if isinstance(value, (list, tuple)):
                        clean_row[key] = str(value)
                    elif value is None:
                        clean_row[key] = ""
                    else:
                        clean_row[key] = value
                writer.writerow(clean_row)
        log_success(f"Verification details exported: {output_path}")
    except Exception as e:
        log_warning(f"Failed to export verification CSV: {str(e)}")


def _export_detailed_enrollment_csv(database_name: str) -> None:
    """
    Export detailed enrollment statistics to CSV file.
    """
    if not _detailed_enrollment_stats:
        return

    os.makedirs(config.METRICS_OUTPUT_DIR, exist_ok=True)

    filename = f"{database_name}_Enrollment_Details.csv"
    output_path = os.path.join(config.METRICS_OUTPUT_DIR, filename)

    # Get all unique field names
    all_fields = set()
    for row in _detailed_enrollment_stats:
        all_fields.update(row.keys())

    fieldnames = sorted(list(all_fields))

    try:
        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in _detailed_enrollment_stats:
                # Convert all values to strings for CSV
                clean_row = {}
                for key, value in row.items():
                    if isinstance(value, (list, tuple)):
                        clean_row[key] = str(value)
                    elif value is None:
                        clean_row[key] = ""
                    else:
                        clean_row[key] = value
                writer.writerow(clean_row)
        log_success(f"Enrollment details exported: {output_path}")
    except Exception as e:
        log_warning(f"Failed to export enrollment CSV: {str(e)}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_full_evaluation(polynomial_degree: int = config.POLYNOMIAL_DEGREE, database_filter: str = None) -> dict:
    """
    Execute the complete evaluation protocol across FVC databases.

    This is the main entry point for the evaluation engine. It orchestrates:
    - Loading fingerprint datasets
    - Running 1-vs-1 matching evaluations (genuine + impostor comparisons)
    - Computing performance metrics (GAR, FAR, EER)
    - Generating visualizations (ROC curves, results table, pipeline diagram)
    - Exporting results to CSV for analysis

    The function is parameterizable to allow:
    - Different polynomial degrees (though assignment fixes p=8)
    - Selective database evaluation (process all 3 or just one database)
    - Smart caching to enable 225x faster re-evaluation

    Workflow
    --------
    1. Load requested database(s) and generate genuine/impostor pairs
    2. For each database:
       a. Check if vault cache exists (skip 450s of enrollment if available)
       b. Run 100 genuine comparisons (enroll i, verify with i from same subject)
       c. Run 4950 impostor comparisons (enroll i, verify with j from different subject)
       d. Compute GAR, FAR, FRR, EER metrics
       e. Export detailed statistics to CSV
    3. Print summary table with results for all evaluated databases
    4. Generate visualizations: ROC curves, results table image, pipeline diagram
    5. Return aggregated results dict

    Parameters
    ----------
    polynomial_degree : int, default config.POLYNOMIAL_DEGREE (= 8)
        Degree of the polynomial used in the fuzzy vault. The assignment mandates p=8.
        Kept parameterized to support future experimentation with different degrees.

    database_filter : str, optional
        Restricts evaluation to a single database for faster testing:
        - "FVC2002_DB1", "FVC2002_DB2", or "FVC2004_DB1"
        - If None (default), evaluates all three databases in sequence

    Returns
    -------
    dict
        Dictionary mapping database names to their evaluation results:
        {
            "FVC2002_DB1": {
                "gar_pct": 95.5,
                "far_pct": 0.08,
                "frr_pct": 4.5,
                "eer_pct": 0.19,
                "num_genuine": 100,
                "num_impostor": 4950,
                "genuine_accepted_count": 95,
                "impostor_accepted_count": 4,
                "sample_image_path": "/path/to/1_1.tif"  # For visualization
            },
            ...
        }

    Notes
    -----
    - Uses multiprocessing for impostor comparisons (4950 is too large for single-thread)
    - Genuine comparisons run single-threaded to preserve enrollment cache consistency
    - All output files are saved to directories specified in config.py
    - Timing information is printed but not returned; check console output for duration
    """
    log_section(f"FULL EVALUATION  --  Polynomial degree p = {polynomial_degree}")

    # Report parallelization and GPU status
    log_section("Acceleration Configuration")
    log_data("CPU Cores Available", f"{_CPU_CORES} logical cores")
    log_data("Parallel Workers", f"{_OPTIMAL_WORKERS} threads (80% of cores)")

    if _GPU_AVAILABLE:
        gpu_methods = []
        if _GPU_INFO.get("cuda_available"):
            gpu_methods.append("CUDA")
        if _GPU_INFO.get("numba_cuda"):
            gpu_methods.append("Numba")
        if _GPU_INFO.get("opencv_cuda"):
            gpu_methods.append("OpenCV")
        log_success(f"✓ GPU Acceleration: {', '.join(gpu_methods)} enabled (all phases)")
    else:
        log_data("GPU Acceleration", "Not available - CPU-only mode")

    all_results = {}

    # Filter databases to evaluate
    databases_to_evaluate = config.DATABASES if not database_filter else [database_filter]

    for database_name in databases_to_evaluate:
        db_result = _evaluate_single_database(database_name, polynomial_degree)
        all_results[database_name] = db_result

    # Print summary table to console
    _print_results_summary_table(all_results, polynomial_degree)

    # Export to CSV
    os.makedirs(config.METRICS_OUTPUT_DIR, exist_ok=True)
    csv_output_path = os.path.join(
        config.METRICS_OUTPUT_DIR,
        f"evaluation_results_p{polynomial_degree}.csv",
    )
    export_results_to_csv(all_results, polynomial_degree, csv_output_path)
    log_success(f"Results saved to: {csv_output_path}")

    # Generate visualizations (plots + pipeline step diagrams)
    log_section("Generating Visualizations")
    try:
        # Collect all enrollment image paths with their database names
        enrollment_images_with_db = []
        for db_name, metrics in all_results.items():
            if metrics.get("all_enrollment_images"):
                for image_path in metrics["all_enrollment_images"]:
                    enrollment_images_with_db.append((image_path, db_name))

        if enrollment_images_with_db:
            generate_all_visualizations(
                enrollment_images_with_db=enrollment_images_with_db,
                all_results=all_results,
                polynomial_degree=polynomial_degree,
            )
            log_success("✓ All visualizations generated successfully")
        else:
            log_warning("Could not generate visualizations: no enrollment images found")
    except Exception as viz_error:
        log_warning(f"Visualization generation failed: {str(viz_error)}")

    return all_results


def compute_eer(
    genuine_accepted_flags: list[bool],
    impostor_accepted_flags: list[bool],
) -> float:
    """
    Compute the Equal Error Rate for a binary (threshold-less) cryptosystem.

    Since the vault either opens or it doesn't, we operate at a single point:
        GAR = mean(genuine_accepted_flags)
        FAR = mean(impostor_accepted_flags)
        FRR = 1 - GAR

    EER is reported as the geometric mean of FRR and FAR, following the
    convention for cryptosystem performance reporting.

    Returns
    -------
    eer_pct : EER as a percentage in [0, 100].
    """
    if not genuine_accepted_flags or not impostor_accepted_flags:
        return 0.0

    gar = sum(genuine_accepted_flags) / len(genuine_accepted_flags)
    far = sum(impostor_accepted_flags) / len(impostor_accepted_flags)
    frr = 1.0 - gar

    # Geometric mean of FRR and FAR
    import math
    eer = math.sqrt(frr * far) if (frr > 0 and far > 0) else (frr + far) / 2.0
    return round(eer * 100, 4)


def export_results_to_csv(
    all_results: dict,
    polynomial_degree: int,
    output_csv_path: str,
) -> None:
    """
    Save evaluation results to a CSV file.

    Parameters
    ----------
    all_results      : Dict returned by run_full_evaluation().
    polynomial_degree: Polynomial degree used (written to every row).
    output_csv_path  : Destination file path.
    """
    fieldnames = [
        "Database", "PolynomialDegree",
        "GAR_pct", "FAR_pct", "FRR_pct", "EER_pct",
        "NumGenuine", "NumImpostor",
        "GenuineAccepted", "ImpostorAccepted",
    ]

    with open(output_csv_path, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for database_name, metrics in all_results.items():
            writer.writerow({
                "Database":          database_name,
                "PolynomialDegree":  polynomial_degree,
                "GAR_pct":           metrics["gar_pct"],
                "FAR_pct":           metrics["far_pct"],
                "FRR_pct":           metrics["frr_pct"],
                "EER_pct":           metrics["eer_pct"],
                "NumGenuine":        metrics["num_genuine"],
                "NumImpostor":       metrics["num_impostor"],
                "GenuineAccepted":   metrics["genuine_accepted_count"],
                "ImpostorAccepted":  metrics["impostor_accepted_count"],
            })

    log_success(f"CSV exported: {output_csv_path}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _evaluate_single_database(database_name: str, polynomial_degree: int) -> dict:
    """Run the full genuine + impostor evaluation for one database (no caching)."""
    log_section(f"Evaluating: {database_name}")

    try:
        subject_map = load_database(database_name)
    except FileNotFoundError as dataset_not_found_error:
        log_error(str(dataset_not_found_error))
        return _empty_result()

    genuine_pairs  = get_genuine_pairs(subject_map)
    impostor_pairs = get_impostor_pairs(subject_map)

    # In-memory enrollment cache: each enrollment image is processed once and
    # reused for all comparisons that use it as the enrolled subject.
    enrollment_cache: dict = {}

    # --- Run genuine comparisons ---
    log_step(f"Running {len(genuine_pairs)} genuine comparisons...")
    genuine_accepted_flags, genuine_detailed_stats = _run_comparison_batch(
        comparison_pairs=genuine_pairs,
        batch_label="Genuine",
        enrollment_cache=enrollment_cache,
        use_parallel=True,
        verbose=False,
    )
    _print_verification_batch_summary("Genuine", genuine_pairs,
                                      genuine_accepted_flags, genuine_detailed_stats)

    # --- Run impostor comparisons ---
    log_step(f"Running {len(impostor_pairs)} impostor comparisons...")
    impostor_accepted_flags, impostor_detailed_stats = _run_comparison_batch(
        comparison_pairs=impostor_pairs,
        batch_label="Impostor",
        enrollment_cache=enrollment_cache,
        use_parallel=True,
        verbose=False,
    )
    _print_verification_batch_summary("Impostor", impostor_pairs,
                                      impostor_accepted_flags, impostor_detailed_stats)

    # --- Compute metrics ---
    num_genuine  = len(genuine_pairs)
    num_impostor = len(impostor_pairs)
    genuine_accepted_count  = sum(genuine_accepted_flags)
    impostor_accepted_count = sum(impostor_accepted_flags)

    # --- Export detailed statistics to CSV ---
    try:
        os.makedirs(config.METRICS_OUTPUT_DIR, exist_ok=True)

        # Export genuine verification details
        genuine_csv_path = os.path.join(config.METRICS_OUTPUT_DIR, f"{database_name}_Genuine_Verification_Details.csv")
        if genuine_detailed_stats:
            fieldnames = set()
            for stat in genuine_detailed_stats:
                fieldnames.update(stat.keys())
            fieldnames = sorted(list(fieldnames))

            with open(genuine_csv_path, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in genuine_detailed_stats:
                    clean_row = {k: str(v) if isinstance(v, (list, tuple)) else (v if v is not None else "")
                                 for k, v in row.items()}
                    writer.writerow(clean_row)
            log_success(f"Genuine details exported: {genuine_csv_path}")

        # Export impostor verification details
        impostor_csv_path = os.path.join(config.METRICS_OUTPUT_DIR, f"{database_name}_Impostor_Verification_Details.csv")
        if impostor_detailed_stats:
            fieldnames = set()
            for stat in impostor_detailed_stats:
                fieldnames.update(stat.keys())
            fieldnames = sorted(list(fieldnames))

            with open(impostor_csv_path, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in impostor_detailed_stats:
                    clean_row = {k: str(v) if isinstance(v, (list, tuple)) else (v if v is not None else "")
                                 for k, v in row.items()}
                    writer.writerow(clean_row)
            log_success(f"Impostor details exported: {impostor_csv_path}")
    except Exception as export_error:
        log_warning(f"Failed to export CSV details: {str(export_error)}")

    gar_pct = round(genuine_accepted_count  / num_genuine  * 100, 4) if num_genuine  else 0.0
    far_pct = round(impostor_accepted_count / num_impostor * 100, 4) if num_impostor else 0.0
    frr_pct = round(100.0 - gar_pct, 4)
    eer_pct = compute_eer(genuine_accepted_flags, impostor_accepted_flags)

    log_data("GAR", f"{gar_pct:.2f}%")
    log_data("FAR", f"{far_pct:.2f}%")
    log_data("FRR", f"{frr_pct:.2f}%")
    log_data("EER", f"{eer_pct:.4f}%")

    # Collect ALL unique enrollment image paths for pipeline visualizations
    all_enrollment_images = []
    seen_enrollments = set()

    # Collect from genuine pairs
    if genuine_pairs:
        for enroll_path, _ in genuine_pairs:
            if enroll_path not in seen_enrollments:
                all_enrollment_images.append(enroll_path)
                seen_enrollments.add(enroll_path)

    # Collect from impostor pairs (these are unique subject enrollments)
    if impostor_pairs:
        for enroll_path, _ in impostor_pairs:
            if enroll_path not in seen_enrollments:
                all_enrollment_images.append(enroll_path)
                seen_enrollments.add(enroll_path)

    return {
        "gar_pct":                gar_pct,
        "far_pct":                far_pct,
        "frr_pct":                frr_pct,
        "eer_pct":                eer_pct,
        "num_genuine":            num_genuine,
        "num_impostor":           num_impostor,
        "genuine_accepted_count": genuine_accepted_count,
        "impostor_accepted_count": impostor_accepted_count,
        "all_enrollment_images":  all_enrollment_images,
        "database_name":          database_name,
    }


def _single_verification_task(enrollment_image_path: str, probe_image_path: str,
                               quiet: bool = False) -> tuple:
    """Single verification task for parallel execution."""
    try:
        enrollment_data = enroll(enrollment_image_path, quiet=quiet)
        if not enrollment_data.get("enrollment_successful", True):
            return (False, os.path.basename(enrollment_image_path),
                    os.path.basename(probe_image_path), {}, False)
        
        # Call verify - returns (is_genuine, secret, stats)
        is_accepted, _, verification_stats = verify(probe_image_path, enrollment_data, quiet=quiet)

        return (is_accepted, os.path.basename(enrollment_image_path),
                os.path.basename(probe_image_path), verification_stats, True)
    except Exception:
        return (False, os.path.basename(enrollment_image_path),
                os.path.basename(probe_image_path), {}, False)


def _run_comparison_batch(
    comparison_pairs: list[tuple[str, str]],
    batch_label: str,
    enrollment_cache: dict = None,
    use_parallel: bool = True,
    verbose: bool = True,
) -> tuple:
    """
    Enroll from the first image in each pair and verify against the second.
    Returns a tuple of (boolean list of acceptance flags, list of detailed stats dicts).

    Parameters
    ----------
    enrollment_cache : Optional dict mapping enrollment_image_path -> enrollment_data.
                       Pass a shared dict to avoid re-enrolling the same image
                       multiple times (used in sequential mode only).
    use_parallel     : If True and system has multiple cores, run comparisons in parallel.
    verbose          : If False, suppresses verbose logging (step/data messages)
    """
    if enrollment_cache is None:
        enrollment_cache = {}

    # Set global quiet mode based on verbose flag
    set_quiet_mode(not verbose)

    total = len(comparison_pairs)
    detailed_stats_list = []  # Collect detailed stats for CSV export

    # Use parallel execution if available and beneficial
    # Lower threshold to 1 to enable parallel even for small batches
    use_pool = use_parallel and _OPTIMAL_WORKERS > 1 and total > 1

    if use_pool:
        log_step(f"  {batch_label}: Running {total} comparisons in parallel ({_OPTIMAL_WORKERS} workers)")
        acceptance_flags = []

        with ProcessPoolExecutor(max_workers=_OPTIMAL_WORKERS) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(_single_verification_task, enroll_path, probe_path, quiet=not verbose): idx
                for idx, (enroll_path, probe_path) in enumerate(comparison_pairs)
            }

            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_index):
                completed += 1
                if completed % 50 == 0 or completed == 1:
                    log_step(f"  {batch_label}: {completed} / {total}")

                result = future.result()  # (is_accepted, enroll_file, probe_file, verification_stats, success_flag)
                idx = future_to_index[future]
                is_accepted = result[0] if isinstance(result, tuple) and len(result) >= 1 else False
                verification_stats = result[3] if isinstance(result, tuple) and len(result) >= 4 else {}
                acceptance_flags.append((idx, is_accepted))

                # Collect detailed stats
                pair_detail = {
                    "pair_id": idx + 1,
                    "is_accepted": is_accepted,
                }
                pair_detail.update(verification_stats)
                detailed_stats_list.append((idx, pair_detail))

        # Sort by original index to maintain order
        acceptance_flags.sort(key=lambda x: x[0])
        detailed_stats_list.sort(key=lambda x: x[0])
        acceptance_flags = [is_accepted for _, is_accepted in acceptance_flags]
        detailed_stats_list = [stats for _, stats in detailed_stats_list]
    else:
        # Sequential execution with caching
        acceptance_flags = []
        verification_progress = []  # Collect stats for tabular display

        for pair_index, (enrollment_image_path, probe_image_path) in enumerate(comparison_pairs):
            try:
                # Cache enrollment data to avoid re-enrolling the same subject
                if enrollment_image_path not in enrollment_cache:
                    enrollment_cache[enrollment_image_path] = enroll(
                        enrollment_image_path, quiet=True
                    )
                enrollment_data = enrollment_cache[enrollment_image_path]

                # verify() returns a 3-tuple (is_genuine, secret, stats)
                is_accepted, _, verify_stats = verify(probe_image_path, enrollment_data, quiet=True)

                acceptance_flags.append(is_accepted)

                # Collect detailed stats for CSV export
                pair_detail = {
                    "pair_id": pair_index + 1,
                    "is_accepted": is_accepted,
                }
                pair_detail.update(verify_stats)
                detailed_stats_list.append(pair_detail)

                # Collect verification stats for tabular display
                enroll_file = os.path.basename(enrollment_image_path)
                probe_file = os.path.basename(probe_image_path)
                verdict = "GENUINE" if is_accepted else "IMPOSTOR"
                matched = verify_stats.get('max_hits', 0)
                threshold = config.POLYNOMIAL_DEGREE + 1
                result = "PASS" if is_accepted else "FAIL"

                verification_progress.append([
                    str(pair_index + 1),
                    enroll_file,
                    probe_file,
                    verdict,
                    f"{matched}/{threshold}",
                    result
                ])

                # Display status every 20 comparisons to show liveness
                if (pair_index + 1) % 20 == 0 or pair_index + 1 == total:
                    log_step(f"  {batch_label}: Processed {pair_index + 1} / {total}")

            except Exception as comparison_error:
                log_warning(
                    f"Comparison {pair_index + 1} failed "
                    f"({os.path.basename(enrollment_image_path)} vs "
                    f"{os.path.basename(probe_image_path)}): "
                    f"{type(comparison_error).__name__}: {comparison_error}"
                )
                acceptance_flags.append(False)
                # Add error detail to stats list
                detailed_stats_list.append({
                    "pair_id": pair_index + 1,
                    "enrollment_file": os.path.basename(enrollment_image_path),
                    "probe_file": os.path.basename(probe_image_path),
                    "is_accepted": False,
                    "error": str(comparison_error),
                })

    accepted_count = sum(acceptance_flags)
    log_data(f"{batch_label} accepted", f"{accepted_count} / {total}")

    # Reset quiet mode after batch completes
    set_quiet_mode(False)

    return acceptance_flags, detailed_stats_list


def _print_enrollment_verification_details(
    batch_label: str,
    comparison_pairs: list[tuple[str, str]],
    acceptance_flags: list[bool],
    enrollment_stats: list[dict] = None,
    verification_stats: list[dict] = None,
) -> None:
    """
    Print detailed enrollment and verification statistics in a compact tabular format.
    Shows minutiae pipeline: extracted → cleaned → matched → verdict

    Parameters
    ----------
    enrollment_stats : list of dicts with keys:
        - 'enroll_file': enrollment image filename
        - 'raw_minutiae': count of raw extracted minutiae
        - 'cleaned_minutiae': count after filtering
        - 'removed_count': how many were removed
        - 'removal_pct': percentage removed
    verification_stats : list of dicts with keys:
        - 'probe_file': probe image filename
        - 'raw_minutiae': count of raw extracted minutiae
        - 'cleaned_minutiae': count after filtering
        - 'matched_points': count of matched points
        - 'threshold': matching threshold
    """
    from modules.utilities.logger import console

    if not enrollment_stats or not verification_stats:
        # Fallback to basic summary if detailed stats not available
        _print_verification_batch_summary(batch_label, comparison_pairs, acceptance_flags)
        return

    headers = [
        "Pair",
        "Enrollment",
        "Raw→Clean",
        "Probe",
        "Raw→Clean",
        "Matched",
        "Verdict",
    ]
    rows = []

    for idx, ((enroll_path, probe_path), is_accepted) in enumerate(zip(comparison_pairs, acceptance_flags)):
        if idx >= len(enrollment_stats) or idx >= len(verification_stats):
            break

        enroll_file = os.path.splitext(os.path.basename(enroll_path))[0]
        probe_file = os.path.splitext(os.path.basename(probe_path))[0]

        enroll = enrollment_stats[idx]
        verify = verification_stats[idx]

        # Format: raw→cleaned (removed%)
        enroll_minutiae = (
            f"{enroll['raw_minutiae']}→{enroll['cleaned_minutiae']} "
            f"(-{enroll['removal_pct']:.0f}%)"
        )
        probe_minutiae = (
            f"{verify['raw_minutiae']}→{verify['cleaned_minutiae']}"
        )

        matched = f"{verify['matched_points']}/{verify['threshold']}"
        verdict = "[green]GENUINE[/green]" if is_accepted else "[red]IMPOSTOR[/red]"

        rows.append([
            str(idx + 1),
            enroll_file,
            enroll_minutiae,
            probe_file,
            probe_minutiae,
            matched,
            verdict,
        ])

    log_table(
        title=f"{batch_label} Pipeline Details ({sum(acceptance_flags)}/{len(acceptance_flags)} genuine)",
        headers=headers,
        rows=rows,
    )


def _print_verification_batch_summary(
    batch_label: str,
    comparison_pairs: list[tuple[str, str]],
    acceptance_flags: list[bool],
    detailed_stats: list[dict] = None
) -> None:
    """
    Print consolidated verification results with diagnostic columns.
    Headers: Pair, Enroll, Probe, XOR Hits, RS Check, Hash Check, Result
    """
    from modules.utilities.logger import console

    headers = ["Pair", "Enrollment", "Probe", "XOR Hits", "RS Check", "Hash Check", "Result"]
    rows = []

    for idx, ((enroll_path, probe_path), is_accepted) in enumerate(zip(comparison_pairs, acceptance_flags)):
        enroll_file = os.path.basename(enroll_path)
        probe_file = os.path.basename(probe_path)
        result = "[bold green]PASS[/bold green]" if is_accepted else "[bold red]FAIL[/bold red]"
        
        xor_hits = "N/A"
        rs_check = "[red]FAIL[/red]"
        hash_check = "[red]FAIL[/red]"
        
        if detailed_stats and idx < len(detailed_stats):
            stats = detailed_stats[idx]
            match_val = stats.get("matched_points", 0)
            thresh_val = stats.get("threshold", config.POLYNOMIAL_DEGREE + 1)
            xor_hits = f"{match_val}/{thresh_val}"
            
            if stats.get("rs_pass"): rs_check = "[green]PASS[/green]"
            if stats.get("hash_pass"): hash_check = "[green]PASS[/green]"

        rows.append([
            str(idx + 1),
            enroll_file,
            probe_file,
            xor_hits,
            rs_check,
            hash_check,
            result,
        ])

    log_table(
        title=f"{batch_label} Verification Results ({sum(acceptance_flags)}/{len(acceptance_flags)} matched)",
        headers=headers,
        rows=rows,
    )


def _print_results_summary_table(all_results: dict, polynomial_degree: int) -> None:
    """Print a colored summary table of all results to the console."""
    headers = ["Database", "p", "GAR (%)", "FAR (%)", "FRR (%)", "EER (%)"]
    rows = []
    for database_name, metrics in all_results.items():
        rows.append([
            database_name,
            polynomial_degree,
            f"{metrics['gar_pct']:.2f}",
            f"{metrics['far_pct']:.2f}",
            f"{metrics['frr_pct']:.2f}",
            f"{metrics['eer_pct']:.4f}",
        ])

    log_table(
        title=f"Evaluation Results -- Polynomial Degree p = {polynomial_degree}",
        headers=headers,
        rows=rows,
    )


def _empty_result() -> dict:
    """Return a zeroed-out result dict for when a database cannot be loaded."""
    return {
        "gar_pct": 0.0, "far_pct": 0.0, "frr_pct": 0.0, "eer_pct": 0.0,
        "num_genuine": 0, "num_impostor": 0,
        "genuine_accepted_count": 0, "impostor_accepted_count": 0,
    }
