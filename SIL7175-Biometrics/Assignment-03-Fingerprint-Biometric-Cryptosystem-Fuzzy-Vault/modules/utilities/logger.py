"""
logger.py -- Colored, structured console output using the `rich` library.

All other modules import from here so that every log line is consistently
formatted and color-coded.  No module should ever call print() directly.

Color / icon convention (ASCII-safe for Windows cp1252 terminals)
-----------------------------------------------------------------
  [*]  Magenta  -- Section banner (major pipeline stage)
  [->] Cyan     -- Step indicator (sub-task in progress)
  [OK] Green    -- Success / completion
  [!]  Yellow   -- Warning (non-fatal, but worth noting)
  [X]  Red      -- Error / failure
  [=]  Blue     -- Data / value display
"""

import sys
import os
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

# Force the console to use UTF-8 encoding on Windows.
if os.name == 'nt':
    os.system('chcp 65001 > nul')

# Force the console to use the correct encoding on Windows.
# Setting force_terminal=True ensures rich uses ANSI codes rather than
# the legacy Windows renderer that cannot handle non-cp1252 characters.
console = Console(force_terminal=True, highlight=False, legacy_windows=False, width=100)

# Global quiet flag: when True, suppresses verbose logging (step/data messages)
# but keeps section headers and important messages (success/warning/error)
_QUIET_MODE = False

def set_quiet_mode(quiet: bool) -> None:
    """Set global quiet mode. When True, suppresses verbose log_step and log_data output."""
    global _QUIET_MODE
    _QUIET_MODE = quiet

def get_quiet_mode() -> bool:
    """Get current quiet mode setting."""
    return _QUIET_MODE


# ---------------------------------------------------------------------------
# Core logging functions
# ---------------------------------------------------------------------------

def log_section(title: str) -> None:
    """Print a bold magenta banner marking the start of a major pipeline stage."""
    separator = "=" * (len(title) + 8)
    console.print()
    console.print(f"[bold magenta]{separator}[/bold magenta]")
    console.print(f"[bold white on magenta]    [*]  {title}    [/bold white on magenta]")
    console.print(f"[bold magenta]{separator}[/bold magenta]")
    console.print()


def log_step(message: str) -> None:
    """Print a cyan step indicator for a sub-task in progress. Suppressed in quiet mode."""
    if not _QUIET_MODE:
        console.print(f"[cyan]  [>>]  {message}[/cyan]")


def log_success(message: str) -> None:
    """Print a green success message."""
    console.print(f"[bold green]  [OK]  {message}[/bold green]")


def log_warning(message: str) -> None:
    """Print a yellow warning message (non-fatal)."""
    console.print(f"[bold yellow]  [!]  WARNING: {message}[/bold yellow]")


def log_error(message: str) -> None:
    """Print a red error message."""
    console.print(f"[bold red]  [X]  ERROR: {message}[/bold red]")


def log_data(label: str, value) -> None:
    """Print a blue label: value pair for displaying computed data. Suppressed in quiet mode."""
    if not _QUIET_MODE:
        console.print(f"[blue]  [=]  {label}:[/blue] [white]{value}[/white]")


# ---------------------------------------------------------------------------
# Rich table helper
# ---------------------------------------------------------------------------

def log_table(title: str, headers: list[str], rows: list[list]) -> None:
    """
    Print a formatted rich table to the console.

    Parameters
    ----------
    title   : Table caption shown above the table.
    headers : Column header strings.
    rows    : List of rows, each row being a list of cell values.
    """
    table = Table(
        title=title,
        box=box.ROUNDED,
        border_style="bright_blue",
        header_style="bold cyan",
        show_lines=True,
    )

    for header_name in headers:
        table.add_column(header_name, justify="center")

    for row_values in rows:
        # Convert every cell to a string so rich does not choke on floats
        table.add_row(*[str(cell) for cell in row_values])

    console.print(table)


# ---------------------------------------------------------------------------
# Verdict display helper (used by vault decoder)
# ---------------------------------------------------------------------------

def log_verdict(is_genuine: bool, subject_label: str = "") -> None:
    """Print a large, colored GENUINE / IMPOSTOR verdict."""
    label_suffix = f" - {subject_label}" if subject_label else ""
    if is_genuine:
        console.print(
            f"[bold green]  [OK]  VERDICT: GENUINE{label_suffix}[/bold green]"
        )
    else:
        console.print(
            f"[bold red]  [X]  VERDICT: IMPOSTOR{label_suffix}[/bold red]"
        )
