# SIL7175 — Biometric Security

M.Tech coursework, IIT Delhi (Semester II).

## Assignments

| # | Topic | Contents |
|---|-------|----------|
| 1 | [Contactless Fingerprint Recognition](Assignment-01-Contactless-Fingerprint-Recognition) | Global minutia topology + loose genetic algorithm matching, per Bontrager et al. See its `references.md` — two of this assignment's raw datasets (~25GB combined) are public research databases not hosted here. |
| 2 | [Multimodal Biometric System](Assignment-02-Multimodal-Biometric-System) | Face + Iris + Offline Signature fusion, SE-AlexNet/WI-AlexNet deep features, SVM verification, 5-fold cross-validation. See its `references.md` — raw CASIA/LFW/IITD/BHSig260 datasets and a disk-cache artifact are not hosted here. |
| 3 | [Fingerprint Biometric Cryptosystem (Fuzzy Vault)](Assignment-03-Fingerprint-Biometric-Cryptosystem-Fuzzy-Vault) | Chaff-free fuzzy vault scheme over FVC2002/FVC2004 fingerprint samples |

## Shared-Datasets

- [contact-based_fingerprints](Shared-Datasets/contact-based_fingerprints) — fingerprint image captures (first/second session) used across this subject's assignments.

## Notes

- Compiled artifacts, disk caches (`__pycache__`, `svm_cache`), and duplicate/backup working copies have been excluded; each assignment folder holds the final submitted source, report, and the data needed to reproduce its results.
- Large third-party research datasets that are not Saurabh's own data, and whose combined size or license terms make re-hosting impractical, are documented (not uploaded) in each assignment's `references.md`.
- Large files (images, trained model weights, PDFs) are tracked via Git LFS.
