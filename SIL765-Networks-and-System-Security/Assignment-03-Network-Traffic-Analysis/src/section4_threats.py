import re
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
from rich.text import Text

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


# task 15 - complex attack patterns

def task15(df: pd.DataFrame, cfg: dict) -> dict:
    ps  = cfg["section4"]["port_scan"]
    sd  = cfg["section4"]["slow_ddos"]
    ih  = cfg["section4"]["ip_hopping"]
    _hdr("Complex Attack Pattern Detection", "Task 15")

    dft = df.dropna(subset=["startDateTime"]).copy()
    dft["hour"] = dft["startDateTime"].dt.floor("1h")

    # -- (a) Stealthy port scan ------------------------------------------------
    console.print(
        f"\n  [bold](a) Stealthy Port Scan[/bold]\n"
        f"  Signature: >={ps['min_distinct_ports']} distinct dst ports on same target,\n"
        f"  spread over >={ps['min_span_minutes']} min, rate < {ps['max_rate_per_min']} flows/min.\n"
        "  Rationale: low-rate scanning evades threshold-based IDS rules."
    )
    scan_agg = (dft.groupby(["source","destination"])
                    .agg(distinct_ports=("destinationPort","nunique"),
                         flow_count=("destinationPort","count"),
                         t_start=("startDateTime","min"),
                         t_end=("startDateTime","max"))
                    .reset_index())
    scan_agg["span_min"]     = (scan_agg["t_end"]-scan_agg["t_start"]).dt.total_seconds()/60
    scan_agg["rate_per_min"] = scan_agg["flow_count"] / scan_agg["span_min"].replace(0,np.nan)
    scans = scan_agg[(scan_agg["distinct_ports"]  >= ps["min_distinct_ports"])  &
                     (scan_agg["span_min"]         >= ps["min_span_minutes"])    &
                     (scan_agg["rate_per_min"]      < ps["max_rate_per_min"])
                     ].sort_values("distinct_ports", ascending=False)

    console.print(f"  Stealthy scan pairs found: [bold red]{len(scans)}[/bold red]\n")
    ts = Table(box=box.SIMPLE_HEAD, padding=(0,1))
    ts.add_column("Source",    style="cyan");  ts.add_column("Destination", style="cyan")
    ts.add_column("Ports",     justify="right", style="red")
    ts.add_column("Span (min)",justify="right", style="yellow")
    ts.add_column("Rate/min",  justify="right", style="magenta")
    for _, r in scans.head(12).iterrows():
        ts.add_row(r["source"], r["destination"],
                   f"{r['distinct_ports']:,}", f"{r['span_min']:.0f}",
                   f"{r['rate_per_min']:.2f}")
    console.print(ts)

    # -- (b) Slow DDoS ---------------------------------------------------------
    console.print(
        f"\n  [bold](b) Slow DDoS Detection[/bold]\n"
        f"  Signature: distinct source count grows monotonically over >={sd['min_run_hours']} hours,\n"
        f"  peak >={sd['min_peak_sources']} sources, growth ratio >={sd['min_growth_ratio']}x."
    )
    hdst = (dft.groupby(["destination","hour"])["source"]
                .nunique().reset_index(name="distinct_srcs")
                .sort_values(["destination","hour"]))

    def mono_run(series):
        arr, best, rlen, rsi = series.values, None, 1, 0
        for i in range(1, len(arr)):
            if arr[i] > arr[i-1]:
                rlen += 1
            else:
                if rlen >= sd["min_run_hours"]:
                    sv, ev = arr[rsi], arr[i-1]
                    if ev >= sd["min_peak_sources"] and sv > 0 and ev/sv >= sd["min_growth_ratio"]:
                        if best is None or rlen > best[2]: best = (sv, ev, rlen)
                rsi, rlen = i, 1
        if rlen >= sd["min_run_hours"]:
            sv, ev = arr[rsi], arr[-1]
            if ev >= sd["min_peak_sources"] and sv > 0 and ev/sv >= sd["min_growth_ratio"]:
                if best is None or rlen > best[2]: best = (sv, ev, rlen)
        return best

    ddos_rows = []
    for dst, grp in hdst.groupby("destination"):
        r = mono_run(grp["distinct_srcs"].reset_index(drop=True))
        if r:
            ddos_rows.append({"destination": dst, "start_srcs": r[0],
                               "peak_srcs": r[1], "run_hours": r[2],
                               "growth_ratio": round(r[1]/r[0], 2)})
    slow_ddos = pd.DataFrame(ddos_rows).sort_values("peak_srcs", ascending=False) if ddos_rows else pd.DataFrame()

    console.print(f"  Slow DDoS candidates: [bold red]{len(slow_ddos)}[/bold red]\n")
    if not slow_ddos.empty:
        td = Table(box=box.SIMPLE_HEAD, padding=(0,1))
        td.add_column("Destination",  style="cyan"); td.add_column("Start Srcs", justify="right", style="green")
        td.add_column("Peak Srcs",    justify="right", style="red");  td.add_column("Hours", justify="right", style="yellow")
        td.add_column("Growth",       justify="right", style="magenta")
        for _, r in slow_ddos.head(12).iterrows():
            td.add_row(r["destination"],f"{r['start_srcs']}", f"{r['peak_srcs']}",
                       f"{r['run_hours']}", f"{r['growth_ratio']}x")
        console.print(td)

    # -- (c) IP hopping --------------------------------------------------------
    console.print(
        f"\n  [bold](c) IP Hopping Detection[/bold]\n"
        f"  Approach: fingerprint each source IP by its frozenset of contacted destination IPs.\n"
        f"  Cluster IPs with Jaccard similarity >= {ih['jaccard_threshold']}\n"
        f"  (>= {ih['jaccard_threshold']*100:.0f}% destination overlap -> likely same actor).\n"
        f"  Min destinations per fingerprint: {ih['min_destinations']},  min cluster size: {ih['min_cluster_size']}"
    )
    fp = {}
    for src, grp in df.groupby("source"):
        dsts = frozenset(grp["destination"].dropna().astype(str).unique())
        if len(dsts) >= ih["min_destinations"]:
            fp[str(src)] = dsts

    dst_to_srcs = defaultdict(list)
    for src, dsts in fp.items():
        for d in dsts: dst_to_srcs[d].append(src)

    cap = ih["candidate_cap"]
    cand = set()
    for srcs in dst_to_srcs.values():
        for i in range(min(len(srcs),cap)):
            for j in range(i+1, min(len(srcs),cap)):
                cand.add(tuple(sorted([srcs[i], srcs[j]])))

    def jacc(a, b):
        i = len(a & b); return i / len(a | b) if (a | b) else 0.0

    thr = ih["jaccard_threshold"]
    sim = [(a, b, jacc(fp[a], fp[b])) for a,b in cand if jacc(fp[a], fp[b]) >= thr]

    parent = {}
    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x: parent[x] = find(parent[x])
        return parent[x]
    def union(x, y): parent[find(x)] = find(y)
    for a,b,_ in sim: union(a,b)

    clusters = defaultdict(list)
    for src in fp: clusters[find(src)].append(src)
    hop_clusters = {k: sorted(v) for k,v in clusters.items() if len(v) >= ih["min_cluster_size"]}

    console.print(f"  Fingerprints built: [cyan]{len(fp):,}[/cyan]  |  "
                  f"Candidate pairs: [cyan]{len(cand):,}[/cyan]  |  "
                  f"Similar pairs (>={thr}): [cyan]{len(sim)}[/cyan]")
    console.print(f"  IP hopping clusters found: [bold red]{len(hop_clusters)}[/bold red]\n")
    for rep, members in list(hop_clusters.items())[:6]:
        common = fp.get(members[0], set())
        for m in members[1:]: common &= fp.get(m, set())
        console.print(f"  Cluster [{len(members)} IPs, {len(common)} shared targets]: "
                      f"[cyan]{members[:5]}[/cyan]"
                      + (" ..." if len(members)>5 else ""))

    # -- Plots -----------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    # Port scan: top-15 scanners
    if not scans.empty:
        top_scan = scans.groupby("source")["distinct_ports"].sum().nlargest(10)
        axes[0].barh(top_scan.index[::-1], top_scan.values[::-1], color="coral")
        axes[0].set_title("Stealthy Scanners - Distinct Ports", fontweight="bold")
        axes[0].set_xlabel("Distinct destination ports scanned")
    # Slow DDoS growth for top-5 targets
    if not slow_ddos.empty:
        top5_tgt = slow_ddos["destination"].head(5).tolist()
        for tgt in top5_tgt:
            sub = hdst[hdst["destination"]==tgt]
            axes[1].plot(sub["hour"], sub["distinct_srcs"], lw=1.2, marker=".", ms=3, label=tgt)
        axes[1].set_title("Slow DDoS - Distinct Source Growth", fontweight="bold")
        axes[1].set_xlabel("Hour"); axes[1].set_ylabel("Distinct sources")
        axes[1].tick_params(axis="x", rotation=30); axes[1].legend(fontsize=7)
    # IP hopping cluster sizes
    if hop_clusters:
        sizes = sorted([len(v) for v in hop_clusters.values()], reverse=True)
        axes[2].bar(range(1, len(sizes)+1), sizes, color="steelblue")
        axes[2].set_title("IP Hopping Cluster Sizes", fontweight="bold")
        axes[2].set_xlabel("Cluster #"); axes[2].set_ylabel("IPs in cluster")
    else:
        axes[2].text(0.5, 0.5, "No IP hopping\nclusters found", ha="center", va="center",
                     transform=axes[2].transAxes, fontsize=12, color="grey")
        axes[2].set_title("IP Hopping Clusters", fontweight="bold")
    fig.suptitle("Task 15 - Complex Attack Pattern Detection", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save(fig, "4_15_attacks", cfg)
    return {"stealthy_scans": scans, "slow_ddos": slow_ddos,
            "ip_hop_clusters": hop_clusters, "fp": fp}


# task 16 - malicious payload identification & encrypted traffic anomalies

def task16(df: pd.DataFrame, cfg: dict) -> dict:
    enc_apps = set(cfg["section4"]["encrypted_apps"])
    patterns = cfg["section4"]["payload_patterns"]
    _hdr("Malicious Payload Identification & Encrypted Traffic Anomalies", "Task 16")

    # -- (a) Payload pattern scanning -----------------------------------------
    console.print("\n  [bold](a) Payload pattern scanning[/bold]")
    findings = []
    for col in ["sourcePayloadAsUTF", "destinationPayloadAsUTF"]:
        series = df[col].dropna().astype(str)
        for label, pat in patterns.items():
            try:
                cnt = series.str.contains(pat, regex=True, case=False, na=False).sum()
            except re.error:
                cnt = 0
            if cnt > 0:
                findings.append({"pattern": label, "column": col, "matches": int(cnt)})
    pf = pd.DataFrame(findings).sort_values("matches", ascending=False) if findings else pd.DataFrame()

    if not pf.empty:
        tp = Table(box=box.ROUNDED, padding=(0,2))
        tp.add_column("Pattern",  style="bold"); tp.add_column("Column", style="dim")
        tp.add_column("Matches",  justify="right", style="red")
        for _, r in pf.iterrows():
            tp.add_row(r["pattern"], r["column"], f"{r['matches']:,}")
        console.print(tp)
    else:
        console.print("  [green]No suspicious payload patterns found.[/green]")

    # -- (b) Encrypted traffic analysis ---------------------------------------
    console.print(f"\n  [bold](b) Encrypted traffic analysis[/bold]\n"
                  f"  Encrypted app names: {sorted(enc_apps)}")
    enc = df[df["appName"].isin(enc_apps)].copy()

    enc_breakdown = enc["appName"].value_counts()
    console.print(f"\n  Encrypted flow breakdown:")
    for app, cnt in enc_breakdown.items():
        console.print(f"    [cyan]{app:20s}[/cyan] {cnt:>8,}  ({cnt/len(df)*100:.2f}%)")
    console.print(f"  [bold]Total encrypted flows: {len(enc):,}[/bold] "
                  f"({len(enc)/len(df)*100:.2f}% of dataset)")

    # Anomalies
    enc_small = enc[enc["totalBytes"] < 100]
    enc_short = enc[enc["duration_s"] < 1]
    console.print(f"\n  (b1) Tiny payload (< 100 B): [bold red]{len(enc_small):,}[/bold red] flows")
    console.print(f"  (b2) Sub-second duration   : [bold red]{len(enc_short):,}[/bold red] flows")

    if len(enc) > 10:
        lo, hi = iqr_bounds(enc["avg_pkt_bytes"].dropna())
        enc_pkt = enc[(enc["avg_pkt_bytes"] < lo) | (enc["avg_pkt_bytes"] > hi)]
        console.print(f"  (b3) Packet-size outliers  : [bold red]{len(enc_pkt):,}[/bold red] flows  "
                      f"(IQR bounds: [{max(0,lo):.0f}, {hi:.0f}] B)")
        if not enc_pkt.empty:
            te = Table(box=box.SIMPLE_HEAD, padding=(0,1))
            te.add_column("Source",  style="cyan"); te.add_column("Destination", style="cyan")
            te.add_column("App",     style="magenta")
            te.add_column("Avg pkt (B)", justify="right", style="red")
            te.add_column("Duration", justify="right", style="yellow")
            for _, r in enc_pkt.sort_values("avg_pkt_bytes", ascending=False).head(8).iterrows():
                te.add_row(str(r["source"]), str(r["destination"]), str(r["appName"]),
                           f"{r['avg_pkt_bytes']:.0f}", f"{r['duration_s']:.0f}s")
            console.print(te)

    # -- (c) C2 beaconing ------------------------------------------------------
    c2cfg  = cfg["section4"]["c2_beaconing"]
    console.print(f"\n  [bold](c) C2 beaconing detection[/bold]\n"
                  f"  Criteria: >={c2cfg['min_flows']} flows, IAT CV < {c2cfg['max_iat_cv']}, "
                  f"avg payload < {c2cfg['max_avg_payload_b']} B")
    dfc2 = df.dropna(subset=["startDateTime"]).sort_values("startDateTime")
    dfc2["iat_s"] = (dfc2.groupby(["source","destination"])["startDateTime"]
                         .diff().dt.total_seconds())
    c2s = (dfc2.groupby(["source","destination"])
                .agg(flow_count=("startDateTime","count"),
                     iat_mean=("iat_s","mean"), iat_std=("iat_s","std"),
                     avg_payload=("totalBytes","mean"))
                .reset_index())
    c2s["iat_cv"] = c2s["iat_std"] / c2s["iat_mean"].replace(0, np.nan)
    beacons = c2s[(c2s["flow_count"] >= c2cfg["min_flows"]) &
                  (c2s["iat_cv"]     <  c2cfg["max_iat_cv"]) &
                  (c2s["avg_payload"]<  c2cfg["max_avg_payload_b"])
                  ].sort_values("iat_cv")

    console.print(f"  C2 beaconing candidates: [bold red]{len(beacons)}[/bold red]\n")
    if not beacons.empty:
        tc = Table(box=box.SIMPLE_HEAD, padding=(0,1))
        tc.add_column("Source",     style="cyan"); tc.add_column("Destination", style="cyan")
        tc.add_column("Flows",      justify="right", style="green")
        tc.add_column("IAT Mean",   justify="right", style="yellow")
        tc.add_column("IAT CV",     justify="right", style="red")
        tc.add_column("Avg Payload",justify="right", style="magenta")
        for _, r in beacons.head(12).iterrows():
            tc.add_row(str(r["source"]), str(r["destination"]),
                       f"{r['flow_count']:,}", f"{r['iat_mean']:.0f}s",
                       f"{r['iat_cv']:.4f}", f"{r['avg_payload']:.0f} B")
        console.print(tc)

    # -- Plots -----------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    if not pf.empty:
        top_pf = pf.head(8)
        axes[0].barh(top_pf["pattern"][::-1], top_pf["matches"][::-1], color="coral")
        axes[0].set_title("Suspicious Payload Pattern Matches", fontweight="bold")
        axes[0].set_xlabel("Number of flows")
    if len(enc) > 0:
        enc_breakdown.plot(kind="bar", ax=axes[1], color=sns.color_palette("muted", len(enc_breakdown)))
        axes[1].set_title("Encrypted Traffic by App", fontweight="bold")
        axes[1].set_ylabel("Flows"); axes[1].tick_params(axis="x", rotation=20)
    if not beacons.empty:
        axes[2].scatter(beacons["iat_mean"], beacons["iat_cv"],
                        s=beacons["flow_count"].clip(upper=500)/5,
                        c=beacons["avg_payload"], cmap="YlOrRd", alpha=0.7)
        axes[2].axhline(c2cfg["max_iat_cv"], color="red", lw=1.2, linestyle="--",
                        label=f"CV threshold={c2cfg['max_iat_cv']}")
        axes[2].set_title("C2 Beaconing Candidates\n(size=flows, color=payload)", fontweight="bold")
        axes[2].set_xlabel("Mean IAT (s)"); axes[2].set_ylabel("IAT Coefficient of Variation")
        axes[2].legend(fontsize=8)
    fig.suptitle("Task 16 - Payload & Encrypted Traffic Analysis", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save(fig, "4_16_payload", cfg)
    return {"payload_findings": pf, "encrypted_flows": len(enc),
            "enc_small": len(enc_small), "enc_short": len(enc_short), "beacons": beacons}


# task 17 - threat attribution & risk register

def task17(all_results: dict, df: pd.DataFrame, cfg: dict) -> dict:
    _hdr("Threat Attribution & Risk Register", "Task 17")
    events = []

    def add(level, ttype, src, dst, detail, justification):
        events.append({"risk_level": level, "threat_type": ttype,
                       "source": str(src), "destination": str(dst),
                       "detail": detail, "justification": justification})

    # -- Pull from previous results --------------------------------------------
    r15 = all_results.get("task15", {})
    r16 = all_results.get("task16", {})
    r12 = all_results.get("task12", {})
    r13 = all_results.get("task13", {})
    r14 = all_results.get("task14", {})

    # HIGH - stealthy scans
    scans = r15.get("stealthy_scans", pd.DataFrame())
    for _, r in scans.iterrows():
        add("HIGH","Stealthy Port Scan", r["source"], r["destination"],
            f"{r['distinct_ports']} ports, {r['span_min']:.0f} min span, "
            f"{r['rate_per_min']:.2f} flows/min",
            "Low-rate multi-port probe evades threshold-based IDS")

    # HIGH - slow DDoS
    ddos = r15.get("slow_ddos", pd.DataFrame())
    for _, r in ddos.head(15).iterrows():
        add("HIGH","Slow DDoS", "Multiple", r["destination"],
            f"{r['run_hours']}h monotonic growth, "
            f"{r['start_srcs']}->{r['peak_srcs']} sources (x{r['growth_ratio']})",
            "Gradual resource exhaustion without detectable traffic spike")

    # HIGH - C2 beaconing
    beacons = r16.get("beacons", pd.DataFrame())
    for _, r in beacons.head(20).iterrows():
        add("HIGH","C2 Beaconing", r["source"], r["destination"],
            f"IAT CV={r['iat_cv']:.4f}, {r['flow_count']} flows, "
            f"avg {r['avg_payload']:.0f} B",
            "Perfectly periodic small-payload connections -- malware C2 beacon")

    # HIGH - IP hopping
    for rep, members in list(r15.get("ip_hop_clusters", {}).items())[:10]:
        fp = r15.get("fp", {})
        common = fp.get(members[0], set())
        for m in members[1:]: common &= fp.get(m, set())
        add("HIGH","IP Hopping",
            ", ".join(members[:3]) + (f" +{len(members)-3}" if len(members) > 3 else ""),
            f"{len(common)} shared targets",
            f"{len(members)} IPs, Jaccard >= {cfg['section4']['ip_hopping']['jaccard_threshold']}",
            "Multiple source IPs with >=50% destination overlap -- actor rotating IPs")

    # HIGH - payload threats
    pf = r16.get("payload_findings", pd.DataFrame())
    if not pf.empty:
        high_pats = {"shell_command","download_backdoor","sql_injection"}
        for _, r in pf.iterrows():
            lvl = "HIGH" if r["pattern"] in high_pats else "MEDIUM"
            add(lvl, f"Payload:{r['pattern']}", "Multiple", "Multiple",
                f"{r['matches']:,} flows in {r['column']}",
                f"Payload contains {r['pattern']} signature -- active exploitation or exfiltration")

    # MEDIUM - volume outliers
    outlier_ips = r12.get("outlier_ips_series", pd.Series())
    for ip, val in (outlier_ips.head(8).items() if not outlier_ips.empty else []):
        add("MEDIUM","Traffic Volume Outlier", ip, "Multiple",
            f"{val/1e9:.2f} GB total (> mean+3sigma)",
            "Unusually high bandwidth -- possible exfiltration or compromised relay")

    # MEDIUM - long flows
    long_flows = r14.get("long_flows_df", pd.DataFrame())
    for _, r in long_flows.head(8).iterrows():
        add("MEDIUM","Long-Duration Flow", r["source"], r["destination"],
            f"{r['duration_s']:.0f}s duration, {r['totalBytes']:,} B, {r['protocolName']}",
            "Persistent connection far beyond typical -- possible tunnel, RAT or C2")

    # MEDIUM - multi-protocol
    mp_sus = r14.get("mp_sus", pd.DataFrame())
    for ip in mp_sus["source"].unique()[:8] if not mp_sus.empty else []:
        add("MEDIUM","Multi-Protocol Burst", ip, "Multiple",
            f">{cfg['section3']['suspicious']['multi_proto_min']} protocols "
            f"in {cfg['section3']['suspicious']['multi_proto_window']}",
            "Rapid protocol switching -- scanning, malware probing, or lateral movement")

    # MEDIUM - encrypted anomalies
    if r16.get("enc_small",0) > 0 or r16.get("enc_short",0) > 0:
        add("MEDIUM","Encrypted Traffic Anomaly", "Multiple", "Multiple",
            f"{r16.get('enc_small',0):,} tiny-payload + "
            f"{r16.get('enc_short',0):,} sub-second encrypted flows",
            "Deviates from normal TLS/SSH session behaviour -- possible C2 or scanner")

    # LOW - behavioural spikes
    beh = r13.get("beh_anom", pd.DataFrame())
    for ip in beh["source"].unique()[:5] if not beh.empty else []:
        add("LOW","Behavioural Spike", ip, "Multiple",
            f"Hourly flows > {cfg['section3']['behavioural']['spike_ratio']}x rolling mean",
            "Could be burst traffic, scan, or legitimate download -- needs correlation")

    # LOW - fan-in
    fan_anom = r13.get("fan_anom", pd.DataFrame())
    if not fan_anom.empty:
        for dst in fan_anom["destination"].unique()[:5]:
            peak = fan_anom[fan_anom["destination"]==dst]["distinct_srcs"].max()
            add("LOW","High Fan-In", "Multiple", dst,
                f"Peak {peak} distinct sources in {cfg['section3']['behavioural']['fan_in_window']}",
                "Could be DDoS target or popular public service -- needs validation")

    risk_df = pd.DataFrame(events)
    console.print()
    counts = risk_df["risk_level"].value_counts()

    # Summary table
    ts = Table(box=box.ROUNDED, padding=(0,2),
               title="[bold]Risk Register Summary[/bold]")
    ts.add_column("Risk Level",  style="bold", justify="center", width=12)
    ts.add_column("Events",      justify="right", style="cyan",   width=8)
    ts.add_column("Threat Types", style="dim")
    COLORS = {"HIGH":"red","MEDIUM":"yellow","LOW":"green"}
    for level in ["HIGH","MEDIUM","LOW"]:
        sub = risk_df[risk_df["risk_level"]==level]
        types = ", ".join(sub["threat_type"].unique()[:4])
        if len(sub["threat_type"].unique()) > 4:
            types += " ..."
        ts.add_row(
            Text(level, style=f"bold {COLORS[level]}"),
            str(len(sub)), types
        )
    console.print(ts)

    # Detailed table per level
    for level in ["HIGH","MEDIUM","LOW"]:
        sub = risk_df[risk_df["risk_level"]==level]
        if sub.empty: continue
        color = COLORS[level]
        console.print(f"\n  [bold {color}]━━ {level} RISK ({len(sub)} events) ━━[/bold {color}]")
        td = Table(box=box.SIMPLE_HEAD, padding=(0,1))
        td.add_column("Threat Type", style="bold", min_width=22)
        td.add_column("Source IP(s)", style="cyan", max_width=22)
        td.add_column("Destination", style="cyan", max_width=18)
        td.add_column("Detail",      style="dim",  max_width=45)
        for _, r in sub.head(12).iterrows():
            td.add_row(r["threat_type"][:24], r["source"][:22],
                       r["destination"][:18], r["detail"][:44])
        console.print(td)

    # -- Plots -----------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    # Pie chart of risk levels
    rc = risk_df["risk_level"].value_counts()
    pie_colors = [{"HIGH":"#E74C3C","MEDIUM":"#F39C12","LOW":"#27AE60"}.get(l,"grey")
                  for l in rc.index]
    axes[0].pie(rc.values, labels=rc.index, autopct="%1.0f%%",
                colors=pie_colors, startangle=90,
                wedgeprops={"edgecolor":"white","linewidth":1.5})
    axes[0].set_title("Risk Level Distribution", fontweight="bold")
    # Threat type bar chart
    tc_cnt = risk_df["threat_type"].value_counts().head(10)
    bar_colors = [{"HIGH":"#E74C3C","MEDIUM":"#F39C12","LOW":"#27AE60"}.get(
        risk_df.loc[risk_df["threat_type"]==t,"risk_level"].values[0],"grey")
        for t in tc_cnt.index]
    axes[1].barh(tc_cnt.index[::-1], tc_cnt.values[::-1], color=bar_colors[::-1])
    axes[1].set_title("Events by Threat Type", fontweight="bold")
    axes[1].set_xlabel("Number of events")
    fig.suptitle("Task 17 - Threat Attribution & Risk Register", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save(fig, "4_17_risk_register", cfg)
    return {"risk_df": risk_df}
