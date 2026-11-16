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


def iqr_bounds(series, mult=1.5):
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    return q1 - mult*(q3-q1), q3 + mult*(q3-q1)


# task 12 - statistical traffic analysis

def task12(df: pd.DataFrame, cfg: dict) -> dict:
    iqr_m   = cfg["section3"]["statistical"]["iqr_multiplier"]
    out_z   = cfg["section3"]["statistical"]["outlier_z_sigma"]
    dev_z   = cfg["section3"]["statistical"]["protocol_dev_sigma"]
    _hdr(f"Statistical Traffic Analysis  (IQR mult={iqr_m}, outlier Z={out_z}sigma)", "Task 12")

    # -- (a) Packet-size anomalies ---------------------------------------------
    avg = df["avg_pkt_bytes"].dropna()
    plo, phi = iqr_bounds(avg, iqr_m)
    pkt_anom = df[df["avg_pkt_bytes"] > phi]
    console.print(f"\n  [bold](a) Packet-size IQR anomalies[/bold]  "
                  f"(mult={iqr_m})  ->  normal range: [{max(0,plo):.0f}, {phi:.0f}] bytes")
    console.print(f"  Flows with anomalously LARGE packets: [bold red]{len(pkt_anom):,}[/bold red]  "
                  f"({len(pkt_anom)/len(df)*100:.2f}% of total)")
    top_anom = (pkt_anom.groupby(["source","destination","protocolName"])
                         .agg(flows=("totalBytes","count"),
                              max_pkt=("avg_pkt_bytes","max"))
                         .nlargest(8,"max_pkt").reset_index())
    t = Table(box=box.SIMPLE_HEAD, padding=(0,1))
    t.add_column("Source",      style="cyan"); t.add_column("Destination", style="cyan")
    t.add_column("Protocol",    style="magenta"); t.add_column("Flows",     justify="right",style="green")
    t.add_column("Max pkt (B)", justify="right",style="red")
    for _, r in top_anom.iterrows():
        t.add_row(r["source"], r["destination"], r["protocolName"],
                  f"{r['flows']:,}", f"{r['max_pkt']:.0f}")
    console.print(t)

    # -- (b) Per-IP flow count anomalies --------------------------------------
    ip_flows = df["source"].value_counts()
    flo, fhi = iqr_bounds(ip_flows, iqr_m)
    high_ips = ip_flows[ip_flows > fhi]
    console.print(f"\n  [bold](b) Per-IP flow count outliers[/bold]  "
                  f"normal range: [{max(0,flo):.0f}, {fhi:.0f}]")
    console.print(f"  Source IPs with abnormally HIGH flow count: [bold red]{len(high_ips)}[/bold red]\n")
    th = Table(box=box.SIMPLE_HEAD, padding=(0,1))
    th.add_column("Source IP", style="cyan"); th.add_column("Flow Count", justify="right", style="red")
    th.add_column("vs IQR Upper", justify="right", style="yellow")
    for ip, cnt in high_ips.head(10).items():
        th.add_row(ip, f"{cnt:,}", f"{cnt/fhi:.1f}x")
    console.print(th)

    # -- (c) Hourly protocol distribution anomalies ----------------------------
    dft = df.dropna(subset=["startDateTime"]).copy()
    dft["hour"] = dft["startDateTime"].dt.floor("1h")
    h_proto = dft.groupby(["hour","protocolName"]).size().unstack(fill_value=0)
    h_share = h_proto.div(h_proto.sum(axis=1), axis=0)
    pm, ps  = h_share.mean(), h_share.std()
    anom_h  = ((h_share - pm).abs() > dev_z * ps).any(axis=1)
    console.print(f"\n  [bold](c) Hourly protocol-distribution anomalies[/bold]  "
                  f"(>{dev_z}sigma deviation): [bold red]{anom_h.sum()}[/bold red] hours")

    # -- (d) IP bytes outliers (mean + z*std) ----------------------------------
    ip_bytes = df.groupby("source")["totalBytes"].sum()
    b_mean, b_std = ip_bytes.mean(), ip_bytes.std()
    b_thr = b_mean + out_z * b_std
    outlier_ips = ip_bytes[ip_bytes > b_thr].sort_values(ascending=False)
    console.print(f"\n  [bold](d) High-volume source IPs[/bold]  "
                  f"threshold = mean + {out_z}sigma = {b_thr/1e9:.2f} GB")
    tb = Table(box=box.SIMPLE_HEAD, padding=(0,1))
    tb.add_column("Source IP", style="cyan"); tb.add_column("Total Bytes", justify="right", style="red")
    tb.add_column("sigma above mean", justify="right", style="yellow")
    for ip, val in outlier_ips.head(10).items():
        tb.add_row(ip, f"{val/1e9:.2f} GB", f"{(val-b_mean)/b_std:.1f}sigma")
    console.print(tb)

    # -- Plots -----------------------------------------------------------------
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    # Box plots per protocol
    top5p = df["protocolName"].value_counts().head(5).index
    cap   = avg.quantile(0.99)
    data_bp = [df.loc[df["protocolName"]==p, "avg_pkt_bytes"].dropna().clip(upper=cap).values for p in top5p]
    bp = axes[0,0].boxplot(data_bp, labels=top5p, patch_artist=True, notch=True,
                            boxprops=dict(facecolor="steelblue", alpha=0.6),
                            medianprops=dict(color="red", lw=2))
    axes[0,0].set_title("Packet Size Box Plot by Protocol", fontweight="bold")
    axes[0,0].set_ylabel("Bytes/packet"); axes[0,0].tick_params(axis="x", rotation=20)

    # Hourly flow count
    hourly = dft.groupby("hour").size()
    axes[0,1].plot(hourly.index, hourly.values, color="steelblue", lw=0.9)
    axes[0,1].set_title("Hourly Flow Count", fontweight="bold")
    axes[0,1].set_ylabel("Flows/hour"); axes[0,1].set_xlabel("Time")
    axes[0,1].tick_params(axis="x", rotation=30)

    # Protocol share heatmap (hour vs protocol, top-5)
    top5_p = df["protocolName"].value_counts().head(5).index.tolist()
    hmap = h_share[top5_p].head(48)   # last 48 hours for readability
    if not hmap.empty:
        sns.heatmap(hmap.T, ax=axes[1,0], cmap="YlOrRd",
                    xticklabels=max(1, len(hmap)//8), cbar_kws={"label":"Share"})
        axes[1,0].set_title("Hourly Protocol Share (48h window)", fontweight="bold")
        axes[1,0].set_xlabel("Hour"); axes[1,0].set_ylabel("Protocol")

    # Top outlier IPs bar chart
    axes[1,1].barh(outlier_ips.head(10).index[::-1],
                   outlier_ips.head(10).values[::-1] / 1e9,
                   color="coral")
    axes[1,1].set_title(f"High-Volume IPs (> mean+{out_z}sigma)", fontweight="bold")
    axes[1,1].set_xlabel("Total GB"); axes[1,1].axvline(b_thr/1e9, color="red", lw=1.2,
                                                         linestyle="--", label="Threshold")
    axes[1,1].legend()
    fig.suptitle("Task 12 - Statistical Traffic Analysis", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save(fig, "3_12_statistical", cfg)
    return {"pkt_anomalies": len(pkt_anom), "outlier_ips": outlier_ips.head(10).to_dict(),
            "high_flow_ips": len(high_ips), "outlier_ips_series": outlier_ips,
            "anom_hours": int(anom_h.sum())}


# task 13 - behavioural analysis

def task13(df: pd.DataFrame, cfg: dict) -> dict:
    spike_ratio = cfg["section3"]["behavioural"]["spike_ratio"]
    roll_h      = cfg["section3"]["behavioural"]["rolling_hours"]
    fan_min     = cfg["section3"]["behavioural"]["fan_in_min_src"]
    fan_win     = cfg["section3"]["behavioural"]["fan_in_window"]
    _hdr(f"Behavioural Analysis  (spike ratio={spike_ratio}x, fan-in>={fan_min} src)", "Task 13")

    dft = df.dropna(subset=["startDateTime"]).copy()
    dft["hour"] = dft["startDateTime"].dt.floor("1h")

    # -- (a) Behavioural spike detection --------------------------------------
    console.print(f"\n  [bold](a) Behavioural spikes[/bold]  "
                  f"flag: hourly flows > {spike_ratio}x rolling {roll_h}-hour mean")
    hsf = (dft.groupby(["source","hour"]).size()
               .reset_index(name="flow_count")
               .sort_values(["source","hour"]))
    hsf["rolling_mean"] = (hsf.groupby("source")["flow_count"]
                              .transform(lambda x: x.shift(1).rolling(roll_h, min_periods=1).mean()))
    hsf["spike_ratio_actual"] = hsf["flow_count"] / hsf["rolling_mean"].replace(0, np.nan)
    beh_anom = hsf[hsf["spike_ratio_actual"] > spike_ratio].sort_values("spike_ratio_actual", ascending=False)

    console.print(f"  IP-hour pairs with sudden activity spike: [bold red]{len(beh_anom)}[/bold red]\n")
    t = Table(box=box.SIMPLE_HEAD, padding=(0,1))
    t.add_column("Source IP", style="cyan"); t.add_column("Hour", style="yellow")
    t.add_column("Flows",     justify="right", style="green")
    t.add_column("Rolling Mean", justify="right", style="dim")
    t.add_column("Spike Ratio", justify="right", style="red")
    for _, r in beh_anom.head(10).iterrows():
        t.add_row(r["source"], str(r["hour"])[:16],
                  f"{r['flow_count']:,}", f"{r['rolling_mean']:.1f}",
                  f"{r['spike_ratio_actual']:.1f}x")
    console.print(t)

    # -- (b) Fan-in / DDoS correlation -----------------------------------------
    console.print(f"\n  [bold](b) Fan-in / DDoS correlation[/bold]  "
                  f">={fan_min} distinct sources -> same destination in {fan_win}")
    dft["fan_bin"] = dft["startDateTime"].dt.floor(fan_win)
    fan = (dft.groupby(["destination","fan_bin"])["source"]
               .nunique().reset_index(name="distinct_srcs"))
    fan_anom = fan[fan["distinct_srcs"] >= fan_min].sort_values("distinct_srcs", ascending=False)

    console.print(f"  Events flagged: [bold red]{len(fan_anom)}[/bold red]  |  "
                  f"Unique destinations: [bold red]{fan_anom['destination'].nunique()}[/bold red]\n")
    tf = Table(box=box.SIMPLE_HEAD, padding=(0,1))
    tf.add_column("Destination",    style="cyan"); tf.add_column("Window Start", style="yellow")
    tf.add_column("Distinct Sources", justify="right", style="red")
    for _, r in fan_anom.head(10).iterrows():
        tf.add_row(r["destination"], str(r["fan_bin"])[:16], f"{r['distinct_srcs']:,}")
    console.print(tf)

    # -- Plots -----------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    top_beh = beh_anom["source"].value_counts().head(8).index
    if len(top_beh):
        bd = (hsf[hsf["source"].isin(top_beh)]
              .pivot_table(index="hour", columns="source", values="flow_count", aggfunc="sum").fillna(0))
        bd.plot(ax=axes[0], lw=0.9, alpha=0.85)
        axes[0].set_title(f"Hourly Flows - Top Behavioural Anomaly IPs", fontweight="bold")
        axes[0].set_ylabel("Flows/hour"); axes[0].tick_params(axis="x", rotation=30)
        axes[0].legend(fontsize=7, ncol=2)

    if not fan_anom.empty:
        top_dst = fan_anom.groupby("destination")["distinct_srcs"].max().nlargest(10)
        axes[1].barh(top_dst.index[::-1], top_dst.values[::-1], color="coral")
        axes[1].axvline(fan_min, color="red", lw=1.2, linestyle="--",
                        label=f"Threshold={fan_min}")
        axes[1].set_title(f"Fan-in: Max Distinct Sources in {fan_win}", fontweight="bold")
        axes[1].set_xlabel("Distinct Sources"); axes[1].legend()

    fig.suptitle("Task 13 - Behavioural Analysis", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save(fig, "3_13_behavioural", cfg)
    return {"behavioural_spikes": len(beh_anom), "fan_in_events": len(fan_anom),
            "ddos_targets": fan_anom["destination"].nunique(),
            "fan_anom": fan_anom, "beh_anom": beh_anom}


# task 14 - suspicious communication patterns

def task14(df: pd.DataFrame, cfg: dict) -> dict:
    dur_z   = cfg["section3"]["suspicious"]["long_dur_z_sigma"]
    mp_win  = cfg["section3"]["suspicious"]["multi_proto_window"]
    mp_min  = cfg["section3"]["suspicious"]["multi_proto_min"]
    _hdr(f"Suspicious Communication Patterns  (long-dur Z={dur_z}sigma, multi-proto >{mp_min} in {mp_win})", "Task 14")

    # -- (a) Long-duration connections -----------------------------------------
    d_mean, d_std = df["duration_s"].mean(), df["duration_s"].std()
    d_thr = d_mean + dur_z * d_std
    long  = df[df["duration_s"] > d_thr].sort_values("duration_s", ascending=False)

    console.print(f"\n  [bold](a) Long-duration connections[/bold]\n"
                  f"  Duration stats: mean={d_mean:.1f}s, std={d_std:.1f}s\n"
                  f"  Threshold (mean+{dur_z}sigma): [bold yellow]{d_thr:.0f}s "
                  f"({d_thr/3600:.1f} h)[/bold yellow]\n"
                  f"  Flagged flows: [bold red]{len(long):,}[/bold red]\n"
                  "  Interpretation: may indicate persistent backdoors, data-staging tunnels,\n"
                  "  covert C2 keep-alive sessions, or long-running legitimate backups.")
    tl = Table(box=box.SIMPLE_HEAD, padding=(0,1))
    tl.add_column("Source",     style="cyan"); tl.add_column("Destination", style="cyan")
    tl.add_column("Protocol",   style="magenta"); tl.add_column("Duration", justify="right", style="red")
    tl.add_column("Bytes",      justify="right", style="green"); tl.add_column("Label", style="yellow")
    for _, r in long.head(12).iterrows():
        tl.add_row(str(r["source"]), str(r["destination"]), str(r["protocolName"]),
                   f"{r['duration_s']:.0f}s", f"{r['totalBytes']:,}", str(r.get("Label","")))
    console.print(tl)

    # -- (b) Multi-protocol bursts ---------------------------------------------
    dft = df.dropna(subset=["startDateTime"]).copy()
    dft["mp_bin"] = dft["startDateTime"].dt.floor(mp_win)
    mp = (dft.groupby(["source","mp_bin"])["protocolName"]
              .nunique().reset_index(name="distinct_protocols"))
    mp_sus = mp[mp["distinct_protocols"] >= mp_min].sort_values("distinct_protocols", ascending=False)

    console.print(f"\n  [bold](b) Multi-protocol bursts[/bold]  "
                  f"(>={mp_min} distinct protocols in {mp_win})\n"
                  f"  Flagged events: [bold red]{len(mp_sus)}[/bold red]  |  "
                  f"Unique source IPs: [bold red]{mp_sus['source'].nunique()}[/bold red]\n"
                  "  Interpretation: legitimate hosts rarely switch protocols rapidly;\n"
                  "  this suggests automated scanning, malware pivoting, or probing.")
    tm = Table(box=box.SIMPLE_HEAD, padding=(0,1))
    tm.add_column("Source IP",  style="cyan"); tm.add_column("Window",  style="yellow")
    tm.add_column("Protocols",  justify="right", style="red")
    for _, r in mp_sus.head(12).iterrows():
        tm.add_row(r["source"], str(r["mp_bin"])[:16], str(r["distinct_protocols"]))
    console.print(tm)

    # -- Plots -----------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    # Duration scatter
    sample = df.dropna(subset=["duration_s","totalBytes"]).sample(min(20000,len(df)), random_state=42)
    colors = np.where(sample["duration_s"] > d_thr, "red", "steelblue")
    axes[0].scatter(sample["duration_s"]/3600, sample["totalBytes"]/1e6,
                    c=colors, alpha=0.3, s=5)
    axes[0].axvline(d_thr/3600, color="orange", lw=1.2, linestyle="--",
                    label=f"Threshold {d_thr/3600:.1f}h")
    axes[0].set_title("Flow Duration vs Total Bytes (red=flagged)", fontweight="bold")
    axes[0].set_xlabel("Duration (hours)"); axes[0].set_ylabel("Total Bytes (MB)")
    axes[0].legend(fontsize=8)
    # Multi-protocol bar chart
    mp_ip_cnt = mp_sus.groupby("source").size().nlargest(10)
    if not mp_ip_cnt.empty:
        axes[1].barh(mp_ip_cnt.index[::-1], mp_ip_cnt.values[::-1], color="coral")
        axes[1].set_title(f"Multi-Protocol Burst Events per IP", fontweight="bold")
        axes[1].set_xlabel("Number of burst windows")
    fig.suptitle("Task 14 - Suspicious Communication Patterns", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save(fig, "3_14_suspicious", cfg)
    return {"long_flows": len(long), "dur_threshold": d_thr,
            "multi_proto_events": len(mp_sus),
            "long_flows_df": long, "mp_sus": mp_sus}
