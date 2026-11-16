# SIL7165 – Assignment 3: Network Traffic Analysis

**Course:** SIL7165 – Network Systems and Security
**Dataset:** 6 CSV log files, ~2.07 million network flow records, ~1.59 GB total
**Entry point:** `analysis.ipynb` (Jupyter Notebook)
**Submitted By:**Lt Col Saurabh Kumar Singh, 2025JCS3011

Analyses ~2.07M network flows captured over 7 days (June 11–17, 2010). Covers protocol statistics, sublinear-space cardinality estimation (HyperLogLog / CMS / Bloom filter), anomaly detection, and threat attribution. All tables and charts render inline in the notebook.

---

## Assignment Coverage

All 17 required tasks are implemented. The table below maps each task to its notebook cell(s) and supporting module.

| # | Task | Notebook Cells | Module | Status |
|---|------|---------------|--------|--------|
| 1.1 | Total number of network flows | 6 | `section1_basic_stats.task1` | Complete |
| 1.2 | Top-k most frequent protocols | 7 | `section1_basic_stats.task2` | Complete |
| 1.3 | Top-10 source/destination IPs by traffic volume | 8 | `section1_basic_stats.task3` | Complete |
| 1.4 | Average packet size & representativeness | 9 | `section1_basic_stats.task4` | Complete |
| 1.5 | Top-3 source–destination pairs | 10 | `section1_basic_stats.task5` | Complete |
| 1.6 | Consistent communication patterns across time windows | 11 | `section1_basic_stats.task6` | Complete |
| 1.7 | Irregular traffic spike detection | 12 | `section1_basic_stats.task7` | Complete |
| 1.8 | Packet size variance analysis | 13 | `section1_basic_stats.task8` | Complete |
| 2a | HyperLogLog – unique IP count estimation | 14–16 | `section2_sublinear.task9` | Complete |
| 2b | Count-Min Sketch – heavy-hitter destination IPs | 17–18 | `section2_sublinear.task10` | Complete |
| 2c | Bloom Filter – IP blocklist membership testing | 19–20 | `section2_sublinear.task11` | Complete |
| 3a | Statistical traffic analysis (IQR/Z-score thresholds) | 21–23 | `section3_anomaly.task12` | Complete |
| 3b | Behavioural analysis (spikes, fan-in, correlation) | 24–26 | `section3_anomaly.task13` | Complete |
| 3c | Suspicious communication patterns | 27–29 | `section3_anomaly.task14` | Complete |
| 4a | Complex attack patterns (port scan / slow DDoS / IP hopping) | 30–34 | `section4_threats.task15` | Complete |
| 4b | Malicious payload identification & encrypted traffic anomalies | 35–38 | `section4_threats.task16` | Complete |
| 4c | Threat attribution & risk register | 39–40 | `section4_threats.task17` | Complete |

---

## Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.10+ | Check with `python --version` |
| Free RAM | ~4 GB | All 6 CSV files are loaded into memory |
| Free disk | ~2 GB | For the dataset + outputs |
| OS | Windows 10/11, Linux, macOS | All platforms supported |
| Internet | Required once | Only for initial `pip install` |

The CSV log files must be present in the `logs/` folder before running. The notebook will fail at the data-loading cell if any file is missing.

---

## Setup

### Single command — Windows (Command Prompt or PowerShell)

```bat
python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt
```

### Single command — Linux / macOS

```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

This creates an isolated virtual environment named `venv`, activates it, and installs every dependency in one step. You only need to do this once per machine.

> **Note:** On subsequent sessions you only need to activate the venv — no need to reinstall:
> - Windows: `venv\Scripts\activate`
> - Linux/macOS: `source venv/bin/activate`

---

## Running the Analysis

### Step 1 — Activate the virtual environment (if not already active)

```bat
# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

You will see `(venv)` prepended to your shell prompt when it is active.

### Step 2 — Launch Jupyter

```bash
jupyter notebook
```

This opens the Jupyter interface in your default browser at `http://localhost:8888`.
If the browser does not open automatically, copy the URL printed in the terminal (it includes a token).

### Step 3 — Open the notebook

Click **`analysis.ipynb`** in the file browser.

### Step 4 — Run the full analysis

In the menu bar: **Kernel → Restart Kernel and Run All Cells**

This executes all 41 cells in order and produces every output described in this README.
Expected total runtime: **5–15 minutes** depending on hardware (dominated by the 1.59 GB CSV load).

When the last cell (Task 4c — Risk Register) completes, the analysis is finished. All tables are printed inline and all charts are saved to `outputs/figures/`.

---

## Project Structure

```
NSS-A3/
├── analysis.ipynb            <- Main notebook (entry point -- run this)
├── config.yaml               <- All algorithm parameters and paths (edit here, not in code)
├── requirements.txt          <- Python dependencies
├── README.md                 <- This file
├── SIL765_Assignment_3.pdf   <- Original assignment specification
|
├── logs/                     <- Place all 6 CSV files here
│   ├── network_analysis_data1.csv   (82 MB,  171 380 rows, June 13-14 2010)
│   ├── network_analysis_data2.csv   (40 MB,  133 193 rows, June 11-12 2010)
│   ├── network_analysis_data3.csv   (78 MB,  275 528 rows, June 12-13 2010)
│   ├── network_analysis_data4.csv   (349 MB, 397 595 rows, June 16-17 2010)
│   ├── network_analysis_data5.csv   (632 MB, 571 698 rows, June 14-15 2010)
│   └── network_analysis_data6.csv   (409 MB, 522 263 rows, June 15-16 2010)
|
├── src/                      <- Supporting Python modules (imported by notebook)
│   ├── __init__.py
│   ├── config_loader.py      <- Loads and validates config.yaml
│   ├── data_loader.py        <- Chunked CSV loading with progress display
│   ├── section1_basic_stats.py  <- Tasks 1.1-1.8
│   ├── section2_sublinear.py    <- Tasks 2a-2c (HyperLogLog, CMS, Bloom Filter)
│   ├── section3_anomaly.py      <- Tasks 3a-3c
│   └── section4_threats.py      <- Tasks 4a-4c
|
└── outputs/                  <- Created automatically on first run
    └── figures/              <- All PNG charts (150 dpi, saved after each section)
```

---

## Dataset Structure

Each of the 6 CSV files shares the same 21-column schema:

| Column | Type | Description |
|--------|------|-------------|
| `generated` | datetime | Timestamp the record was written |
| `appName` | string | Detected application (HTTP, DNS, SSH, BitTorrent, …) |
| `totalSourceBytes` | int | Bytes sent by source host |
| `totalDestinationBytes` | int | Bytes sent by destination host |
| `totalSourcePackets` | int | Packets sent by source |
| `totalDestinationPackets` | int | Packets sent by destination |
| `sourcePayloadAsBase64` | string | Raw source payload (Base64-encoded) |
| `sourcePayloadAsUTF` | string | Raw source payload (UTF-8 text) |
| `destinationPayloadAsBase64` | string | Raw destination payload (Base64-encoded) |
| `destinationPayloadAsUTF` | string | Raw destination payload (UTF-8 text) |
| `direction` | string | Traffic direction: L2R, R2L, or L2L |
| `sourceTCPFlagsDescription` | string | TCP flags from source (e.g. `S,A`, `F,A`) |
| `destinationTCPFlagsDescription` | string | TCP flags from destination |
| `source` | string | Source IP address |
| `protocolName` | string | Transport protocol (`tcp_ip`, `udp_ip`) |
| `sourcePort` | int | Source port number |
| `destination` | string | Destination IP address |
| `destinationPort` | int | Destination port number |
| `startDateTime` | datetime | Session start time |
| `stopDateTime` | datetime | Session end time |
| `Label` | string | Ground-truth label: `Normal` or `Attack` |

The notebook also derives four additional columns at load time:

| Derived column | Formula | Used by |
|----------------|---------|---------|
| `totalBytes` | `totalSourceBytes + totalDestinationBytes` | Tasks 1.3, 3a |
| `totalPackets` | `totalSourcePackets + totalDestinationPackets` | Task 1.4 |
| `duration_s` | `(stopDateTime − startDateTime).total_seconds()` | Tasks 3c, 4b |
| `avg_pkt_bytes` | `totalBytes / totalPackets` (NaN-safe) | Tasks 1.4, 1.8 |

---

## Configuration Reference (`config.yaml`)

All thresholds and algorithm parameters are in `config.yaml`. You never need to edit the source code to change behaviour.

### `data` section

| Key | Default | Description |
|-----|---------|-------------|
| `data.base_dir` | `"logs"` | Folder containing CSV files (relative to project root) |
| `data.files` | (all 6 files) | List of CSV filenames to load; leave `[]` to auto-glob |
| `data.chunk_size` | `100000` | Rows per read chunk — reduce to `50000` if you get OOM errors |

### `output` section

| Key | Default | Description |
|-----|---------|-------------|
| `output.figures_dir` | `"outputs/figures"` | Where PNG charts are saved |
| `output.show_plots` | `true` | Set `false` on headless machines (no GUI) |
| `output.save_plots` | `true` | Whether to save figures to disk |

### `section1` section

| Key | Default | Description |
|-----|---------|-------------|
| `section1.top_k_protocols` | `5` | k for Task 1.2 top-k protocols chart |
| `section1.top_n_ips` | `10` | Number of IPs shown in Task 1.3 |
| `section1.top_n_pairs` | `3` | Number of src–dst pairs in Task 1.5 |
| `section1.time_window` | `"1h"` | Tumbling window size for Task 1.6 (pandas offset string) |
| `section1.consistent_ip_min_pct` | `0.80` | Fraction of windows an IP must appear in to be "consistent" |
| `section1.spike_bin` | `"5min"` | Bin width for the Task 1.7 time-series |
| `section1.spike_z_threshold` | `2.0` | Z-score above which a bin is flagged as a spike |

### `section2` section

| Key | Default | Description |
|-----|---------|-------------|
| `section2.hyperloglog.precision_bits` | `12` | b parameter → m = 2^b registers; higher = more accurate |
| `section2.count_min_sketch.hash_rows` | `5` | Number of hash functions (d) |
| `section2.count_min_sketch.hash_width` | `10000` | Number of buckets per hash row (w) |
| `section2.count_min_sketch.heavy_hitter_pct` | `0.01` | IPs with estimated count > N × this are heavy hitters |
| `section2.bloom_filter.target_fpr` | `0.01` | Desired false-positive rate (1%) |
| `section2.bloom_filter.probe_count` | `100000` | Random IPs used to measure actual FPR |

### `section3` section

| Key | Default | Description |
|-----|---------|-------------|
| `section3.statistical.iqr_multiplier` | `1.5` | IQR fence multiplier for outlier bounds |
| `section3.statistical.outlier_z_sigma` | `3.0` | Per-IP bytes: flag if > mean + z×std |
| `section3.statistical.protocol_dev_sigma` | `2.0` | Hourly protocol share deviation threshold |
| `section3.behavioural.spike_ratio` | `5.0` | Flow count must be > ratio × rolling mean to be a spike |
| `section3.behavioural.rolling_hours` | `3` | Rolling mean window width in hours |
| `section3.behavioural.fan_in_min_src` | `20` | Distinct sources needed in one window to flag fan-in |
| `section3.behavioural.fan_in_window` | `"5min"` | Time window for fan-in detection |
| `section3.suspicious.long_dur_z_sigma` | `3.0` | Duration threshold: flag if > mean + z×std |
| `section3.suspicious.multi_proto_window` | `"60s"` | Window for multi-protocol detection |
| `section3.suspicious.multi_proto_min` | `3` | Minimum distinct protocols in window to flag |

### `section4` section

| Key | Default | Description |
|-----|---------|-------------|
| `section4.port_scan.min_distinct_ports` | `30` | Distinct destination ports to qualify as a scan |
| `section4.port_scan.min_span_minutes` | `10` | Minimum duration over which scan occurs |
| `section4.port_scan.max_rate_per_min` | `5.0` | Maximum flow rate (stealthy = low rate) |
| `section4.slow_ddos.min_run_hours` | `3` | Minimum consecutive hours for slow DDoS pattern |
| `section4.slow_ddos.min_peak_sources` | `5` | Peak distinct source IPs required |
| `section4.slow_ddos.min_growth_ratio` | `1.5` | Minimum per-hour growth ratio in source count |
| `section4.ip_hopping.jaccard_threshold` | `0.50` | Minimum Jaccard similarity to link two IPs as same actor |
| `section4.ip_hopping.min_cluster_size` | `3` | Minimum IPs in a cluster to flag as IP hopping |
| `section4.c2_beaconing.min_flows` | `5` | Minimum connections needed to detect beaconing |
| `section4.c2_beaconing.max_iat_cv` | `0.30` | Max coefficient of variation for inter-arrival times |
| `section4.c2_beaconing.max_avg_payload_b` | `500` | Max average payload for C2 classification |

---

## Section-by-Section Task Guide

### Section 1 — Basic Network Traffic Statistics

---

#### Task 1.1 — Total number of network flows
**Notebook cell:** 6
**Function:** `src/section1_basic_stats.py` → `task1(df, cfg)`

**Requirement:** Compute the total number of network flows in the dataset.

**Approach:** A single `len(df)` gives the flow count. The function also reports unique source IPs, unique destination IPs, unique protocols, date range, and total bytes as an orientation summary.

**Expected output:**
```
╭─ Task 1.1  Total Number of Network Flows ──────────────────╮
│ Metric                    Value                             │
│ Total flows               2,071,657                         │
│ Unique source IPs         ~543 000                          │
│ Unique destination IPs    ~180 000                          │
│ Unique protocols          15                                 │
│ Date range                2010-06-11 → 2010-06-17           │
│ Total bytes transferred   ~XX GB                            │
╰──────────────────────────────────────────────────────────────╯
```

---

#### Task 1.2 — Top-k most frequent protocols
**Notebook cell:** 7
**Function:** `task2(df, cfg)`
**Config key:** `section1.top_k_protocols` (default 5)

**Requirement:** Identify the top k most frequently used protocols (k configurable).

**Approach:** Group by `appName`, count flows, sort descending. The bar chart shows absolute counts; a pie chart shows percentage share.

**Expected output:** Console table + `outputs/figures/fig_1_2_protocols.png` (bar + pie charts).
Top protocols are typically: `HTTPWeb`, `DNS`, `SecureWeb`, `SSH`, `BitTorrent`.

---

#### Task 1.3 — Top-10 source and destination IPs by traffic volume
**Notebook cell:** 8
**Function:** `task3(df, cfg)`
**Config key:** `section1.top_n_ips` (default 10)

**Requirement:** Identify the top 10 most active source and destination IPs. Specify the metric used.

**Approach:** Metric is **total bytes** (`totalSourceBytes` for sources, `totalDestinationBytes` for destinations). Bytes reflects actual data volume rather than packet count, making it more representative of bandwidth consumers.

**Expected output:** Two side-by-side horizontal bar charts → `outputs/figures/fig_1_3_top10_ips.png`.

---

#### Task 1.4 — Average packet size and representativeness
**Notebook cell:** 9
**Function:** `task4(df, cfg)`

**Requirement:** Compute average packet size across all flows. Comment on whether the average is representative.

**Approach:** `avg_pkt_bytes = totalBytes / totalPackets`. Reports mean, median, standard deviation, and skewness. Representativeness is assessed: if `skewness > 1` or `std > mean`, the distribution is right-skewed and the mean is not representative — the median should be preferred.

**Expected output:** Summary table + histogram with mean/median markers → `outputs/figures/fig_1_4_pkt_size_dist.png`.

---

#### Task 1.5 — Top-3 source–destination pairs
**Notebook cell:** 10
**Function:** `task5(df, cfg)`

**Requirement:** Identify the top 3 most frequent source–destination pairs.

**Approach:** Group by `(source, destination)`, count flows, take top 3. Each pair is shown with its protocol distribution.

**Expected output:** Console table with rank, source IP, destination IP, flow count, and dominant protocol.

---

#### Task 1.6 — Consistent communication patterns across time windows
**Notebook cell:** 11
**Function:** `task6(df, cfg)`
**Config keys:** `section1.time_window` (default `1h`), `section1.consistent_ip_min_pct` (default `0.80`)

**Requirement:** Determine which IP addresses exhibit consistent communication patterns across multiple time windows. Define and justify the notion of "time window".

**Approach:** **Time window:** 1-hour tumbling windows on `startDateTime` (floor to hour). An IP is "consistent" if it appears in ≥ 80% of all observed windows. Rationale: 1-hour granularity is long enough to capture typical service behaviour, short enough to detect intermittent actors.

**Expected output:** Table of IP addresses active in ≥ 80% of windows, with their window presence count and percentage.

---

#### Task 1.7 — Irregular traffic spike detection
**Notebook cell:** 12
**Function:** `task7(df, cfg)`
**Config keys:** `section1.spike_bin` (default `5min`), `section1.spike_z_threshold` (default `2.0`)

**Requirement:** Detect and highlight irregular spikes in traffic volume. Specify the method and discuss possible causes.

**Approach:** **Method:** Count flows per 5-minute bin. Compute mean (μ) and standard deviation (σ) of bin counts. A bin is a spike if its count > μ + 2σ (Z-score > 2.0, catching the top ~2.5% of bins). Possible causes include DDoS bursts, scheduled backups, scan sweeps, or network events.

**Expected output:** Time-series plot with baseline, threshold line, and spike bins highlighted in red → `outputs/figures/fig_1_7_spikes.png`. Console table lists the top spike bins with timestamps and flow counts.

---

#### Task 1.8 — Packet size variance analysis
**Notebook cell:** 13
**Function:** `task8(df, cfg)`

**Requirement:** Compute the variance of packet sizes and analyse potential reasons for high or low variance.

**Approach:** Computes variance, standard deviation, and coefficient of variation (CV = std/mean). **High variance** (CV > 1) in this dataset is expected: it contains a mix of DNS (tiny ~50 B), HTTP (medium ~500 B), and file-transfer (large ~1500 B) flows — different application protocols inherently produce different packet sizes.

**Expected output:** Summary statistics table with interpretation text.

---

### Section 2 — Traffic Estimation Using Sublinear Space

---

#### Task 2a (Task 9) — HyperLogLog: unique IP address estimation
**Notebook cells:** 14–16
**Function:** `src/section2_sublinear.py` → `task9(df, cfg)`
**Config keys:** `section2.hyperloglog.precision_bits` (default `12`)

**Requirement:** Estimate total distinct IP addresses using sublinear space. Compare with exact count. Error ≤ 10%. Analyse trade-offs.

**Algorithm:** HyperLogLog (Flajolet et al., 2007).
- Each IP is hashed with a 64-bit hash.
- The hash is split: the leading `b` bits select one of `m = 2^b` registers; the position of the leftmost `1` in the remaining bits is stored.
- Cardinality is estimated from the harmonic mean of 2^(register values), corrected with the constant α_m.
- At `b = 12`: m = 4,096 registers, ~4 KB memory, theoretical standard error ≈ 1.6%.

**Trade-offs:**
- Space: 4 KB vs ~4 MB for an exact Python `set` of the same IPs (1,000× savings)
- Accuracy: ~1.6% error vs 0% for exact
- Speed: single pass, O(n) time with no hash collisions to resolve

**Expected output:** Table comparing HLL estimate vs exact count with error percentage. Error should be well under 10%.

---

#### Task 2b (Task 10) — Count-Min Sketch: heavy-hitter destination IPs
**Notebook cells:** 17–18
**Function:** `task10(df, cfg)`
**Config keys:** `section2.count_min_sketch.*`

**Requirement:** Identify destination IPs receiving a significant fraction of total traffic (heavy hitters). Use a space-efficient approximate method. Compare with exact counts. Error < 10%.

**Algorithm:** Count-Min Sketch (Cormode & Muthukrishnan, 2005).
- A `d × w` integer matrix (d = 5 hash rows, w = 10,000 columns).
- For each flow, increment cells `(i, h_i(dst_ip) mod w)` for each of the d hash functions.
- To query an IP, return `min(matrix[i][h_i(ip)])` — the minimum across rows upper-bounds the true count.
- An IP is a "heavy hitter" if its estimated count > `heavy_hitter_pct × N`.

**Trade-offs:**
- Space: 200 KB (5 × 10,000 × 4-byte ints) vs ~14 MB for an exact `Counter`
- Guarantees: overestimate only (never undercount), error ε = e/w ≈ 0.00027 with probability ≥ 1 − δ = 1 − e^(−d) ≈ 0.99

**Expected output:** Side-by-side table of heavy hitters: CMS estimate vs exact count, relative error per IP.

---

#### Task 2c (Task 11) — Bloom Filter: IP blocklist membership testing
**Notebook cells:** 19–20
**Function:** `task11(df, cfg)`
**Config keys:** `section2.bloom_filter.*`

**Requirement:** Determine whether an IP has been previously observed without storing all IPs. Compare FPR and space with exact membership test.

**Algorithm:** Bloom Filter (Bloom, 1970) using `bitarray` for bit-level efficiency.
- Given target FPR p = 1%, the optimal number of bits is `m = −n × ln(p) / (ln 2)^2` and optimal hash functions `k = (m/n) × ln 2`.
- All unique source IPs from the dataset are inserted.
- Membership queries return `True` (possibly false positive) or `False` (definite negative — zero false negatives guaranteed).

**Trade-offs:**
- Space: ~2.9 KB (Bloom) vs ~121 KB (exact Python `set`) — ~42× savings
- False negatives: 0 (guaranteed)
- False positives: ~1% (configurable via `target_fpr`)

**Expected output:** Table showing m (bits), k (hash functions), actual measured FPR on `probe_count` random IPs, and space comparison.

---

### Section 3 — Advanced Anomaly Detection

---

#### Task 3a (Task 12) — Statistical traffic analysis
**Notebook cells:** 21–23
**Function:** `src/section3_anomaly.py` → `task12(df, cfg)`

**Requirement:** Define statistical thresholds for anomalies in packet sizes, flow counts, and protocol distributions. Compare traffic across time windows. Flag unusual IP volumes.

**Approach:**
- **Packet size outliers:** IQR method. Lower fence = Q1 − 1.5×IQR; upper fence = Q3 + 1.5×IQR.
- **Per-IP traffic anomalies:** Z-score. Flag IPs where total bytes > mean + 3σ or < mean − 3σ.
- **Protocol distribution shift:** Hourly vs daily protocol share. Chi-squared test on the contingency table; if p < 0.05, the distribution has shifted significantly between windows.

**Expected output:** Three tables (packet outliers, anomalous IPs, protocol deviation) + `outputs/figures/fig_3a_heatmap.png` (hourly protocol heatmap).

---

#### Task 3b (Task 13) — Behavioural analysis
**Notebook cells:** 24–26
**Function:** `task13(df, cfg)`

**Requirement:** Detect IPs with sudden behaviour changes. Detect network-wide correlation (multiple IPs targeting same destination). Identify high fan-in destinations.

**Approach:**
- **Sudden spikes:** Per-IP hourly flow counts. Flag if current count > `spike_ratio` × 3-hour rolling mean (default 5×). This catches IPs that were idle and suddenly generate bursts.
- **Fan-in detection (potential DDoS):** In each 5-minute window, identify destination IPs receiving traffic from ≥ 20 distinct source IPs. Large fan-in indicates DDoS or coordinated scanning.
- **Correlation patterns:** IPs that contact the same destination within the same short window.

**Expected output:** Tables of spike IPs (with before/after flow counts), fan-in destinations (with source counts), and correlated source groups.

---

#### Task 3c (Task 14) — Suspicious communication patterns
**Notebook cells:** 27–29
**Function:** `task14(df, cfg)`

**Requirement:** Identify long-duration connections. Detect IPs using multiple protocols in a short span.

**Approach:**
- **Long-duration flows:** Flag connections with `duration_s > mean + 3σ`. Long sessions can indicate data exfiltration, tunnelling, or persistent backdoors.
- **Multi-protocol abuse:** In a 60-second sliding window, flag source IPs that use ≥ 3 distinct `protocolName` or `appName` values. Legitimate hosts rarely switch protocols rapidly; this pattern is associated with scanners and lateral movement.

**Expected output:** Table of long-duration flows (source, destination, duration, application) and table of multi-protocol abusers.

---

### Section 4 — Deep Security Threat Analysis

---

#### Task 4a (Task 15) — Complex attack pattern detection
**Notebook cells:** 30–34
**Function:** `src/section4_threats.py` → `task15(df, cfg)`

**Requirement:** Detect stealthy port scans, slow DDoS attacks, and IP hopping behaviour.

**Sub-task 15.1 — Stealthy port scan:**
- **Signature:** A source IP probes ≥ 30 distinct destination ports on the same target host, spread over ≥ 10 minutes at a rate < 5 flows/minute.
- **Rationale:** Traditional IDS threshold-based detection misses scans that stay below the packet-rate trigger. Requiring a minimum time span ensures we catch low-and-slow scanners.

**Sub-task 15.2 — Slow DDoS:**
- **Signature:** A destination IP sees monotonically increasing distinct source counts across ≥ 3 consecutive hourly windows, with peak ≥ 5 sources and growth ratio ≥ 1.5 per hour.
- **Rationale:** Slow DDoS does not produce traffic spikes — it exhausts server state tables gradually. Monotonic growth in source count separates it from normal fluctuation.

**Sub-task 15.3 — IP hopping:**
- **Algorithm:** Destination fingerprinting + Jaccard clustering.
  1. For each source IP compute its "destination fingerprint": the frozen set of destination IPs it contacts.
  2. Compute pairwise Jaccard similarity between fingerprints of candidate IPs (capped at `candidate_cap` comparisons for O(n²) protection).
  3. IPs with Jaccard ≥ 0.50 are linked; clusters of size ≥ 3 are flagged as potential single actors hopping IPs.

**Expected output:** Tables of detected port scanners (with port count, duration, rate), slow DDoS destinations, and IP hopping clusters.

---

#### Task 4b (Task 16) — Malicious payload identification
**Notebook cells:** 35–38
**Function:** `task16(df, cfg)`

**Requirement:** Analyse payload data for suspicious patterns. Flag anomalous encrypted traffic. Identify C2 beaconing.

**Sub-task 16.1 — Payload pattern matching:**
Scans `sourcePayloadAsUTF` and `destinationPayloadAsUTF` using regex patterns defined in `config.yaml`:

| Pattern | Examples detected |
|---------|------------------|
| `shell_command` | `/bin/sh`, `cmd.exe`, `powershell` |
| `download_backdoor` | `wget`, `curl`, `nc`, `ncat` |
| `sql_injection` | `SELECT … FROM`, `UNION ALL SELECT` |
| `xss` | `<script>`, `javascript:` |
| `scanner_ua` | User-Agents containing `bot`, `nmap`, `masscan` |
| `credential_leak` | `password=`, `secret=` |
| `large_b64_blob` | Base64 strings ≥ 60 chars (possible encoded payloads) |

**Sub-task 16.2 — Anomalous encrypted traffic:**
Flows with `appName` in `{SecureWeb, SSH, IPSec, Authentication}` are isolated. Within this subset, IQR is applied to packet sizes. Encrypted flows with tiny payloads (< 100 bytes) or very short duration (< 1 second) are flagged — these can indicate protocol abuse or tunnelling handshakes.

**Sub-task 16.3 — C2 beaconing:**
- **Signature:** A source IP makes ≥ 5 connections to the same destination with coefficient of variation (CV = std/mean) of inter-arrival times < 0.30 AND average payload < 500 bytes.
- **Rationale:** C2 implants "beacon" at regular intervals to check in with their controller. Low CV means highly regular timing; small payload means the check-in is a heartbeat, not bulk transfer.

**Expected output:** Tables of flows matching each payload pattern, anomalous encrypted flows, and detected beaconing pairs.

---

#### Task 4c (Task 17) — Threat attribution and risk register
**Notebook cells:** 39–40
**Function:** `task17(df, cfg)`

**Requirement:** Categorise each detected security event as Low / Medium / High risk with justification. Generate a concise risk report.

**Risk classification logic:**

| Risk Level | Criteria |
|------------|----------|
| **HIGH** | Multiple confirmed behavioural indicators (e.g., IP confirmed as both port scanner AND C2 beacon AND IP hopper); direct payload evidence of exploitation |
| **MEDIUM** | Statistical outlier with plausible malicious explanation (e.g., sudden spike from previously inactive IP, fan-in event, long-duration encrypted flow) |
| **LOW** | Unusual but likely benign (e.g., consistent communicator that appears in nearly every window — possibly a monitoring tool) |

Each entry in the risk register records: source IP or destination IP, detected indicator(s), risk level, confidence score, and a one-line justification.

**Expected output:** Risk register table printed inline in the notebook.

---

## Generating the Word Report

After running `analysis.ipynb`, run:

```bash
python build_report.py
```

Output: `outputs/report.docx` (open in Word or LibreOffice).

The script reads `outputs/results.json` (written by the last cell of `analysis.ipynb`) and all figures from `outputs/figures/`, then produces a Word document with narrative, all data tables, embedded figures, and a colour-coded risk register.

---

## Output Files Reference

| File | Generated by | Contents |
|------|-------------|----------|
| `outputs/figures/fig_1_2_protocols.png` | Task 1.2 | Bar + pie chart of top-k protocols |
| `outputs/figures/fig_1_3_top10_ips.png` | Task 1.3 | Top-10 source/destination IPs by bytes |
| `outputs/figures/fig_1_4_pkt_size_dist.png` | Task 1.4 | Packet size histogram with mean/median |
| `outputs/figures/fig_1_7_spikes.png` | Task 1.7 | Traffic timeline with spike annotations |
| `outputs/figures/fig_3a_heatmap.png` | Task 3a | Hourly protocol distribution heatmap |
| `outputs/results.json` | analysis.ipynb | All numerical results for all four sections (read by build_report.py) |
| `outputs/report.docx` | build_report.py | Full security analysis report with narrative, all tables and embedded figures |

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: No module named 'pandas'` | venv not activated | Run `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Linux/macOS) |
| `ModuleNotFoundError: No module named 'bitarray'` | Dependencies not installed | Run `pip install -r requirements.txt` inside the activated venv |
| `jupyter: command not found` | jupyter not installed | Run `pip install jupyter jupyterlab` inside the venv |
| `FileNotFoundError: logs/network_analysis_data1.csv` | CSV files missing from `logs/` | Copy all 6 CSV files into the `logs/` folder |
| `MemoryError` or kernel crash during data load | Insufficient RAM | Reduce `data.chunk_size` to `50000` in `config.yaml` |
| Plots don't appear / blank windows | Headless environment | Set `output.show_plots: false` in `config.yaml`; plots are still saved to `outputs/figures/` |
| Kernel restart required | Previous run left state | In Jupyter: **Kernel → Restart Kernel and Run All Cells** |
| `PermissionError` writing to `outputs/` | Folder doesn't exist | The notebook creates it automatically; if it fails, create `outputs/figures/` manually |
| `Port 8888 is already in use` | Another Jupyter instance running | Use `jupyter notebook --port 8889` or kill the other instance |
| Very slow data loading (> 30 min) | Antivirus scanning large files | Temporarily exclude the `logs/` folder from real-time scanning |
