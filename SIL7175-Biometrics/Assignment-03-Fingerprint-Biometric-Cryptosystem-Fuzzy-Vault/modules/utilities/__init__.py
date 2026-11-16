"""
utilities package -- Organized utility modules for the Chaff-Free Fuzzy Vault system.

Sub-modules:
  - logger: Colored console output (uses rich library)
  - dataset_loader: FVC database loading and pair generation
  - evaluator: GAR/FAR/EER computation and metrics
  - visualizer: Pipeline visualization and ROC curves
  - parallel_processor: Parallel processing utilities for CPU-bound tasks
"""

from modules.utilities.logger import (
    log_section, log_step, log_success, log_warning, log_error, log_data, log_table, log_verdict
)
from modules.utilities.dataset_loader import load_database, get_genuine_pairs, get_impostor_pairs
# NOTE: evaluator deliberately NOT imported here to avoid circular dependency with m09_vault_encoder
# Import directly in main.py or other modules as needed
from modules.utilities.visualizer import (
    visualize_pipeline_steps, plot_roc_curve, plot_combined_roc, save_results_table_image
)
from modules.utilities.parallel_processor import (
    ParallelProcessor, parallel_enroll_verify, parallel_batch_enroll_verify, get_optimal_workers
)
from modules.utilities.gpu_accelerator import (
    is_gpu_available, get_gpu_info, log_gpu_status, enhance_with_gpu_gabor, pca_align_gpu,
    gf_multiply_batch, print_acceleration_status
)

__all__ = [
    'log_section', 'log_step', 'log_success', 'log_warning', 'log_error', 'log_data', 'log_table', 'log_verdict',
    'load_database', 'get_genuine_pairs', 'get_impostor_pairs',
    # run_full_evaluation, compute_eer, export_results_to_csv NOT exported to avoid circular import
    'visualize_pipeline_steps', 'plot_roc_curve', 'plot_combined_roc', 'save_results_table_image',
    'ParallelProcessor', 'parallel_enroll_verify', 'parallel_batch_enroll_verify', 'get_optimal_workers',
    'is_gpu_available', 'get_gpu_info', 'log_gpu_status', 'enhance_with_gpu_gabor', 'pca_align_gpu',
    'gf_multiply_batch', 'print_acceleration_status',
]
