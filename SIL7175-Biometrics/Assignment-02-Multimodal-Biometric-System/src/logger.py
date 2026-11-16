"""
Centralised console logging for the pipeline.

Modules import BiometricLogger for consistent formatting, 
phase headers, and timing readouts.

Usage:
    from src.logger import log

    log.phase("Feature Extraction")
    log.info("Processing user 001")
    log.ok("Done — 4096-dim vector extracted")
    log.warn("Pupil radius near threshold — result may be imprecise")
    log.error("Image load failed: /path/to/img.jpg")
    log.progress(current=42, total=100, label="Users processed")
"""

import sys
import time

# ANSI escape colour codes.
_RESET   = "\033[0m"
_BOLD    = "\033[1m"
_DIM     = "\033[2m"
_GREEN   = "\033[92m"
_YELLOW  = "\033[93m"
_RED     = "\033[91m"
_CYAN    = "\033[96m"
_MAGENTA = "\033[95m"
_BLUE    = "\033[94m"
_WHITE   = "\033[97m"


class BiometricLogger:
    """
    Lightweight structured logger.
    
    Prefixes messages with a coloured tag for phases, progress, 
    warnings, and errors.
    """

    def __init__(self, use_colour: bool = True):
        # Disable colour when output is redirected to a file
        self._colour = use_colour and sys.stdout.isatty()
        self._phase_start_time = None

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    def _c(self, code: str, text: str) -> str:
        """Wraps text in the given ANSI code if colour is enabled."""
        if self._colour:
            return f"{code}{text}{_RESET}"
        return text

    def _emit(self, tag: str, colour: str, message: str):
        """Prints a consistently formatted log line to stdout."""
        label = self._c(colour + _BOLD, f"[{tag:^9}]")
        print(f"{label}  {message}", flush=True)

    # ------------------------------------------------------------------ #
    # Public API                                                            #
    # ------------------------------------------------------------------ #

    def phase(self, phase_name: str):
        """
        Prints a prominent separator marking the start of a pipeline phase.
        Also starts an internal timer so the elapsed time can be reported
        later via phase_done().
        """
        self._phase_start_time = time.time()
        bar = self._c(_CYAN + _BOLD, "=" * 60)
        title = self._c(_CYAN + _BOLD, f"  PHASE: {phase_name}")
        print(f"\n{bar}", flush=True)
        print(title, flush=True)
        print(bar, flush=True)

    def phase_done(self, phase_name: str):
        """Prints a phase completion footer with elapsed time."""
        elapsed = time.time() - self._phase_start_time if self._phase_start_time else 0
        msg = f"Phase '{phase_name}' complete in {elapsed:.1f}s"
        bar = self._c(_CYAN + _DIM, "-" * 60)
        print(f"{bar}", flush=True)
        self._emit("DONE", _GREEN, msg)
        print(f"{bar}\n", flush=True)

    def step(self, step_label: str):
        """Prints a sub-step header within a phase (less prominent than phase())."""
        label = self._c(_BLUE + _BOLD, f"--- {step_label} ---")
        print(f"\n{label}", flush=True)

    def info(self, message: str):
        """General informational message — routine progress."""
        self._emit("INFO", _WHITE, message)

    def ok(self, message: str):
        """Success / completion confirmation."""
        self._emit("OK", _GREEN, message)

    def warn(self, message: str):
        """Non-fatal issue that the user should be aware of."""
        self._emit("WARN", _YELLOW, message)

    def error(self, message: str):
        """An error occurred. Pipeline continues unless caller raises."""
        self._emit("ERROR", _RED, message)

    def skip(self, message: str):
        """Indicates a user or file was skipped (not an error)."""
        self._emit("SKIP", _MAGENTA, message)

    def csv(self, filepath: str, row_count: int):
        """Confirms a CSV file was written successfully."""
        self._emit("CSV", _GREEN, f"Saved {row_count} rows → {filepath}")

    def model(self, message: str):
        """Deep learning model events (loading, saving, training epoch)."""
        self._emit("MODEL", _MAGENTA, message)

    def progress(self, current: int, total: int, label: str = ""):
        """
        Prints a compact progress line.
        Uses carriage return so successive calls overwrite the same line
        when colour/TTY is available, reducing console noise on long loops.
        """
        pct = int(100 * current / max(total, 1))
        filled = int(30 * current / max(total, 1))
        bar_str = "█" * filled + "░" * (30 - filled)
        coloured_bar = self._c(_CYAN, f"[{bar_str}]")
        suffix = f" {label}" if label else ""
        line = f"\r  {coloured_bar} {pct:3d}% ({current}/{total}){suffix}"
        if current >= total:
            # Final call — move to next line
            print(line, flush=True)
        else:
            print(line, end="", flush=True)

    def separator(self):
        """Prints a plain divider line."""
        print(self._c(_DIM, "-" * 60), flush=True)


# Module-level instance
log = BiometricLogger()
