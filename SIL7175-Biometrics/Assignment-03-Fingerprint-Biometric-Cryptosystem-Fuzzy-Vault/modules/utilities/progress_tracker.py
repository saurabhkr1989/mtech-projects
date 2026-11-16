"""
progress_tracker.py - Track and display enrollment/verification pipeline progress in tabular format.
"""

from typing import List, Dict, Any
from modules.utilities.logger import log_table


class PipelineProgressTracker:
    """
    Tracks all steps in the enrollment/verification pipeline and displays them as a table.

    Usage:
        tracker = PipelineProgressTracker("Enrollment")
        tracker.add_step("Load image", "OK", "512x512")
        tracker.add_step("Segmentation", "OK", "60862 pixels")
        ...
        tracker.display_table()
    """

    def __init__(self, operation_name: str, image_filename: str = ""):
        """
        Initialize progress tracker.

        Parameters
        ----------
        operation_name : str
            "Enrollment" or "Verification"
        image_filename : str
            Name of the image being processed
        """
        self.operation_name = operation_name
        self.image_filename = image_filename
        self.steps: List[Dict[str, str]] = []
        self.step_count = 0

    def add_step(self, operation: str, status: str = "OK", details: str = "") -> None:
        """
        Add a step to the progress tracker.

        Parameters
        ----------
        operation : str
            Description of the operation (e.g., "Load image", "Gabor enhancement")
        status : str
            Status of operation: "OK", "SKIP", "WARN", "FAIL"
        details : str
            Additional details/values (e.g., "60862 pixels", "48 minutiae extracted")
        """
        self.step_count += 1
        self.steps.append({
            "step": str(self.step_count),
            "operation": operation,
            "status": status,
            "details": details,
        })

    def display_table(self) -> None:
        """Display all collected steps as a formatted table."""
        if not self.steps:
            return

        # Color-code status values
        styled_steps = []
        for step in self.steps:
            styled_row = step.copy()
            status = step["status"]

            # Apply color based on status
            if status == "OK":
                styled_row["status"] = "[green]OK[/green]"
            elif status == "SKIP":
                styled_row["status"] = "[yellow]SKIP[/yellow]"
            elif status == "WARN":
                styled_row["status"] = "[yellow]WARN[/yellow]"
            elif status == "FAIL":
                styled_row["status"] = "[red]FAIL[/red]"

            styled_steps.append([
                styled_row["step"],
                styled_row["operation"],
                styled_row["status"],
                styled_row["details"],
            ])

        title = f"{self.operation_name} Pipeline - {self.image_filename}"
        headers = ["Step", "Operation", "Status", "Details"]

        log_table(
            title=title,
            headers=headers,
            rows=styled_steps,
        )


class EnrollmentProgressTracker(PipelineProgressTracker):
    """Specialized tracker for enrollment pipeline."""

    def __init__(self, image_filename: str):
        super().__init__("Enrollment", image_filename)
        # Pre-define standard enrollment steps
        self._define_standard_steps()

    def _define_standard_steps(self) -> None:
        """Define the standard enrollment pipeline steps."""
        standard_steps = [
            "Load image",
            "Segmentation",
            "Gabor enhancement",
            "Thinning",
            "Singular point detection",
            "Minutiae extraction",
            "Clustering filter",
            "Edge filter",
            "PCA alignment",
            "Quantization",
            "Secret key generation",
            "RS encoding",
            "Vault creation",
        ]
        # Initialize all steps as pending
        for step in standard_steps:
            self.steps.append({
                "step": str(len(self.steps) + 1),
                "operation": step,
                "status": "PENDING",
                "details": "",
            })

    def update_step(self, step_number: int, status: str, details: str = "") -> None:
        """
        Update a pre-defined step with results.

        Parameters
        ----------
        step_number : int
            Step number to update (1-indexed)
        status : str
            Status of operation
        details : str
            Details/result values
        """
        if 0 < step_number <= len(self.steps):
            self.steps[step_number - 1]["status"] = status
            self.steps[step_number - 1]["details"] = details


class VerificationProgressTracker(PipelineProgressTracker):
    """Specialized tracker for verification pipeline."""

    def __init__(self, image_filename: str):
        super().__init__("Verification", image_filename)
        # Pre-define standard verification steps
        self._define_standard_steps()

    def _define_standard_steps(self) -> None:
        """Define the standard verification pipeline steps."""
        standard_steps = [
            "Load probe image",
            "Segmentation",
            "Gabor enhancement",
            "Thinning",
            "Minutiae extraction",
            "Clustering filter",
            "Edge filter",
            "PCA alignment",
            "Quantization",
            "XOR matching",
            "Threshold comparison",
        ]
        # Initialize all steps as pending
        for step in standard_steps:
            self.steps.append({
                "step": str(len(self.steps) + 1),
                "operation": step,
                "status": "PENDING",
                "details": "",
            })

    def update_step(self, step_number: int, status: str, details: str = "") -> None:
        """
        Update a pre-defined step with results.

        Parameters
        ----------
        step_number : int
            Step number to update (1-indexed)
        status : str
            Status of operation
        details : str
            Details/result values
        """
        if 0 < step_number <= len(self.steps):
            self.steps[step_number - 1]["status"] = status
            self.steps[step_number - 1]["details"] = details
