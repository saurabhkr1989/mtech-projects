# External datasets and excluded cache artifacts

- **Raw Dataset/** (BHSig260, CASIA-Iris-Distance, IITD Database, lfw) is not hosted here. These are public biometric research databases distributed under their own originating labs' access/redistribution terms, not Saurabh's own data. `src/data/dataset_mapper.py` documents how they're consumed; request access from each database's own distribution page.
- **results/svm_cache/** (~17GB) and the top-level **training weights.zip** (a zip of the same per-user SVM cache) are excluded as disk-cache artifacts, not source or results: `svm_verification.py` regenerates them deterministically from `extracted_features/` on a training run, per the README's note on "joblib disk caching".
- **resources/shape_predictor_68_face_landmarks.dat** (dlib's standard public pretrained landmark model, ~95MB) is not hosted here; run `download_dlib_model.py` to fetch it from dlib's own distribution.

What *is* included: all source code, the report, `extracted_features/` (the intermediate feature vectors needed to reproduce classification without the restricted raw datasets), and `results/` (the two trained model weights `se_alexnet_finetuned.pth`/`wi_alexnet_trained.pth`, ROC curves, and metrics CSVs) that back the report's claims.
