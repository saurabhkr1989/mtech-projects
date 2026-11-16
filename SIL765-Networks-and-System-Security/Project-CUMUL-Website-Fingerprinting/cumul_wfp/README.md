# CUMUL Website Fingerprinting Project
# ====================================
# A reproduction of the CUMUL attack from Panchenko et al., NDSS 2016
# Implemented for Windows with Python 3.8

## Project Structure
```
cumul_wfp/
├── config.py              # Configuration (edit this only)
├── collect/              # Data collection modules
├── preprocess/           # Trace sanitization
├── features/             # CUMUL feature extraction
├── classifier/           # SVM classification
├── evaluate/             # Evaluation harness
├── tests/                # Smoke tests
└── data/                 # Data storage
```

## Quick Start

1. **Setup Environment** (see Phase 0 in coding plan):
   - Install Npcap driver
   - Install Tor Browser Bundle
   - Create Python virtual environment
   - Install dependencies: `pip install -r requirements.txt`

2. **Run Smoke Test**:
   ```
   python -m tests.smoke_test
   ```

3. **Collect Data** (Phase 1):
   ```
   python -m collect.capture
   ```

4. **Extract Features** (Phase 3):
   ```
   python -m features.cumul
   ```

5. **Train Classifier** (Phase 4):
   ```
   python -m classifier.svm_model
   ```

6. **Evaluate** (Phase 5):
   ```
   python -m evaluate.closed_world
   ```

## Configuration

Edit `config.py` to change:
- Target websites
- Number of instances
- SVM parameters
- Feature flags (open-world, longitudinal, demo mode)

## Requirements

- Python 3.8+
- Npcap driver
- Tor Browser Bundle
- See requirements.txt for Python packages

## Authors

- Lt Col Dey Sanjeetkumar (2025JCS2949)
- Lt Col Saurabh Kumar Singh (2025JCS3011)
