"""
main.py -- Chaff-Free Fuzzy Vault: CLI entry point.

SIL7175 Assignment-3 -- Fingerprint-Based Biometric Cryptosystem

Dataset download instructions
------------------------------
Register and download the FVC2002 and FVC2004 datasets from:
    http://bias.csr.unibo.it/fvc2002/
    http://bias.csr.unibo.it/fvc2004/

Extract into this directory structure:
    datasets/
        FVC2002/
            DB1_B/    <- 100 subjects x 8 impressions (.tif files)
            DB2_B/
        FVC2004/
            DB1_B/

Each folder should contain files named: 1_1.tif, 1_2.tif, ..., 100_8.tif
Update DATASET_ROOT in config.py if you place them elsewhere.

Usage
-----
    python main.py --mode demo              --image PATH
    python main.py --mode enroll            --image PATH [--save-vault VAULT.json]
    python main.py --mode enroll-visual     --image PATH
    python main.py --mode verify            --image PATH --vault VAULT.json
    python main.py --mode match             --image PATH --probe PATH
    python main.py --mode evaluate          [--db-root PATH] [--degree 8]
    python main.py --mode interactive       # Menu-driven interactive mode

Modes
-----
  demo              4-panel preprocessing visualization for one image.

  enroll            Enroll fingerprint, print vault and secret key.
                    Optionally save vault to JSON.

  enroll-visual     Enroll with full pipeline visualization to outputs/enrollments/.

  verify            Verify probe fingerprint against saved vault.

  match             Compare two fingerprints with detailed matching output.
                    Saves JSON results to outputs/matches/.

  evaluate          Full 1-vs-1 evaluation on FVC databases.
                    Outputs: GAR/FAR/EER metrics, ROC curves.

  interactive       Menu-driven mode for all operations.
"""

import argparse
import json
import os
import sys
from multiprocessing import cpu_count

# Ensure the project root is on the Python path
sys.path.insert(0, os.path.dirname(__file__))

from modules.utilities import config
from modules.utilities.logger import (
    log_section, log_step, log_data, log_success,
    log_warning, log_error, log_verdict, console,
)

# Auto-detect system capabilities
_CPU_CORES = cpu_count()
_OPTIMAL_WORKERS = min(8, max(1, _CPU_CORES - 1))
_GPU_AVAILABLE = False
_NUMBA_AVAILABLE = False

try:
    from numba import jit
    _NUMBA_AVAILABLE = True
except ImportError:
    pass

try:
    from modules.utilities.gpu_accelerator import is_gpu_available, get_gpu_info
    if is_gpu_available():
        _GPU_AVAILABLE = True
except (ImportError, RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    argument_parser = _build_argument_parser()
    parsed_args = argument_parser.parse_args()

    _print_banner()
    _ensure_output_directories_exist()

    if parsed_args.mode == "demo":
        _run_demo_mode(parsed_args)

    elif parsed_args.mode == "enroll":
        _run_enroll_mode(parsed_args)

    elif parsed_args.mode == "enroll-visual":
        _run_enroll_visual_mode(parsed_args)

    elif parsed_args.mode == "verify":
        _run_verify_mode(parsed_args)

    elif parsed_args.mode == "match":
        _run_match_mode(parsed_args)

    elif parsed_args.mode == "evaluate":
        _run_evaluate_mode(parsed_args)

    elif parsed_args.mode == "interactive":
        _run_interactive_mode()

    else:
        log_error(f"Unknown mode: '{parsed_args.mode}'")
        argument_parser.print_help()
        sys.exit(1)


# ---------------------------------------------------------------------------
# Mode implementations
# ---------------------------------------------------------------------------

def _run_interactive_mode() -> None:
    """
    Interactive menu-driven mode allowing users to select operations.
    """
    from modules.utilities.logger import console

    while True:
        console.print("\n")
        console.print("[bold cyan]╔════════════════════════════════════════════════════╗[/bold cyan]")
        console.print("[bold cyan]║  Chaff-Free Fuzzy Vault - Interactive Mode         ║[/bold cyan]")
        console.print("[bold cyan]╚════════════════════════════════════════════════════╝[/bold cyan]")
        console.print("\n[bold]Select an operation:[/bold]")
        console.print("  [1] Demo  - Visualize fingerprint processing pipeline")
        console.print("  [2] Enroll - Enroll a new fingerprint")
        console.print("  [3] Verify - Verify a fingerprint against a vault")
        console.print("  [4] Evaluate - Run full 1-vs-1 evaluation")
        console.print("  [5] Exit\n")

        choice = console.input("[bold]Enter choice (1-5): [/bold]").strip()

        if choice == "1":
            _interactive_demo()
        elif choice == "2":
            _interactive_enroll()
        elif choice == "3":
            _interactive_verify()
        elif choice == "4":
            _interactive_evaluate()
        elif choice == "5":
            console.print("[green]✓[/green] Goodbye!\n")
            sys.exit(0)
        else:
            console.print("[red]✗ Invalid choice. Please try again.[/red]")


def _interactive_demo() -> None:
    """Interactive demo mode."""
    from modules.utilities.logger import console

    image_path = console.input("[bold]Enter fingerprint image path: [/bold]").strip()
    if not image_path or not os.path.isfile(image_path):
        console.print(f"[red]✗ File not found: {image_path}[/red]")
        return

    class DemoArgs:
        image = image_path

    _run_demo_mode(DemoArgs())
    console.print("\n[green]✓ Demo completed.[/green]")


def _interactive_enroll() -> None:
    """Interactive enrollment mode."""
    from modules.utilities.logger import console

    image_path = console.input("[bold]Enter fingerprint image path: [/bold]").strip()
    if not image_path or not os.path.isfile(image_path):
        console.print(f"[red]✗ File not found: {image_path}[/red]")
        return

    save_vault = console.input("[bold]Save vault to file? (y/n, default: y): [/bold]").strip().lower()
    vault_path = None
    if save_vault != "n":
        vault_path = console.input("[bold]Enter vault file path (default: enrolled_vault.json): [/bold]").strip()
        if not vault_path:
            vault_path = "enrolled_vault.json"

    class EnrollArgs:
        image = image_path
        save_vault = vault_path

    _run_enroll_mode(EnrollArgs())
    if vault_path:
        console.print(f"\n[green]✓ Vault saved to: {vault_path}[/green]")


def _interactive_verify() -> None:
    """Interactive verification mode."""
    from modules.utilities.logger import console

    image_path = console.input("[bold]Enter probe fingerprint image path: [/bold]").strip()
    if not image_path or not os.path.isfile(image_path):
        console.print(f"[red]✗ File not found: {image_path}[/red]")
        return

    vault_path = console.input("[bold]Enter vault file path: [/bold]").strip()
    if not vault_path or not os.path.isfile(vault_path):
        console.print(f"[red]✗ File not found: {vault_path}[/red]")
        return

    class VerifyArgs:
        image = image_path
        vault = vault_path

    _run_verify_mode(VerifyArgs())
    console.print("\n[green]✓ Verification completed.[/green]")


def _interactive_evaluate() -> None:
    """Interactive evaluation mode."""
    from modules.utilities.logger import console

    db_root = console.input("[bold]Enter dataset root path (default: Dataset/): [/bold]").strip()
    if not db_root:
        db_root = "Dataset/"

    if not os.path.isdir(db_root):
        console.print(f"[red]✗ Directory not found: {db_root}[/red]")
        return

    class EvalArgs:
        db_root = db_root
        degree = None

    _run_evaluate_mode(EvalArgs())
    console.print("\n[green]✓ Evaluation completed.[/green]")


def _run_demo_mode(args) -> None:
    """
    Run the full preprocessing pipeline on a single image and save a
    4-panel pipeline visualization to outputs/step_visuals/.
    """
    if not args.image:
        log_error("--mode demo requires --image PATH")
        sys.exit(1)

    log_section("DEMO MODE -- Pipeline Visualization")
    log_data("Input image", args.image)

    from modules.utilities.visualizer import visualize_pipeline_steps

    output_filename = (
        "pipeline_"
        + os.path.splitext(os.path.basename(args.image))[0]
        + ".png"
    )
    output_path = os.path.join(config.STEP_VISUALS_OUTPUT_DIR, output_filename)

    visualize_pipeline_steps(args.image, output_path)
    log_success(f"Visualization saved to: {output_path}")


def _run_enroll_mode(args) -> None:
    """
    Enroll one fingerprint image.  Print the vault and secret key.
    Optionally save the vault to a JSON file.
    """
    if not args.image:
        log_error("--mode enroll requires --image PATH")
        sys.exit(1)

    log_section("ENROLL MODE")
    log_data("Fingerprint image", args.image)

    from modules.m09_vault_encoder import enroll

    enrollment_data = enroll(args.image)

    if not enrollment_data.get("enrollment_successful", True) is True:
        log_error(f"Enrollment aborted: {enrollment_data.get('error', 'Unknown error')}")
        sys.exit(1)

    log_success("Enrollment complete")

    # Handle both bytes and string formats for secret key
    secret_key = enrollment_data["secret_key_bytes"]
    if isinstance(secret_key, bytes):
        secret_key_hex = secret_key.hex()
    else:
        secret_key_hex = secret_key

    log_data("Secret key (hex)", secret_key_hex)
    log_data("Vault size (points)", len(enrollment_data["vault_points"]))
    log_data("Coord min", f"{enrollment_data['coord_min']:.4f}")
    log_data("Coord max", f"{enrollment_data['coord_max']:.4f}")

    if args.save_vault:
        _save_vault_to_json(enrollment_data, args.save_vault)
        log_success(f"Vault saved to: {args.save_vault}")


def _run_verify_mode(args) -> None:
    """
    Verify a probe fingerprint against a previously saved vault.
    """
    if not args.image:
        log_error("--mode verify requires --image PATH")
        sys.exit(1)
    if not args.vault:
        log_error("--mode verify requires --vault VAULT.json")
        sys.exit(1)

    log_section("VERIFY MODE")
    log_data("Probe image", args.image)
    log_data("Vault file", args.vault)

    enrollment_data = _load_vault_from_json(args.vault)
    if not enrollment_data.get("vault_points"):
        log_error("Failed to load valid vault data from JSON")
        sys.exit(1)

    from modules.m10_vault_decoder import verify

    is_genuine, recovered_secret, verification_stats = verify(args.image, enrollment_data)

    log_section("VERIFICATION RESULT")
    if is_genuine and recovered_secret is not None:
        log_data("Recovered secret (hex)", recovered_secret)

    # Compare recovered secret to enrolled secret (if available in vault file)
    enrolled_secret = enrollment_data.get("secret_key_bytes")
    if enrolled_secret and is_genuine and recovered_secret:
        secrets_match = (recovered_secret == enrolled_secret)
        log_data("Secrets match", "YES" if secrets_match else "NO -- mismatch!")


def _run_enroll_visual_mode(args) -> None:
    """Enroll single image with full pipeline visualization to outputs/enrollments/"""
    if not args.image:
        log_error("--mode enroll-visual requires --image PATH")
        sys.exit(1)

    from modules.utilities.visualizer import visualize_pipeline_steps
    from modules.m09_vault_encoder import enroll

    log_section("ENROLL WITH FULL VISUALIZATION")
    log_data("Image", args.image)

    if not os.path.exists(args.image):
        log_error(f"Image file not found: {args.image}")
        sys.exit(1)

    enrollment_data = enroll(args.image)
    if not enrollment_data.get("enrollment_successful"):
        log_error(f"Enrollment failed: {enrollment_data.get('error')}")
        sys.exit(1)

    # Save visualizations
    image_name = os.path.basename(args.image)
    output_dir = os.path.join(config.OUTPUT_ROOT, "enrollments", os.path.splitext(image_name)[0])
    os.makedirs(output_dir, exist_ok=True)

    try:
        output_file = os.path.join(output_dir, f"{os.path.splitext(image_name)[0]}_pipeline.png")
        visualize_pipeline_steps(args.image, output_file)
        log_success(f"Pipeline visualization saved to: {output_file}")
    except Exception as e:
        log_warning(f"Visualization generation skipped: {e}")

    log_success("Enrollment complete with visualizations")
    log_data("Vault size", len(enrollment_data["vault_points"]))
    log_data("Output directory", output_dir)


def _run_match_mode(args) -> None:
    """Compare two fingerprints with detailed matching output and visualization"""
    if not args.image:
        log_error("--mode match requires --image PATH (enrollment image)")
        sys.exit(1)
    if not args.probe:
        log_error("--mode match requires --probe PATH (verification image)")
        sys.exit(1)

    from modules.m09_vault_encoder import enroll
    from modules.m10_vault_decoder import verify

    log_section("TWO-IMAGE FINGERPRINT MATCHING")
    log_data("Enrolled image", args.image)
    log_data("Probe image", args.probe)

    if not os.path.exists(args.image):
        log_error(f"Enrollment image not found: {args.image}")
        sys.exit(1)
    if not os.path.exists(args.probe):
        log_error(f"Probe image not found: {args.probe}")
        sys.exit(1)

    # Enrollment
    log_step("Enrolling first fingerprint...")
    enrollment_data = enroll(args.image, quiet=True)
    if not enrollment_data.get("enrollment_successful"):
        log_error(f"Enrollment failed: {enrollment_data.get('error')}")
        sys.exit(1)

    vault_size = len(enrollment_data["vault_points"])
    log_success(f"Enrollment complete - Vault size: {vault_size}")

    # Verification
    log_step("Verifying second fingerprint...")
    is_genuine, _, verify_stats = verify(args.probe, enrollment_data, quiet=True)

    matched_points = verify_stats.get("matched_points", 0)
    match_ratio = (matched_points / vault_size * 100) if vault_size > 0 else 0
    combos_tried = verify_stats.get("lagrange_combos_tried", 0)

    log_section("MATCHING RESULT")
    log_data("Result", "✓ GENUINE MATCH" if is_genuine else "✗ IMPOSTOR (NO MATCH)")
    log_data("Matched points", f"{matched_points} / {vault_size}")
    log_data("Match ratio", f"{match_ratio:.2f}%")
    log_data("Lagrange combinations", f"{combos_tried}")
    log_data("Verdict", verify_stats.get("verdict", "UNKNOWN"))

    # Save results
    output_dir = os.path.join(config.OUTPUT_ROOT, "matches")
    os.makedirs(output_dir, exist_ok=True)

    enroll_name = os.path.splitext(os.path.basename(args.image))[0]
    probe_name = os.path.splitext(os.path.basename(args.probe))[0]
    result_file = os.path.join(output_dir, f"{enroll_name}_vs_{probe_name}.json")

    import json
    result_data = {
        "enrolled_image": args.image,
        "probe_image": args.probe,
        "result": "GENUINE" if is_genuine else "IMPOSTOR",
        "matched_points": matched_points,
        "vault_size": vault_size,
        "match_ratio_percent": match_ratio,
        "lagrange_combos_tried": combos_tried,
        "verdict": verify_stats.get("verdict", "UNKNOWN")
    }

    with open(result_file, 'w') as f:
        json.dump(result_data, f, indent=2)

    log_success(f"Results saved to: {result_file}")


def _run_evaluate_mode(args) -> None:
    """
    Run the full 1-vs-1 evaluation on all three FVC databases.
    Auto-detects and uses available system resources (GPU, parallelization).
    Saves CSV metrics and ROC plot images.
    """
    log_section("EVALUATE MODE -- Full 1-vs-1 Protocol")

    # Report system configuration
    log_step("System Configuration")
    log_data("CPU Cores Available", _CPU_CORES)
    log_data("Parallelization", "ENABLED" if _OPTIMAL_WORKERS > 1 else "DISABLED (single core)")
    log_data("Workers", _OPTIMAL_WORKERS if _OPTIMAL_WORKERS > 1 else "1")

    if _GPU_AVAILABLE:
        log_success("GPU Acceleration AVAILABLE")
        try:
            gpu_info = get_gpu_info()
            if gpu_info.get("device_info"):
                log_data("GPU Device", gpu_info["device_info"].get("name", "Unknown"))
                log_data("Compute Capability", gpu_info["device_info"].get("compute_capability", "Unknown"))
        except:
            pass
    else:
        log_data("GPU Acceleration", "NOT AVAILABLE (CPU-only mode)")

    if _NUMBA_AVAILABLE:
        log_success("Numba JIT AVAILABLE (10-100x GF speedup)")
    else:
        log_data("Numba JIT", "NOT AVAILABLE")

    print()
    polynomial_degree = args.degree if args.degree else config.POLYNOMIAL_DEGREE
    log_data("Polynomial degree p", polynomial_degree)

    if args.db_root:
        # Override the dataset root at runtime if user supplied --db-root
        import config as cfg_module
        cfg_module.DATASET_ROOT = args.db_root
        log_data("Dataset root (overridden)", args.db_root)

    from modules.utilities.evaluator import run_full_evaluation

    # Pass database filter if specified
    database_filter = args.database if args.database else None
    if database_filter:
        log_data("Evaluating database", database_filter)

    all_results = run_full_evaluation(polynomial_degree, database_filter=database_filter)

    log_success("Evaluation complete. Check outputs/ for results.")


# ---------------------------------------------------------------------------
# Vault JSON persistence helpers
# ---------------------------------------------------------------------------

def _save_vault_to_json(enrollment_data: dict, file_path: str) -> None:
    """Serialize enrollment data to a JSON file for later verification."""
    # Handle both bytes and string formats for secret key
    secret_key = enrollment_data["secret_key_bytes"]
    if isinstance(secret_key, bytes):
        secret_key_hex = secret_key.hex()
    else:
        secret_key_hex = secret_key

    serializable_data = {
        "vault_points":   enrollment_data["vault_points"],
        "coord_min":      enrollment_data["coord_min"],
        "coord_max":      enrollment_data["coord_max"],
        "secret_key_hex":  secret_key_hex,
        "secret_key_hash": enrollment_data.get("secret_key_hash"),
        "image_path":      enrollment_data["image_path"],
        "singular_point":  enrollment_data["singular_point"],   # [sx, sy]
        "pca_matrix_U":    enrollment_data["pca_matrix_U"],     # [[a,b],[c,d]]
        "ridge_frequency": enrollment_data.get("ridge_frequency", 1.0),
    }
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    with open(file_path, "w") as vault_file:
        json.dump(serializable_data, vault_file, indent=2)


def _load_vault_from_json(file_path: str) -> dict:
    """Deserialize enrollment data from a JSON file."""
    if not os.path.isfile(file_path):
        log_error(f"Vault file not found: {file_path}")
        sys.exit(1)

    with open(file_path, "r") as vault_file:
        raw_data = json.load(vault_file)

    enrollment_data = {
        "vault_points":      raw_data["vault_points"],
        "coord_min":         raw_data["coord_min"],
        "coord_max":         raw_data["coord_max"],
        "secret_key_bytes":  bytes.fromhex(raw_data["secret_key_hex"]),
        "secret_key_hash":   raw_data.get("secret_key_hash"),
        "image_path":        raw_data.get("image_path", ""),
        "singular_point":    raw_data["singular_point"],
        "pca_matrix_U":      raw_data["pca_matrix_U"],
        "ridge_frequency":   raw_data.get("ridge_frequency", 1.0),
    }
    return enrollment_data


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _find_any_sample_image() -> str | None:
    """
    Find one fingerprint image from the first available FVC database folder.
    Used to auto-select a sample for pipeline visualization after evaluation.
    Tries every supported format so JPG/BMP/PNG databases are handled as well.
    """
    from modules.utilities.dataset_loader import SUPPORTED_EXTENSIONS
    for db_config in config.DATABASES.values():
        db_dir = os.path.join(config.DATASET_ROOT, db_config["subdir"])
        for ext in SUPPORTED_EXTENSIONS:
            candidate_path = os.path.join(db_dir, f"1_1{ext}")
            if os.path.isfile(candidate_path):
                return candidate_path
    return None


def _ensure_output_directories_exist() -> None:
    """Create all output subdirectories if they do not yet exist."""
    for output_dir in [
        config.OUTPUT_ROOT,
        config.METRICS_OUTPUT_DIR,
        config.PLOTS_OUTPUT_DIR,
        config.STEP_VISUALS_OUTPUT_DIR,
    ]:
        os.makedirs(output_dir, exist_ok=True)


def _print_banner() -> None:
    """Print a colored startup banner."""
    console.print()
    console.print(
        "[bold magenta]====================================================[/bold magenta]"
    )
    console.print(
        "[bold magenta]  Chaff-Free Fuzzy Vault  |  SIL7175 Assignment-3  [/bold magenta]"
    )
    console.print(
        "[bold magenta]====================================================[/bold magenta]"
    )
    console.print(
        f"[cyan]  p={config.POLYNOMIAL_DEGREE} | "
        f"Secret={config.SECRET_KEY_BITS}b | "
        f"Chaff={getattr(config, 'VAULT_CHAFF_POINTS', 0)} | "
        f"Core=Orientation-Coherence[/cyan]"
    )
    console.print()


def _build_argument_parser() -> argparse.ArgumentParser:
    """Define and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Chaff-Free Fuzzy Vault -- SIL7175 Assignment-3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--mode",
        required=True,
        choices=["demo", "enroll", "enroll-visual", "verify", "match", "evaluate", "interactive"],
        help="Operation mode: demo, enroll, enroll-visual, verify, match, evaluate, or interactive.",
    )
    parser.add_argument(
        "--image",
        default=None,
        metavar="PATH",
        help="Path to a fingerprint image (.tif, .bmp, etc.).",
    )
    parser.add_argument(
        "--probe",
        default=None,
        metavar="PATH",
        help="Path to probe/verification image (used with --mode match).",
    )
    parser.add_argument(
        "--vault",
        default=None,
        metavar="VAULT.json",
        help="Path to a vault JSON file (required for --mode verify).",
    )
    parser.add_argument(
        "--save-vault",
        default=None,
        metavar="VAULT.json",
        help="Save the enrollment vault to this JSON file (used with --mode enroll).",
    )
    parser.add_argument(
        "--db-root",
        default=None,
        metavar="PATH",
        help="Override the FVC dataset root directory (default: config.DATASET_ROOT).",
    )
    parser.add_argument(
        "--degree",
        type=int,
        default=None,
        metavar="INT",
        help="Polynomial degree p (default: 8 as required by the assignment).",
    )
    parser.add_argument(
        "--database",
        default=None,
        metavar="DB_NAME",
        choices=["FVC2002_DB1", "FVC2002_DB2", "FVC2004_DB1"],
        help="Evaluate only a specific database (default: all three databases).",
    )

    return parser


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
