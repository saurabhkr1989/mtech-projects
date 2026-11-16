import time
from pathlib import Path

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

NEEDED_COLS = [
    "source", "destination", "sourcePort", "destinationPort",
    "protocolName", "appName",
    "totalSourceBytes", "totalDestinationBytes",
    "totalSourcePackets", "totalDestinationPackets",
    "startDateTime", "stopDateTime",
    "sourceTCPFlagsDescription", "destinationTCPFlagsDescription",
    "sourcePayloadAsUTF", "destinationPayloadAsUTF",
    "direction", "Label",
]


def load(cfg: dict) -> pd.DataFrame:
    files = cfg["data"]["abs_files"]
    chunk_size = cfg["data"].get("chunk_size", 100_000)

    console.print()
    console.rule("[bold cyan]Loading Dataset[/bold cyan]")
    console.print(f"  Base directory : [yellow]{cfg['data']['base_dir']}[/yellow]")
    console.print(f"  Chunk size     : [yellow]{chunk_size:,} rows[/yellow]")
    console.print(f"  Files to load  : [yellow]{len(files)}[/yellow]\n")

    file_table = Table(box=box.SIMPLE_HEAD, show_edge=False, padding=(0, 1))
    file_table.add_column("#",         style="dim",    justify="right",  width=4)
    file_table.add_column("Filename",  style="cyan",                     min_width=32)
    file_table.add_column("Size (MB)", justify="right", style="magenta", width=10)
    file_table.add_column("Rows",      justify="right", style="green",   width=12)
    file_table.add_column("Load time", justify="right", style="yellow",  width=10)

    all_dfs, total_rows, total_bytes_sz = [], 0, 0

    for idx, fpath in enumerate(files, 1):
        fpath = Path(fpath)
        if not fpath.exists():
            console.print(f"  [red]MISSING[/red] {fpath}")
            continue
        size_mb = fpath.stat().st_size / 1e6
        total_bytes_sz += fpath.stat().st_size

        t0 = time.perf_counter()
        chunks = []
        for chunk in pd.read_csv(fpath, chunksize=chunk_size,
                                  usecols=NEEDED_COLS, low_memory=False):
            chunks.append(chunk)
        fdf = pd.concat(chunks, ignore_index=True)
        elapsed = time.perf_counter() - t0

        all_dfs.append(fdf)
        total_rows += len(fdf)
        file_table.add_row(
            str(idx),
            fpath.name,
            f"{size_mb:.1f}",
            f"{len(fdf):,}",
            f"{elapsed:.1f}s",
        )

    console.print(file_table)
    console.print(f"  [bold green]Total:[/bold green] {len(files)} files | "
                  f"[bold green]{total_rows:,}[/bold green] flows | "
                  f"[bold green]{total_bytes_sz/1e6:.0f} MB[/bold green] on disk\n")

    df = pd.concat(all_dfs, ignore_index=True)

    df["startDateTime"] = pd.to_datetime(df["startDateTime"], errors="coerce")
    df["stopDateTime"]  = pd.to_datetime(df["stopDateTime"],  errors="coerce")

    for col in ["totalSourceBytes", "totalDestinationBytes",
                "totalSourcePackets", "totalDestinationPackets"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["totalBytes"]   = df["totalSourceBytes"]   + df["totalDestinationBytes"]
    df["totalPackets"] = df["totalSourcePackets"]  + df["totalDestinationPackets"]
    df["duration_s"]   = (df["stopDateTime"] - df["startDateTime"]).dt.total_seconds().clip(lower=0)
    df["avg_pkt_bytes"] = np.where(df["totalPackets"] > 0,
                                   df["totalBytes"] / df["totalPackets"], np.nan)

    ov = Table(title="Dataset Overview", box=box.ROUNDED, padding=(0, 2))
    ov.add_column("Metric",  style="bold")
    ov.add_column("Value",   style="cyan")

    date_min = df["startDateTime"].min()
    date_max = df["stopDateTime"].max()
    ov.add_row("Total flows",           f"{len(df):,}")
    ov.add_row("Columns loaded",        str(len(df.columns)))
    ov.add_row("Unique source IPs",     f"{df['source'].nunique():,}")
    ov.add_row("Unique destination IPs",f"{df['destination'].nunique():,}")
    ov.add_row("Unique protocols",      f"{df['protocolName'].nunique():,}")
    ov.add_row("Date range (start)",    str(date_min)[:19] if pd.notna(date_min) else "N/A")
    ov.add_row("Date range (end)",      str(date_max)[:19] if pd.notna(date_max) else "N/A")
    ov.add_row("Memory usage",          f"{df.memory_usage(deep=True).sum()/1e6:.1f} MB")
    console.print(ov)
    console.print()

    return df
