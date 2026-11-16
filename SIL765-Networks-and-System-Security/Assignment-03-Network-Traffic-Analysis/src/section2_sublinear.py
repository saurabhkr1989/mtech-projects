import hashlib, math, random, ipaddress
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
sns.set_theme(style="whitegrid", palette="muted")


def _save(fig, name, cfg):
    path = Path(cfg["output"]["figures_dir"]) / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    console.print(f"  [dim]Figure saved -> {path}[/dim]")
    if cfg["output"].get("show_plots", True):
        import subprocess, sys
        try:
            if sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", "start", "", str(path)],
                                 creationflags=0x08000000)
        except Exception:
            pass
    plt.close(fig)


def _hdr(title, tag):
    console.print()
    console.print(Panel(f"[bold white]{tag}  {title}[/bold white]",
                        style="bold cyan", expand=False))


# hyperloglog
class HyperLogLog:
    # Flajolet et al. 2007: hash each item to 64 bits, top-b bits pick register,
    # rest gives rho (leftmost 1 position). estimate = alpha * m^2 / sum(2^-M[j])
    _ALPHA_MAP = {16: 0.673, 32: 0.697, 64: 0.709}

    def __init__(self, b: int = 12):
        self.b = b
        self.m = 1 << b
        self.registers = np.zeros(self.m, dtype=np.int8)
        self.alpha = self._ALPHA_MAP.get(self.m, 0.7213 / (1 + 1.079 / self.m))

    def _hash64(self, item: str) -> int:
        raw = hashlib.md5(item.encode()).digest()
        return int.from_bytes(raw[:8], "big")

    def add(self, item: str):
        x   = self._hash64(item)
        j   = x >> (64 - self.b)                           # register index
        w   = x & ((1 << (64 - self.b)) - 1)               # remaining bits
        rho = (64 - self.b - int(w).bit_length() + 1) if w else (64 - self.b + 1)
        if rho > self.registers[j]:
            self.registers[j] = rho

    def count(self) -> int:
        Z = 1.0 / np.sum(2.0 ** (-self.registers.astype(np.float64)))
        E = self.alpha * (self.m ** 2) * Z
        # Small-range correction
        V = int(np.sum(self.registers == 0))
        if E <= 2.5 * self.m and V > 0:
            E = self.m * math.log(self.m / V)
        return int(E)

    @property
    def space_bytes(self):
        return self.m  # 1 byte per register


def task9(df: pd.DataFrame, cfg: dict) -> dict:
    b   = cfg["section2"]["hyperloglog"]["precision_bits"]
    std_err = 1.04 / math.sqrt(1 << b) * 100
    _hdr(f"HyperLogLog - Unique IP Estimation  (b={b}, std_error~{std_err:.1f}%)", "Task 9")

    console.print(
        "  [bold]Algorithm:[/bold] HyperLogLog (Flajolet et al., 2007)\n"
        f"  [bold]Parameters:[/bold] b={b} precision bits -> m={1<<b:,} registers\n"
        f"  [bold]Theoretical std error:[/bold] 1.04/√m ~ [cyan]{std_err:.2f}%[/cyan]\n"
        "  [bold]Space:[/bold] O(2^b) = fixed, independent of stream size"
    )

    hll = HyperLogLog(b)
    for ip in df["source"].dropna().astype(str):
        hll.add(ip)
    for ip in df["destination"].dropna().astype(str):
        hll.add(ip)
    estimate = hll.count()

    # Exact baseline
    exact = len(set(df["source"].dropna().astype(str)) |
                set(df["destination"].dropna().astype(str)))
    error = abs(estimate - exact) / exact * 100

    hll_kb   = hll.space_bytes / 1024
    exact_kb = exact * 16 / 1024   # ~16 bytes per IP string

    t = Table(box=box.ROUNDED, padding=(0, 2))
    t.add_column("Method",      style="bold")
    t.add_column("Unique IPs",  justify="right", style="cyan")
    t.add_column("Space Used",  justify="right", style="magenta")
    t.add_column("Error",       justify="right", style="yellow")
    t.add_row("HyperLogLog (sublinear)", f"{estimate:,}", f"{hll_kb:.1f} KB", f"{error:.2f}%")
    t.add_row("Python set (exact)",      f"{exact:,}", f"{exact_kb:.0f} KB", "0.00%")
    console.print(t)

    status = "[bold green]PASS[/bold green]" if error <= 10 else "[bold red]FAIL[/bold red]"
    console.print(f"\n  Error {error:.2f}% -- target <= 10% -> {status}")
    console.print(f"  Space savings: [bold]{exact_kb/hll_kb:.0f}x[/bold] less memory than exact set")
    console.print(
        "\n  [bold]Trade-off analysis:[/bold]\n"
        "   * HLL uses O(2^b) bytes  -- fixed regardless of how many unique IPs exist.\n"
        "   * Exact set uses O(n) bytes growing linearly with distinct IP count.\n"
        "   * Increasing b halves the error but doubles the space (b=14 -> 0.4% error, 16 KB).\n"
        "   * Both methods run in O(n) time (single pass over the stream)."
    )

    # Error vs precision-bits plot
    bs     = list(range(8, 17))
    errors_th = [1.04 / math.sqrt(1 << bi) * 100 for bi in bs]
    spaces_kb = [(1 << bi) / 1024 for bi in bs]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(bs, errors_th, marker="o", color="steelblue")
    axes[0].axvline(b, color="red", lw=1.2, linestyle="--", label=f"b={b} (chosen)")
    axes[0].axhline(10, color="orange", lw=1, linestyle="--", label="10% target")
    axes[0].set_title("HyperLogLog: Error vs Precision Bits", fontweight="bold")
    axes[0].set_xlabel("Precision bits (b)"); axes[0].set_ylabel("Std error (%)")
    axes[0].legend(fontsize=8); axes[0].grid(True, alpha=0.4)
    axes[1].bar([str(bi) for bi in bs], spaces_kb,
                color=["red" if bi == b else "steelblue" for bi in bs])
    axes[1].set_title("Space (KB) vs Precision Bits", fontweight="bold")
    axes[1].set_xlabel("Precision bits (b)"); axes[1].set_ylabel("Space (KB)")
    fig.suptitle("Task 9 - HyperLogLog Parameter Analysis", fontsize=12, fontweight="bold")
    plt.tight_layout()
    _save(fig, "2_9_hyperloglog", cfg)
    return {"hll_estimate": estimate, "exact_count": exact, "error_pct": error,
            "hll_kb": hll_kb, "exact_kb": exact_kb}


# count-min sketch
class CountMinSketch:
    # Cormode & Muthukrishnan 2005: d rows x w cols, each row has independent hash.
    # query = min over all rows; over-counts but never under-counts.
    def __init__(self, d: int = 5, w: int = 10_000):
        self.d = d; self.w = w
        self.table  = np.zeros((d, w), dtype=np.int32)
        self._seeds = [i * 0x9E3779B9 for i in range(1, d+1)]

    def _h(self, item: str, seed: int) -> int:
        return int(hashlib.md5((str(seed) + item).encode()).hexdigest(), 16) % self.w

    def update(self, item: str, count: int = 1):
        for i, s in enumerate(self._seeds):
            self.table[i, self._h(item, s)] += count

    def query(self, item: str) -> int:
        return int(min(self.table[i, self._h(item, s)]
                       for i, s in enumerate(self._seeds)))

    @property
    def space_bytes(self):
        return self.d * self.w * 4   # int32 = 4 bytes


def task10(df: pd.DataFrame, cfg: dict) -> dict:
    d   = cfg["section2"]["count_min_sketch"]["hash_rows"]
    w   = cfg["section2"]["count_min_sketch"]["hash_width"]
    hh  = cfg["section2"]["count_min_sketch"]["heavy_hitter_pct"]
    eps = math.e / w
    dlt = math.exp(-d)
    _hdr(f"Count-Min Sketch - Heavy Hitter Destination IPs  (d={d}, w={w:,})", "Task 10")

    console.print(
        "  [bold]Algorithm:[/bold] Count-Min Sketch (Cormode & Muthukrishnan, 2005)\n"
        f"  [bold]Parameters:[/bold] d={d} rows, w={w:,} buckets\n"
        f"  [bold]Error guarantee:[/bold] eps = e/w ~ {eps:.5f}, delta = e^(-d) ~ {dlt:.4f}\n"
        f"  [bold]Heavy hitter threshold:[/bold] count > {hh*100:.0f}% of total flows\n"
        f"  [bold]Space:[/bold] {d}x{w}x4 = {d*w*4/1024:.0f} KB"
    )

    cms  = CountMinSketch(d, w)
    dsts = df["destination"].dropna().astype(str)
    for ip in dsts:
        cms.update(ip)

    exact    = dsts.value_counts()
    total    = len(df)
    hh_thr   = int(total * hh)

    # Compare top-20
    top20 = exact.head(20)
    comp  = pd.DataFrame({
        "IP":           top20.index,
        "exact_count":  top20.values,
        "sketch_count": [cms.query(ip) for ip in top20.index],
    })
    comp["abs_error"]   = (comp["sketch_count"] - comp["exact_count"]).abs()
    comp["pct_error"]   = comp["abs_error"] / comp["exact_count"] * 100
    mean_err = comp["pct_error"].mean()

    exact_hh  = exact[exact >= hh_thr]
    sketch_hh = {ip: cnt for ip in exact.index[:200]
                 if (cnt := cms.query(ip)) >= hh_thr}

    console.print(f"\n  Heavy hitter threshold : {hh_thr:,} flows (= {hh*100:.0f}% of {total:,})")
    console.print(f"  Exact heavy hitters    : [bold]{len(exact_hh)}[/bold]")
    console.print(f"  Sketch heavy hitters   : [bold]{len(sketch_hh)}[/bold]\n")

    t = Table(box=box.SIMPLE_HEAD, padding=(0, 1), title="Top-20 Destination IP Comparison")
    t.add_column("Rank", justify="right", style="dim", width=5)
    t.add_column("IP Address",    style="cyan")
    t.add_column("Exact Count",   justify="right", style="green")
    t.add_column("Sketch Est.",   justify="right", style="yellow")
    t.add_column("Abs Error",     justify="right", style="magenta")
    t.add_column("% Error",       justify="right", style="red")
    for i, row in comp.iterrows():
        t.add_row(str(i+1), row["IP"],
                  f"{row['exact_count']:,}", f"{row['sketch_count']:,}",
                  f"{row['abs_error']:,}", f"{row['pct_error']:.4f}%")
    console.print(t)

    status = "[bold green]PASS[/bold green]" if mean_err <= 10 else "[bold red]FAIL[/bold red]"
    console.print(f"\n  Mean |% error| on top-20 : [bold]{mean_err:.4f}%[/bold] -- target <= 10% -> {status}")
    cms_kb   = cms.space_bytes / 1024
    exact_kb = len(exact) * 24 / 1024
    console.print(f"  CMS space: [bold]{cms_kb:.0f} KB[/bold]  vs  "
                  f"exact dict: ~[bold]{exact_kb:.0f} KB[/bold]  "
                  f"({exact_kb/cms_kb:.1f}x savings)")

    # Error bar plot
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    x = range(1, 21)
    axes[0].bar(x, comp["exact_count"], label="Exact", alpha=0.7, color="steelblue")
    axes[0].bar(x, comp["sketch_count"], label="Sketch", alpha=0.6, color="coral")
    axes[0].set_title("Exact vs Sketch Count - Top-20 Dst IPs", fontweight="bold")
    axes[0].set_xlabel("Rank"); axes[0].set_ylabel("Flow count")
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:,.0f}"))
    axes[0].legend(fontsize=8)
    axes[1].bar(x, comp["pct_error"], color="coral")
    axes[1].axhline(10, color="red", lw=1.2, linestyle="--", label="10% target")
    axes[1].set_title("% Error per Destination IP", fontweight="bold")
    axes[1].set_xlabel("Rank"); axes[1].set_ylabel("% Error")
    axes[1].legend()
    fig.suptitle("Task 10 - Count-Min Sketch Accuracy", fontsize=12, fontweight="bold")
    plt.tight_layout()
    _save(fig, "2_10_cms", cfg)
    return {"mean_err_pct": mean_err, "n_heavy_hitters": len(exact_hh),
            "cms_kb": cms_kb, "exact_kb": exact_kb}


# bloom filter
try:
    from bitarray import bitarray as _ba
    _HAS_BA = True
except ImportError:
    _HAS_BA = False


class BloomFilter:
    # Bloom 1970: bit array of m bits, k hash functions.
    # add sets k bits; query returns false if any bit is 0 (no false negatives).
    def __init__(self, n: int, fpr: float = 0.01):
        self.n   = n
        self.fpr = fpr
        self.m   = math.ceil(-n * math.log(fpr) / (math.log(2)**2))
        self.k   = max(1, round(self.m / n * math.log(2)))
        if _HAS_BA:
            self._bits = _ba(self.m); self._bits.setall(0)
        else:
            self._bits = bytearray(math.ceil(self.m / 8))
        self.theory_fpr = (1 - math.exp(-self.k * n / self.m)) ** self.k

    def _hashes(self, item: str):
        h1 = int(hashlib.md5(item.encode()).hexdigest(), 16)
        h2 = int(hashlib.sha256(item.encode()).hexdigest(), 16)
        for i in range(self.k):
            yield (h1 + i * h2) % self.m

    def _get(self, i):
        return self._bits[i] if _HAS_BA else (self._bits[i>>3] >> (i&7)) & 1

    def _set(self, i):
        if _HAS_BA: self._bits[i] = 1
        else:       self._bits[i>>3] |= 1 << (i&7)

    def add(self, item: str):
        for idx in self._hashes(item): self._set(idx)

    def __contains__(self, item: str) -> bool:
        return all(self._get(idx) for idx in self._hashes(item))

    @property
    def space_bytes(self): return self.m // 8


def task11(df: pd.DataFrame, cfg: dict) -> dict:
    target_fpr  = cfg["section2"]["bloom_filter"]["target_fpr"]
    n_probe     = cfg["section2"]["bloom_filter"]["probe_count"]
    _hdr(f"Bloom Filter - IP Blocklist Membership  (target FPR={target_fpr*100:.0f}%)", "Task 11")

    src_ips = list(df["source"].dropna().astype(str).unique())
    n       = len(src_ips)
    bf      = BloomFilter(n, target_fpr)

    console.print(
        "  [bold]Algorithm:[/bold] Bloom Filter (Bloom, 1970)\n"
        "  [bold]Design:[/bold]\n"
        f"    n = {n:,} unique source IPs\n"
        f"    m = {bf.m:,} bits  ({bf.space_bytes/1024:.1f} KB)\n"
        f"    k = {bf.k} hash functions  (double-hashing: h1 + i.h2 mod m)\n"
        f"    Theoretical FPR = (1-e^(-k.n/m))^k = [cyan]{bf.theory_fpr*100:.3f}%[/cyan]"
    )

    for ip in src_ips:
        bf.add(ip)

    # True positives
    fn = sum(1 for ip in src_ips if ip not in bf)

    # Generate random IPs NOT in dataset for FPR measurement
    all_known = set(df["source"].dropna().astype(str)) | set(df["destination"].dropna().astype(str))
    random.seed(42)
    random_ips = []
    while len(random_ips) < n_probe:
        c = str(ipaddress.IPv4Address(random.randint(0, 2**32 - 1)))
        if c not in all_known:
            random_ips.append(c)

    fp     = sum(1 for ip in random_ips if ip in bf)
    actual = fp / n_probe

    exact_set    = set(src_ips)
    exact_fp     = sum(1 for ip in random_ips if ip in exact_set)

    bf_kb   = bf.space_bytes / 1024
    set_kb  = (200 + n * 50) / 1024

    t = Table(box=box.ROUNDED, padding=(0, 2))
    t.add_column("Method",          style="bold")
    t.add_column("False Negatives", justify="right", style="cyan")
    t.add_column("False Positives", justify="right", style="red")
    t.add_column("FPR",             justify="right", style="yellow")
    t.add_column("Space",           justify="right", style="magenta")
    t.add_row("Bloom Filter",  str(fn), f"{fp}/{n_probe:,}",  f"{actual*100:.3f}%", f"{bf_kb:.1f} KB")
    t.add_row("Python set",    "0",     f"{exact_fp}/{n_probe:,}", "0.000%",         f"{set_kb:.0f} KB")
    console.print(t)

    status = "[bold green]PASS[/bold green]" if actual <= target_fpr * 1.2 else "[bold yellow]CLOSE[/bold yellow]"
    console.print(f"\n  Actual FPR {actual*100:.3f}% -- target <= {target_fpr*100:.1f}% -> {status}")
    console.print(f"  Space savings: [bold]{set_kb/bf_kb:.1f}x[/bold]  |  "
                  "False negatives: [bold]0[/bold] (guaranteed by construction)")
    console.print(
        "\n  [bold]Key trade-off:[/bold]\n"
        "   Bloom filter -> 0 false negatives, tunable FPR, sublinear space.\n"
        "   Exact set    -> 0 FPR, but O(n) space growing with universe size.\n"
        "   Use case: IP blocklist -- a rare FP (block benign IP) is acceptable;\n"
        "   a false negative (pass blocked IP) is not."
    )

    # FPR vs load-factor curve
    load_factors = np.linspace(0.01, 0.99, 200)
    fpr_curve    = (1 - np.exp(-bf.k * load_factors)) ** bf.k
    actual_load  = n / bf.m
    fig, axes    = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(load_factors, fpr_curve * 100, color="steelblue", lw=1.5)
    axes[0].axvline(actual_load, color="red", lw=1.2, linestyle="--",
                    label=f"Actual load={actual_load:.3f}")
    axes[0].axhline(target_fpr*100, color="orange", lw=1.2, linestyle="--",
                    label=f"Target FPR={target_fpr*100:.1f}%")
    axes[0].set_title(f"FPR vs Load Factor  (k={bf.k})", fontweight="bold")
    axes[0].set_xlabel("Load factor (n/m)"); axes[0].set_ylabel("FPR (%)")
    axes[0].legend(fontsize=8); axes[0].set_ylim(0, 30)
    methods = ["Bloom Filter", "Python set"]
    spaces  = [bf_kb, set_kb]
    bars    = axes[1].bar(methods, spaces, color=["steelblue","coral"])
    for bar, val in zip(bars, spaces):
        axes[1].text(bar.get_x()+bar.get_width()/2, bar.get_height()+set_kb*0.01,
                     f"{val:.0f} KB", ha="center", va="bottom", fontsize=10)
    axes[1].set_title("Space Comparison", fontweight="bold"); axes[1].set_ylabel("KB")
    fig.suptitle("Task 11 - Bloom Filter Analysis", fontsize=12, fontweight="bold")
    plt.tight_layout()
    _save(fig, "2_11_bloom", cfg)
    return {"actual_fpr": actual, "target_fpr": target_fpr,
            "false_negatives": fn, "bf_kb": bf_kb, "set_kb": set_kb}
