#Advance Computer Networks (COL7524)
#===Mini Project : Empirical Validation & Extended Analysis of TIMELY Congestion Control Protocol===
#Member 1: Lt Col Dey Sanjeetkumar, 	Entry No: 2025JCS2949
#Member 2: Lt Col Saurabh Kumar Singh, 	Entry No: 2025JCS3011

#!/usr/bin/env python3
# ============================================
# generate_graphs.py — TIMELY vs DCTCP Plotter
# ============================================

import os, glob, warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Silence layout and deprecation warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

OUTPUT_DIR = "output/graphs_fixed"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ------------------------------------------------------------
def load_and_normalize(pattern):
    files = sorted(glob.glob(pattern))
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        for col in ["Time_us", "SenderID", "RTT_us", "Rate_Mbps", "QueueSize_bits"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["Time_s"] = df.get("Time_us", 0) / 1e6
        df["Rate_Gbps"] = df.get("Rate_Mbps", 0) / 1000.0
        df["Queue_KB"] = df.get("QueueSize_bits", 0) / (8 * 1024)
        dfs.append(df)
    df = pd.concat(dfs, ignore_index=True)
    df = df.dropna(subset=["Time_s"])
    if len(df) > 300:
        df = df[df["Time_s"] > df["Time_s"].max() * 0.2]
    return df

# ------------------------------------------------------------
def summarize(df, field, agg_type="sender", max_points=1000):
    if df.empty or field not in df.columns:
        return pd.DataFrame(columns=["Time_s", "median", "p25", "p75"])

    if agg_type == "agg" and (df["SenderID"] == -1).any():
        agg = df[df["SenderID"] == -1].sort_values("Time_s")[["Time_s", field]].rename(columns={field: "median"})
        agg["p25"], agg["p75"] = agg["median"], agg["median"]
    else:
        per = df[df["SenderID"] != -1]
        grouped = per.groupby("Time_s")[field].agg(["mean", "min", "max"]).reset_index()
        grouped.rename(columns={"mean": "median", "min": "p25", "max": "p75"}, inplace=True)
        agg = grouped

    if len(agg) > max_points:
        agg = agg.iloc[:: max(1, len(agg) // max_points)]
    return agg.ffill().bfill().reset_index(drop=True)

def auto_ylim(vals):
    if len(vals) == 0:
        return (0, 1)
    vmin, vmax = np.nanmin(vals), np.nanmax(vals)
    if np.isclose(vmin, vmax):
        pad = abs(vmin) * 0.05 if abs(vmin) > 1e-6 else 0.5
        return (max(0, vmin - pad), vmax + pad)
    span = vmax - vmin
    return (max(0, vmin - 0.1 * span), vmax + 0.1 * span)

# ------------------------------------------------------------
def single_plot(exp, df, field, ylabel, title, fname, agg_type="sender"):
    s = summarize(df, field, agg_type=agg_type)
    plt.figure(figsize=(10, 4))
    if not s.empty:
        plt.plot(s["Time_s"], s["median"], "b-", lw=1.2, label="TIMELY median")
        plt.fill_between(s["Time_s"], s["p25"], s["p75"], color="b", alpha=0.25)
        plt.ylim(*auto_ylim(s["median"]))
    else:
        plt.ylim(0, 1)
    plt.xlabel("Time (s) [Steady State]")
    plt.ylabel(ylabel, color="blue")
    plt.title(title)
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, fname), dpi=250)
    plt.close()
    print(f"[Saved] {fname}")

def dual_plot(exp, df_t, df_d, field, ylabel, title, fname, agg_type_t="sender", agg_type_d="sender"):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True, gridspec_kw={"hspace": 0.12})
    s_t = summarize(df_t, field, agg_type=agg_type_t)
    if not s_t.empty:
        ax1.plot(s_t["Time_s"], s_t["median"], "b-", lw=1.2, label="TIMELY median")
        ax1.fill_between(s_t["Time_s"], s_t["p25"], s_t["p75"], color="b", alpha=0.25)
        ax1.set_ylim(*auto_ylim(s_t["median"]))
    ax1.set_ylabel(f"TIMELY {ylabel}", color="blue")
    ax1.grid(True, linestyle="--", alpha=0.4)
    ax1.legend(loc="best")

    s_d = summarize(df_d, field, agg_type=agg_type_d)
    if not s_d.empty:
        ax2.plot(s_d["Time_s"], s_d["median"], "r-", lw=1.2, label="DCTCP median")
        ax2.fill_between(s_d["Time_s"], s_d["p25"], s_d["p75"], color="r", alpha=0.25)
        ax2.set_ylim(*auto_ylim(s_d["median"]))
    ax2.set_ylabel(f"DCTCP {ylabel}", color="red")
    ax2.set_xlabel("Time (s) [Steady State]")
    ax2.grid(True, linestyle="--", alpha=0.4)
    ax2.legend(loc="best")

    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(os.path.join(OUTPUT_DIR, fname), dpi=250)
    plt.close()
    print(f"[Saved] {fname}")

def rtt_cdf(exp, df_t, df_d):
    plt.figure(figsize=(6, 4))
    bins = np.linspace(0, 600, 120)
    if not df_t.empty and "RTT_us" in df_t.columns:
        h, e = np.histogram(df_t[df_t["RTT_us"] > 0]["RTT_us"], bins=bins, density=True)
        plt.plot(e[1:], np.cumsum(h) / np.sum(h), "b-", lw=1.3, label="TIMELY RTT CDF")
    if not df_d.empty and "RTT_us" in df_d.columns:
        h, e = np.histogram(df_d[df_d["RTT_us"] > 0]["RTT_us"], bins=bins, density=True)
        plt.plot(e[1:], np.cumsum(h) / np.sum(h), "r-", lw=1.3, label="DCTCP RTT CDF")
    plt.xlabel("RTT (µs)")
    plt.ylabel("CDF")
    plt.xlim(0, 600)
    plt.ylim(0, 1.05)
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"exp_{exp}_rtt_cdf.png"), dpi=250)
    plt.close()
    print(f"[Saved] exp_{exp}_rtt_cdf.png")

# ------------------------------------------------------------
def main():
    dual_exps = [2, 4, 5, 6]
    single_exps = [1, 3]
    print("=== Generating Graphs ===")
    for exp in single_exps + dual_exps:
        df_t = load_and_normalize(f"output/csv/exp{exp}_timely_run*.csv")
        df_d = load_and_normalize(f"output/csv/exp{exp}_dctcp_run*.csv")

        if exp in single_exps and not df_t.empty:
            print(f"→ Exp {exp}: TIMELY only")
            single_plot(exp, df_t, "Queue_KB", "Queue Size (KB)", f"Experiment {exp}: Queue Dynamics",
                        f"exp_{exp}_queue.png", agg_type="agg")
            single_plot(exp, df_t, "RTT_us", "RTT (µs)", f"Experiment {exp}: RTT Dynamics",
                        f"exp_{exp}_rtt.png", agg_type="sender")
            rtt_cdf(exp, df_t, pd.DataFrame())
            single_plot(exp, df_t, "Rate_Gbps", "Per Sender Throughput (Gbps)",
                        f"Experiment {exp}: Aggregate Throughput vs Time",
                        f"exp_{exp}_throughput.png", agg_type="sender")

        elif exp in dual_exps and (not df_t.empty or not df_d.empty):
            print(f"→ Exp {exp}: TIMELY vs DCTCP")
            # FIXED: Ensure DCTCP uses 'sender' aggregation for Exp 4 (Dynamic RTT)
            # Only use 'agg' for queue plots or if specifically desired, but here 
            # we want throughput/RTT distributions which are sender-based.
            agg_type_d = "sender" if exp in [2, 4, 5, 6] else "agg"

            dual_plot(exp, df_t, df_d, "Queue_KB", "Queue Size (KB)",
                      f"Experiment {exp}: Queue Dynamics", f"exp_{exp}_queue.png",
                      agg_type_t="agg", agg_type_d=agg_type_d) # Note: Queue might need 'agg' if using switch logs
            
            # For RTT and Throughput, we ALWAYS want sender stats
            dual_plot(exp, df_t, df_d, "RTT_us", "RTT (µs)",
                      f"Experiment {exp}: RTT Dynamics", f"exp_{exp}_rtt.png",
                      agg_type_t="sender", agg_type_d="sender")
            
            rtt_cdf(exp, df_t, df_d)
            
            dual_plot(exp, df_t, df_d, "Rate_Gbps", "Per Sender Throughput (Gbps)",
                      f"Experiment {exp}: Aggregate Throughput vs Time",
                      f"exp_{exp}_throughput.png", agg_type_t="sender", agg_type_d="sender")

    print("\n All graphs saved to 'output/graphs_fixed/'")

if __name__ == "__main__":
    main()