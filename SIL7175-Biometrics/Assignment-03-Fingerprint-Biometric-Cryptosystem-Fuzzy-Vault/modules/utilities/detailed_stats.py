"""
detailed_stats.py - Collect and export comprehensive pipeline statistics to CSV.
"""

import csv
import os
from pathlib import Path
from typing import List, Dict, Any


class DetailedPipelineStats:
    """Collect comprehensive statistics from enrollment and verification pipelines."""

    def __init__(self):
        """Initialize statistics collector."""
        self.enrollment_stats: List[Dict[str, Any]] = []
        self.verification_stats: List[Dict[str, Any]] = []

    def add_enrollment_stats(self, stats_dict: Dict[str, Any]) -> None:
        """
        Add enrollment statistics for one image.

        Parameters
        ----------
        stats_dict : dict
            Dictionary containing all enrollment statistics
            Expected keys:
            - enroll_file: str
            - image_height, image_width: int
            - foreground_pixels: int
            - skeleton_ridge_pixels: int
            - singular_point: tuple
            - raw_minutiae: int
            - cleaned_minutiae: int
            - spurious_removed: int
            - pca_matrix_shape: tuple
            - coord_min, coord_max: float
            - quantized_count: int
            - secret_key_hex: str
            - rs_codeword_length: int
            - vault_points: int
        """
        self.enrollment_stats.append(stats_dict)

    def add_verification_stats(self, stats_dict: Dict[str, Any]) -> None:
        """
        Add verification statistics for one comparison.

        Parameters
        ----------
        stats_dict : dict
            Dictionary containing all verification statistics
            Expected keys:
            - pair_id: int
            - enrollment_file: str
            - probe_file: str
            - probe_height, probe_width: int
            - probe_foreground_pixels: int
            - probe_skeleton_ridge_pixels: int
            - probe_raw_minutiae: int
            - probe_cleaned_minutiae: int
            - probe_spurious_removed: int
            - probe_quantized_count: int
            - matched_points: int
            - matching_threshold: int
            - verdict: str (GENUINE/IMPOSTOR)
            - is_accepted: bool
        """
        self.verification_stats.append(stats_dict)

    def export_enrollment_csv(self, output_path: str) -> None:
        """
        Export enrollment statistics to CSV.

        Parameters
        ----------
        output_path : str
            Path to output CSV file
        """
        if not self.enrollment_stats:
            return

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Get all unique keys from all stats dictionaries
        fieldnames = set()
        for stat in self.enrollment_stats:
            fieldnames.update(stat.keys())
        fieldnames = sorted(list(fieldnames))

        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for stat in self.enrollment_stats:
                # Convert non-string values to strings
                row = {}
                for key, value in stat.items():
                    if isinstance(value, (tuple, list)):
                        row[key] = str(value)
                    else:
                        row[key] = value
                writer.writerow(row)

    def export_verification_csv(self, output_path: str, database_name: str = "") -> None:
        """
        Export verification statistics to CSV.

        Parameters
        ----------
        output_path : str
            Path to output CSV file
        database_name : str
            Name of database (FVC2002_DB1, etc.)
        """
        if not self.verification_stats:
            return

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Get all unique keys from all stats dictionaries
        fieldnames = set()
        for stat in self.verification_stats:
            fieldnames.update(stat.keys())
        fieldnames = sorted(list(fieldnames))

        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for stat in self.verification_stats:
                # Convert non-string values to strings
                row = {}
                for key, value in stat.items():
                    if isinstance(value, (tuple, list)):
                        row[key] = str(value)
                    else:
                        row[key] = value
                writer.writerow(row)

    def export_summary_csv(self, output_path: str, metrics_dict: Dict[str, Any]) -> None:
        """
        Export overall metrics summary to CSV.

        Parameters
        ----------
        output_path : str
            Path to output CSV file
        metrics_dict : dict
            Dictionary containing metrics for all databases
            Expected structure:
            {
                "database_name": {
                    "gar": float,
                    "far": float,
                    "frr": float,
                    "eer": float,
                    "genuine_accepted": int,
                    "genuine_total": int,
                    "impostor_accepted": int,
                    "impostor_total": int,
                }
            }
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        fieldnames = [
            "Database",
            "Polynomial_Degree",
            "Genuine_Accepted",
            "Genuine_Total",
            "GAR_%",
            "Impostor_Accepted",
            "Impostor_Total",
            "FAR_%",
            "FRR_%",
            "EER_%"
        ]

        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for db_name, metrics in metrics_dict.items():
                row = {
                    "Database": db_name,
                    "Polynomial_Degree": 8,
                    "Genuine_Accepted": metrics.get("genuine_accepted", 0),
                    "Genuine_Total": metrics.get("genuine_total", 0),
                    "GAR_%": f"{metrics.get('gar', 0):.2f}",
                    "Impostor_Accepted": metrics.get("impostor_accepted", 0),
                    "Impostor_Total": metrics.get("impostor_total", 0),
                    "FAR_%": f"{metrics.get('far', 0):.2f}",
                    "FRR_%": f"{metrics.get('frr', 0):.2f}",
                    "EER_%": f"{metrics.get('eer', 0):.4f}",
                }
                writer.writerow(row)
