# CUMUL Website Fingerprinting — M.Tech Project (SIL765/COL7165)

Website fingerprinting over Tor using the CUMUL (cumulative traffic) feature set, per Panchenko et al. (2016) — `Panchenko2016a.pdf` is the base paper this project implements.

## Variants

- **[cumul_wfp](cumul_wfp)** — the core implementation: Tor circuit-based traffic capture, CUMUL feature extraction, SVM classifier, and evaluation pipeline. `data/raw/` holds the raw `.pcap` captures (one per site visit) used to train and evaluate the classifier; `data/models/` the trained SVM/scaler/label-encoder; `results/` the confusion matrices, cross-validation results, and evaluation reports/dashboards backing the project report's numbers.
- **[youtube_wfp](youtube_wfp)** — a later variant: given a YouTube link in its config, it drives a Tor-based browser to play the video in full across multiple runs, capturing packet traces to train weights on streaming traffic specifically.
- **[twitter_wfp](twitter_wfp)** — a parallel variant for X/Twitter post browsing (private browser window, no Tor), with its own captured traces under `raw/`.

## References

See [references/](references) for the project abstract, mid/end-term reports and presentations, and [All-Details](references/All-Details) for HTML write-ups of the CUMUL workflow, module responsibilities, and classifier internals. [MidTerm-Report-Images](references/MidTerm-Report-Images) holds the midterm report as page scans (no separate midterm PDF was produced).

## Notes

- Portable distributions of `youtube_wfp`/`twitter_wfp` that bundled a Tor Browser, Firefox, and a Python runtime for easy deployment are not included here — only the authored source and captured data, which is what matters for review and reproduction. Each variant's own README (where present) has the original run instructions.
- A Python virtual environment and `__pycache__` build artifacts bundled with an earlier working copy of `cumul_wfp` have been excluded.
- Large files (pcap captures, trained models, images, reports) are tracked via Git LFS.
