"""
parallel_processor.py -- Parallel processing utilities for CPU-bound operations.

Provides:
- Parallel enrollment/verification operations
- Batch processing with configurable worker pools
- Thread-safe progress tracking
- Deterministic results consistent with serial execution
"""

import sys
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from typing import Callable, List, Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.utilities.logger import log_step, log_data, log_success, log_warning


# ============================================================================
# PARALLEL EXECUTOR
# ============================================================================

class ParallelProcessor:
    """
    Safe parallel processor for CPU-bound and I/O-bound operations.

    Attributes
    ----------
    max_workers : int
        Number of parallel workers (CPU-bound: cpu_count - 1, I/O: cpu_count * 2)
    use_processes : bool
        Use ProcessPoolExecutor (True) or ThreadPoolExecutor (False)
    """

    def __init__(self, max_workers: int = None, use_processes: bool = True):
        """
        Initialize parallel processor.

        Parameters
        ----------
        max_workers : int, optional
            Number of parallel workers. If None:
            - For processes: min(8, cpu_count - 1)
            - For threads: min(32, cpu_count * 4)
        use_processes : bool
            True for CPU-bound tasks (GIL-free), False for I/O-bound
        """
        if use_processes:
            self.use_processes = True
            if max_workers is None:
                max_workers = min(8, max(1, cpu_count() - 1))
        else:
            self.use_processes = False
            if max_workers is None:
                max_workers = min(32, cpu_count() * 4)

        self.max_workers = max_workers
        self.executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor

    def map_parallel(
        self,
        func: Callable,
        items: List[Any],
        description: str = "Processing"
    ) -> List[Any]:
        """
        Apply function to items in parallel, maintaining order.

        Parameters
        ----------
        func : Callable
            Function to apply to each item
        items : List
            Items to process
        description : str
            Description for logging

        Returns
        -------
        results : List
            Results in same order as input items
        """
        log_step(f"{description} ({len(items)} items, {self.max_workers} workers)")

        results = [None] * len(items)
        futures_to_index = {}

        with self.executor_class(max_workers=self.max_workers) as executor:
            for idx, item in enumerate(items):
                future = executor.submit(func, item)
                futures_to_index[future] = idx

            completed = 0
            for future in as_completed(futures_to_index):
                idx = futures_to_index[future]
                try:
                    results[idx] = future.result()
                    completed += 1

                    if len(items) > 10 and completed % max(1, len(items) // 10) == 0:
                        log_data("Progress", f"{completed}/{len(items)}")
                except Exception as e:
                    log_warning(f"Task {idx} failed: {str(e)}")
                    results[idx] = None

        log_data(f"{description} complete", f"{completed}/{len(items)}")
        return results

    def map_reduce(
        self,
        func: Callable,
        items: List[Any],
        reduce_func: Callable = None,
        description: str = "Processing"
    ) -> Any:
        """
        Apply function to items in parallel and reduce results.

        Parameters
        ----------
        func : Callable
            Function to apply to each item
        items : List
            Items to process
        reduce_func : Callable, optional
            Function to combine results. If None, returns list of results.
        description : str
            Description for logging

        Returns
        -------
        result : Any
            Reduced result or list of results
        """
        results = self.map_parallel(func, items, description)

        if reduce_func is None:
            return results

        return reduce_func(results)

    def batch_process(
        self,
        func: Callable,
        items: List[Any],
        batch_size: int = None,
        description: str = "Processing batches"
    ) -> List[Any]:
        """
        Process items in batches with parallel workers.

        Useful for: large number of items, variable processing time per item

        Parameters
        ----------
        func : Callable
            Function to apply to each item
        items : List
            Items to process
        batch_size : int, optional
            Batch size. If None: len(items) // self.max_workers
        description : str
            Description for logging

        Returns
        -------
        results : List
            Results in same order as input items
        """
        if batch_size is None:
            batch_size = max(1, len(items) // (self.max_workers * 2))

        batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

        log_step(f"{description} ({len(items)} items in {len(batches)} batches)")

        batch_results = self.map_parallel(
            lambda batch: [func(item) for item in batch],
            batches,
            description=description
        )

        # Flatten results
        results = []
        for batch_result in batch_results:
            if batch_result:
                results.extend(batch_result)

        return results


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def parallel_enroll_verify(
    enroll_path: str,
    verify_paths: List[str],
    description: str = "Parallel verification",
    max_workers: int = None
) -> List[Tuple[bool, Any]]:
    """
    Enroll once and verify against multiple probes in parallel.

    Parameters
    ----------
    enroll_path : str
        Enrollment image path
    verify_paths : List[str]
        Probe image paths
    description : str
        Description for logging
    max_workers : int
        Number of workers

    Returns
    -------
    results : List[Tuple[bool, Any]]
        (is_genuine, recovered_secret) for each probe
    """
    from modules.m09_vault_encoder import enroll
    from modules.m10_vault_decoder import verify

    log_step(f"Enrolling from {os.path.basename(enroll_path)}")
    enrollment_data = enroll(enroll_path)

    if not enrollment_data.get("enrollment_successful"):
        log_warning("Enrollment failed")
        return [(False, None)] * len(verify_paths)

    def verify_against_enrollment(verify_path):
        try:
            return verify(verify_path, enrollment_data)
        except Exception as e:
            log_warning(f"Verification failed: {str(e)}")
            return (False, None)

    processor = ParallelProcessor(max_workers=max_workers, use_processes=True)
    results = processor.map_parallel(verify_against_enrollment, verify_paths, description)

    return results


def parallel_batch_enroll_verify(
    enroll_verify_pairs: List[Tuple[str, str]],
    description: str = "Parallel enrollment and verification",
    max_workers: int = None
) -> List[Tuple[bool, Any]]:
    """
    Process multiple (enroll, verify) pairs in parallel.

    Parameters
    ----------
    enroll_verify_pairs : List[Tuple[str, str]]
        List of (enroll_path, verify_path) tuples
    description : str
        Description for logging
    max_workers : int
        Number of workers

    Returns
    -------
    results : List[Tuple[bool, Any]]
        (is_genuine, recovered_secret) for each pair
    """
    from modules.m09_vault_encoder import enroll
    from modules.m10_vault_decoder import verify

    def process_pair(args):
        enroll_path, verify_path = args
        try:
            enrollment_data = enroll(enroll_path)
            if not enrollment_data.get("enrollment_successful"):
                return (False, None)
            return verify(verify_path, enrollment_data)
        except Exception as e:
            return (False, None)

    processor = ParallelProcessor(max_workers=max_workers, use_processes=True)
    results = processor.map_parallel(process_pair, enroll_verify_pairs, description)

    return results


def get_optimal_workers(task_type: str = "cpu") -> int:
    """
    Get optimal number of workers for task type.

    Parameters
    ----------
    task_type : str
        "cpu" for CPU-bound, "io" for I/O-bound

    Returns
    -------
    workers : int
        Recommended number of workers
    """
    cpu_cores = cpu_count()

    if task_type == "cpu":
        return min(8, max(1, cpu_cores - 1))
    elif task_type == "io":
        return min(32, cpu_cores * 4)
    else:
        return cpu_cores
