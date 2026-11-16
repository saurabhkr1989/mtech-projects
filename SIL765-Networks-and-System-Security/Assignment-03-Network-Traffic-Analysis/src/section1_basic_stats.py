import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for saving; show() handled separately
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


# helpers

def _save(fig, name: str, cfg: dict):
    path = Path(cfg["output"]["figures_dir"]) / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    console.print(f"  [dim]Figure saved -> {path}[/dim]")
    if cfg["output"].get("show_plots", True):
        import subprocess, sys
        # reopen with PIL / OS viewer so CLI doesn't block
        try:
            if sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", "start", "", str(path)],
                                 creationflags=0x08000000)
        except Exception:
            pass
    plt.close(fig)


def _section_header(title: str, task_id: str):
    console.print()
    console.print(Panel(f"[bold white]{task_id}  {title}[/bold white]",
                        style="bold cyan", expand=False))


# task 1.1 - total flows

def task1(df: pd.DataFrame, cfg: dict) -> dict:
    _section_header("Total Number of Network Flows", "Task 1.1")
    t = Table(box=box.ROUNDED, padding=(0, 2))
    t.add_column("Metric",              style="bold")
    t.add_column("Value",               style="cyan", justify="right")
    t.add_row("Total flows",            f"{len(df):,}")
    t.add_row("Unique source IPs",      f"{df['source'].nunique():,}")
    t.add_row("Unique destination IPs", f"{df['destination'].nunique():,}")
    t.add_row("Unique (src, dst) pairs",f"{df.groupby(['source','destination']).ngroups:,}")
    t.add_row("Unique protocols",       f"{df['protocolName'].nunique():,}")
    t.add_row("Unique app names",       f"{df['appName'].nunique():,}")
    t.add_row("Date range start",       str(df["startDateTime"].min())[:19])
    t.add_row("Date range end",         str(df["stopDateTime"].max())[:19])
    t.add_row("Total bytes transferred",f"{df['totalBytes'].sum()/1e9:.2f} GB")
    t.add_row("Total packets",          f"{df['totalPackets'].sum():,.0f}")
    console.print(t)
    return {"total_flows": len(df)}


# task 1.2 - top-k protocols

def task2(df: pd.DataFrame, cfg: dict) -> dict:
    k = cfg["section1"]["top_k_protocols"]
    _section_header(f"Top-{k} Most Frequently Used Protocols  (k={k} -- configurable in config.yaml)", "Task 1.2")

    proto_cnt = df["protocolName"].value_counts()
    total     = len(df)
    top_k     = proto_cnt.head(k)

    t = Table(box=box.ROUNDED, padding=(0, 2))
    t.add_column("Rank",       justify="right",  style="dim",    width=6)
    t.add_column("Protocol",   style="bold cyan")
    t.add_column("Flows",      justify="right",  style="green")
    t.add_column("% of Total", justify="right",  style="magenta")
    t.add_column("Cumulative %",justify="right", style="yellow")
    cum = 0.0
    for rank, (proto, cnt) in enumerate(top_k.items(), 1):
        pct = cnt / total * 100
        cum += pct
        t.add_row(str(rank), proto, f"{cnt:,}", f"{pct:.2f}%", f"{cum:.2f}%")
    console.print(t)
    console.print(f"\n  [dim]Remaining {len(proto_cnt)-k} protocol(s) account for "
                  f"{(1 - top_k.sum()/total)*100:.2f}% of flows.[/dim]")

    # Bar chart + pie chart side by side
    all_k_label = list(top_k.index) + (["Others"] if len(proto_cnt) > k else [])
    all_k_vals  = list(top_k.values) + ([proto_cnt.iloc[k:].sum()] if len(proto_cnt) > k else [])

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    # Bar
    colors = sns.color_palette("muted", len(all_k_label))
    axes[0].bar(all_k_label, all_k_vals, color=colors, edgecolor="white")
    axes[0].set_title(f"Top-{k} Protocols by Flow Count", fontweight="bold")
    axes[0].set_xlabel("Protocol")
    axes[0].set_ylabel("Number of Flows")
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    axes[0].tick_params(axis="x", rotation=20)
    for bar, val in zip(axes[0].patches, all_k_vals):
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(all_k_vals)*0.01,
                     f"{val/1e3:.0f}k", ha="center", va="bottom", fontsize=8)
    # Pie
    axes[1].pie(all_k_vals, labels=all_k_label, autopct="%1.1f%%",
                colors=colors, startangle=140, pctdistance=0.8)
    axes[1].set_title("Protocol Share", fontweight="bold")
    fig.suptitle("Network Protocol Distribution", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save(fig, "1_2_protocols", cfg)
    return {"top_protocols": top_k.to_dict()}


# task 1.3 - top-10 source / destination ips

def task3(df: pd.DataFrame, cfg: dict) -> dict:
    n = cfg["section1"]["top_n_ips"]
    _section_header(f"Top-{n} Most Active Source & Destination IPs  (metric: bytes)", "Task 1.3")

    top_src = (df.groupby("source")["totalSourceBytes"].sum().nlargest(n)
                 .reset_index(name="bytes_sent"))
    top_dst = (df.groupby("destination")["totalDestinationBytes"].sum().nlargest(n)
                 .reset_index(name="bytes_received"))

    # Also compute flow count for context
    src_flows = df["source"].value_counts().rename("flows")
    dst_flows = df["destination"].value_counts().rename("flows")
    top_src = top_src.merge(src_flows.reset_index().rename(columns={"index":"source","source":"source","count":"flows"}),
                            left_on="source", right_on="source", how="left")
    top_dst = top_dst.merge(dst_flows.reset_index().rename(columns={"index":"destination","destination":"destination","count":"flows"}),
                            left_on="destination", right_on="destination", how="left")

    console.print("\n  [bold]Top Source IPs (by bytes sent)[/bold]")
    ts = Table(box=box.SIMPLE_HEAD, padding=(0, 1))
    ts.add_column("Rank", justify="right", style="dim", width=5)
    ts.add_column("Source IP",   style="cyan")
    ts.add_column("Bytes Sent",  justify="right", style="green")
    ts.add_column("Flows",       justify="right", style="magenta")
    for i, row in top_src.iterrows():
        ts.add_row(str(i+1), row["source"],
                   f"{row['bytes_sent']/1e6:.1f} MB", f"{int(row.get('flows',0)):,}")
    console.print(ts)

    console.print("\n  [bold]Top Destination IPs (by bytes received)[/bold]")
    td = Table(box=box.SIMPLE_HEAD, padding=(0, 1))
    td.add_column("Rank", justify="right", style="dim", width=5)
    td.add_column("Destination IP",     style="cyan")
    td.add_column("Bytes Received",     justify="right", style="green")
    td.add_column("Flows",              justify="right", style="magenta")
    for i, row in top_dst.iterrows():
        td.add_row(str(i+1), row["destination"],
                   f"{row['bytes_received']/1e6:.1f} MB", f"{int(row.get('flows',0)):,}")
    console.print(td)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, data, xcol, title, color in [
        (axes[0], top_src,  "bytes_sent",     f"Top-{n} Source IPs (MB Sent)",     "steelblue"),
        (axes[1], top_dst, "bytes_received", f"Top-{n} Destination IPs (MB Recv)", "coral"),
    ]:
        vals = data[xcol] / 1e6
        ax.barh(data.iloc[:, 0], vals, color=color, edgecolor="white")
        ax.invert_yaxis()
        ax.set_xlabel("MB")
        ax.set_title(title, fontweight="bold")
        for bar, v in zip(ax.patches, vals):
            ax.text(v + max(vals)*0.01, bar.get_y() + bar.get_height()/2,
                    f"{v:.0f}", va="center", fontsize=8)
    fig.suptitle("Traffic Volume by IP Address", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save(fig, "1_3_top_ips", cfg)
    return {"top_src": top_src.head(3).to_dict("records"),
            "top_dst": top_dst.head(3).to_dict("records")}


# task 1.4 - average packet size

def task4(df: pd.DataFrame, cfg: dict) -> dict:
    _section_header("Average Packet Size & Representativeness", "Task 1.4")
    avg = df["avg_pkt_bytes"].dropna()

    mean_v   = avg.mean()
    median_v = avg.median()
    std_v    = avg.std()
    skew_v   = avg.skew()
    kurt_v   = avg.kurt()
    q1, q3   = avg.quantile(0.25), avg.quantile(0.75)

    t = Table(box=box.ROUNDED, padding=(0, 2))
    t.add_column("Statistic",  style="bold")
    t.add_column("Value",      style="cyan", justify="right")
    t.add_row("Mean",          f"{mean_v:.2f} bytes")
    t.add_row("Median",        f"{median_v:.2f} bytes")
    t.add_row("Std deviation", f"{std_v:.2f} bytes")
    t.add_row("Skewness",      f"{skew_v:.3f}")
    t.add_row("Kurtosis",      f"{kurt_v:.3f}")
    t.add_row("Q1 / Q3",       f"{q1:.1f} / {q3:.1f} bytes")
    t.add_row("IQR",           f"{q3-q1:.2f} bytes")
    console.print(t)

    representative = abs(skew_v) <= 1 and std_v <= mean_v
    if representative:
        console.print("  [green]The mean IS representative -- low skewness, std < mean.[/green]")
    else:
        console.print("  [yellow]The mean is NOT representative.[/yellow] Distribution is "
                      f"[bold]{'right' if skew_v > 0 else 'left'}-skewed[/bold] "
                      f"(skew={skew_v:.2f}), std ({std_v:.0f}) "
                      f"{'>' if std_v > mean_v else '<'} mean ({mean_v:.0f}). "
                      "Use [bold]median[/bold] as a better measure of central tendency.\n"
                      "  Reason: mixed-protocol traffic -- small DNS/ICMP (64-128 B) "
                      "coexist with large HTTP/FTP transfers (1 KB-60 KB).")

    cap = avg.quantile(0.99)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    # Histogram
    axes[0].hist(avg.clip(upper=cap), bins=80, color="steelblue", alpha=0.85, edgecolor="none")
    axes[0].axvline(mean_v,   color="red",    lw=1.5, linestyle="--", label=f"Mean {mean_v:.0f} B")
    axes[0].axvline(median_v, color="orange", lw=1.5, linestyle="--", label=f"Median {median_v:.0f} B")
    axes[0].set_title("Packet Size Distribution (capped 99th pct)", fontweight="bold")
    axes[0].set_xlabel("Avg bytes/packet"); axes[0].set_ylabel("Flow count")
    axes[0].legend(fontsize=8)
    # Box plot per protocol
    top5p = df["protocolName"].value_counts().head(5).index
    data_bp = [df.loc[df["protocolName"]==p, "avg_pkt_bytes"].dropna().clip(upper=cap).values
               for p in top5p]
    axes[1].boxplot(data_bp, labels=top5p, patch_artist=True,
                    boxprops=dict(facecolor="steelblue", alpha=0.6))
    axes[1].set_title("Packet Size by Protocol", fontweight="bold")
    axes[1].set_xlabel("Protocol"); axes[1].set_ylabel("Bytes/packet")
    axes[1].tick_params(axis="x", rotation=20)
    # CDF
    sorted_v = np.sort(avg.values)
    axes[2].plot(sorted_v, np.linspace(0, 1, len(sorted_v)), color="steelblue", lw=1.5)
    axes[2].axvline(mean_v,   color="red",    lw=1, linestyle="--", label="Mean")
    axes[2].axvline(median_v, color="orange", lw=1, linestyle="--", label="Median")
    axes[2].set_xlim(0, cap); axes[2].set_ylim(0, 1)
    axes[2].set_title("CDF of Packet Size", fontweight="bold")
    axes[2].set_xlabel("Bytes/packet"); axes[2].set_ylabel("Cumulative fraction")
    axes[2].legend(fontsize=8)
    fig.suptitle("Task 1.4 - Packet Size Analysis", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save(fig, "1_4_packet_size", cfg)
    return {"mean_pkt": mean_v, "median_pkt": median_v, "std_pkt": std_v, "skew_pkt": skew_v}


# task 1.5 - top-3 src-dst pairs

def task5(df: pd.DataFrame, cfg: dict) -> dict:
    n = cfg["section1"]["top_n_pairs"]
    _section_header(f"Top-{n} Most Frequent Source-Destination Pairs", "Task 1.5")

    pairs = (df.groupby(["source", "destination"])
               .agg(flows=("totalBytes","count"),
                    total_bytes=("totalBytes","sum"),
                    protocols=("protocolName","nunique"))
               .nlargest(n, "flows").reset_index())

    t = Table(box=box.ROUNDED, padding=(0, 2))
    t.add_column("Rank",          justify="right", style="dim", width=5)
    t.add_column("Source IP",     style="cyan")
    t.add_column("Destination IP",style="cyan")
    t.add_column("Flows",         justify="right", style="green")
    t.add_column("% of Total",    justify="right", style="yellow")
    t.add_column("Total Bytes",   justify="right", style="magenta")
    t.add_column("Protocols",     justify="right", style="white")
    total = len(df)
    for i, row in pairs.iterrows():
        t.add_row(str(i+1), row["source"], row["destination"],
                  f"{row['flows']:,}", f"{row['flows']/total*100:.3f}%",
                  f"{row['total_bytes']/1e6:.1f} MB", str(row["protocols"]))
    console.print(t)

    fig, ax = plt.subplots(figsize=(9, 4))
    labels = [f"{r['source']}\n-> {r['destination']}" for _, r in pairs.iterrows()]
    bars = ax.bar(labels, pairs["flows"], color=sns.color_palette("muted", n))
    for bar, val in zip(bars, pairs["flows"]):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+max(pairs["flows"])*0.01,
                f"{val:,}", ha="center", va="bottom", fontsize=9)
    ax.set_title(f"Top-{n} Source-Destination Pairs by Flow Count", fontweight="bold")
    ax.set_ylabel("Number of Flows")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    plt.tight_layout()
    _save(fig, "1_5_top_pairs", cfg)
    return {"top_pairs": pairs.to_dict("records")}


# task 1.6 - consistent communication patterns

def task6(df: pd.DataFrame, cfg: dict) -> dict:
    win  = cfg["section1"]["time_window"]
    thr  = cfg["section1"]["consistent_ip_min_pct"]
    _section_header(f"Consistent Communication Patterns  (window={win}, threshold={thr*100:.0f}%)", "Task 1.6")

    console.print(f"  [bold]Time window definition:[/bold] [cyan]{win}[/cyan] tumbling window on startDateTime.\n"
                  "  [bold]Rationale:[/bold] 1-hour windows match standard SIEM practice; they capture\n"
                  "  intra-day rhythms (business hours, backup jobs) without excessive noise.")

    dft = df.dropna(subset=["startDateTime"]).copy()
    dft["window"] = dft["startDateTime"].dt.floor(win)
    total_win = dft["window"].nunique()
    threshold_wins = thr * total_win

    src_wins = (dft.groupby("source")["window"].nunique()
                   .reset_index(name="windows_active")
                   .sort_values("windows_active", ascending=False))
    src_wins["pct_active"] = src_wins["windows_active"] / total_win * 100
    consistent = src_wins[src_wins["windows_active"] >= threshold_wins]

    console.print(f"\n  Total {win} windows in dataset : [cyan]{total_win}[/cyan]")
    console.print(f"  Threshold (>={thr*100:.0f}%)          : [cyan]{threshold_wins:.0f} windows[/cyan]")
    console.print(f"  Consistently active IPs       : [bold green]{len(consistent)}[/bold green]\n")

    t = Table(box=box.ROUNDED, padding=(0, 2))
    t.add_column("IP Address",     style="cyan")
    t.add_column("Windows Active", justify="right", style="green")
    t.add_column("% Active",       justify="right", style="yellow")
    for _, row in consistent.head(20).iterrows():
        t.add_row(row["source"], str(int(row["windows_active"])),
                  f"{row['pct_active']:.1f}%")
    console.print(t)

    # Activity heatmap
    dft["hour_of_day"] = dft["startDateTime"].dt.hour
    dft["day"]         = dft["startDateTime"].dt.date
    top_ip_list = consistent["source"].head(10).tolist()
    if top_ip_list:
        hm_data = (dft[dft["source"].isin(top_ip_list)]
                   .groupby(["source", "hour_of_day"]).size().unstack(fill_value=0))
        fig, ax = plt.subplots(figsize=(14, max(4, len(hm_data)*0.5+2)))
        sns.heatmap(hm_data, ax=ax, cmap="YlOrRd", linewidths=0.3,
                    cbar_kws={"label": "Flows"})
        ax.set_title("Activity Heatmap: Top-10 Consistent IPs x Hour of Day", fontweight="bold")
        ax.set_xlabel("Hour of Day"); ax.set_ylabel("Source IP")
        plt.tight_layout()
        _save(fig, "1_6_consistent_ips", cfg)

    return {"consistent_ips": consistent["source"].tolist(), "total_windows": total_win}


# task 1.7 - traffic spikes

def task7(df: pd.DataFrame, cfg: dict) -> dict:
    bin_w = cfg["section1"]["spike_bin"]
    z_thr = cfg["section1"]["spike_z_threshold"]
    _section_header(f"Irregular Traffic Spike Detection  (bin={bin_w}, Z-threshold={z_thr}sigma)", "Task 1.7")

    console.print(f"  [bold]Method:[/bold] Z-score on {bin_w} flow-count bins.\n"
                  f"  A bin is a spike when its count > mu + {z_thr}sigma "
                  f"(upper {(1 - 0.9772 if z_thr==2 else 0.0013)*100:.2f}% tail under normality).")

    dft = df.dropna(subset=["startDateTime"]).copy()
    dft["bin"] = dft["startDateTime"].dt.floor(bin_w)
    bins = dft.groupby("bin").size().reset_index(name="flow_count")
    mu, sigma = bins["flow_count"].mean(), bins["flow_count"].std()
    thresh = mu + z_thr * sigma
    bins["z_score"] = (bins["flow_count"] - mu) / sigma
    bins["is_spike"] = bins["flow_count"] > thresh
    spikes = bins[bins["is_spike"]].sort_values("flow_count", ascending=False)

    console.print(f"\n  mu = {mu:.1f} flows/bin,  sigma = {sigma:.1f},  "
                  f"threshold = [bold red]{thresh:.1f}[/bold red] flows/bin")
    console.print(f"  Spike bins detected: [bold red]{len(spikes)}[/bold red] "
                  f"/ {len(bins)} total bins\n")

    t = Table(box=box.SIMPLE_HEAD, padding=(0, 1))
    t.add_column("Rank", justify="right", style="dim", width=5)
    t.add_column("Bin (start)",         style="cyan")
    t.add_column("Flow Count",          justify="right", style="red")
    t.add_column("Z-Score",             justify="right", style="yellow")
    for i, (_, row) in enumerate(spikes.head(10).iterrows(), 1):
        t.add_row(str(i), str(row["bin"])[:19],
                  f"{row['flow_count']:,}", f"{row['z_score']:.2f}sigma")
    console.print(t)
    console.print("\n  [bold]Possible causes:[/bold] DDoS/flood attack, scheduled backup, "
                  "software-update push,\n  ARP broadcast storm, or port scanning burst.")

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=False)
    # Timeline
    axes[0].plot(bins["bin"], bins["flow_count"],
                 color="steelblue", lw=0.9, label="Flows per bin")
    axes[0].fill_between(bins["bin"], bins["flow_count"], alpha=0.2, color="steelblue")
    if not spikes.empty:
        axes[0].scatter(spikes["bin"], spikes["flow_count"],
                        color="red", zorder=5, s=25, label=f"Spike (>{thresh:.0f})")
    axes[0].axhline(thresh, color="orange", lw=1.2, linestyle="--",
                    label=f"Threshold mu+{z_thr}sigma = {thresh:.0f}")
    axes[0].set_title(f"Traffic Timeline with Spike Detection ({bin_w} bins)", fontweight="bold")
    axes[0].set_ylabel("Flows per bin"); axes[0].legend(fontsize=8)
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:,.0f}"))
    # Z-score distribution
    axes[1].hist(bins["z_score"], bins=60, color="steelblue", alpha=0.8, edgecolor="none")
    axes[1].axvline(z_thr, color="red", lw=1.5, linestyle="--", label=f"Z={z_thr}")
    axes[1].set_title("Z-Score Distribution of Bin Flow Counts", fontweight="bold")
    axes[1].set_xlabel("Z-Score"); axes[1].set_ylabel("Number of bins")
    axes[1].legend()
    plt.tight_layout()
    _save(fig, "1_7_spikes", cfg)
    return {"spike_threshold": thresh, "n_spikes": len(spikes),
            "spikes": spikes.head(10).to_dict("records")}


# task 1.8 - packet size variance

def task8(df: pd.DataFrame, cfg: dict) -> dict:
    _section_header("Packet Size Variance Analysis", "Task 1.8")
    avg = df["avg_pkt_bytes"].dropna()

    var_v  = avg.var()
    std_v  = math.sqrt(var_v)
    cv     = std_v / avg.mean() * 100   # coefficient of variation

    t = Table(box=box.ROUNDED, padding=(0, 2))
    t.add_column("Statistic",             style="bold")
    t.add_column("Value",                 style="cyan", justify="right")
    t.add_row("Variance",                 f"{var_v:,.2f} bytes²")
    t.add_row("Standard deviation",       f"{std_v:.2f} bytes")
    t.add_row("Coefficient of variation", f"{cv:.1f}%")
    t.add_row("Min / Max",                f"{avg.min():.1f} / {avg.max():.1f} bytes")
    console.print(t)

    console.print(
        f"\n  [bold]Interpretation (CV = {cv:.0f}%):[/bold]\n"
        "  [bold yellow]HIGH variance[/bold yellow] -- the dataset mixes:\n"
        "    * Tiny control packets: DNS (64-80 B), ICMP echo (84 B), TCP SYN (60-80 B)\n"
        "    * Medium sessions: HTTP, SMTP, POP3 (200-600 B avg)\n"
        "    * Large transfers: FTP, BitTorrent, video streaming (900-2000 B avg)\n"
        "  A single mean cannot represent all of these; [bold]protocol-stratified[/bold] statistics\n"
        "  or a [bold]log-scale[/bold] view are more informative."
    )

    # Variance contribution by protocol
    top5 = df["protocolName"].value_counts().head(5).index
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    colors = sns.color_palette("muted", len(top5))
    vars_  = [df.loc[df["protocolName"]==p, "avg_pkt_bytes"].dropna().var() for p in top5]
    axes[0].bar(top5, vars_, color=colors, edgecolor="white")
    axes[0].set_title("Packet-Size Variance by Protocol", fontweight="bold")
    axes[0].set_xlabel("Protocol"); axes[0].set_ylabel("Variance (bytes²)")
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:,.0f}"))
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].hist(np.log1p(avg), bins=80, color="steelblue", alpha=0.85, edgecolor="none")
    axes[1].set_title("Log-Scale Distribution of Packet Size", fontweight="bold")
    axes[1].set_xlabel("log(1 + bytes/packet)"); axes[1].set_ylabel("Flow count")
    fig.suptitle("Task 1.8 - Packet Size Variance", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save(fig, "1_8_variance", cfg)
    return {"variance": var_v, "std": std_v, "cv_pct": cv}
