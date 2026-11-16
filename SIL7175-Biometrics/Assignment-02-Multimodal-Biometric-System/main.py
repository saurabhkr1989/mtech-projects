import os
import sys
import numpy as np
import pandas as pd

import torch
import cv2
from tqdm import tqdm
from torchvision import transforms
from sklearn.model_selection import KFold
import concurrent.futures
import threading
import pickle

from src.config import Config
from src.logger import log
from src.data.dataset_mapper import generate_full_mapping

# --- Preprocessing modules ---
from src.preprocessing.face_preprocessor import FacePreprocessor
from src.preprocessing.iris_preprocessor import IrisPreprocessor
from src.preprocessing.signature_preprocessor import SignaturePreprocessor

# --- Feature extraction modules ---
from src.features.texture_extractor import TextureExtractor
from src.features.deep_se_alexnet import SEAlexNet
from src.features.deep_wi_alexnet import AlexNet_N

# --- Classification and fusion ---
from src.classification.svm_verification import SVMVerifier
from src.fusion.fusion_strategies import FeatureFusion, DecisionFusion
from src.evaluation.evaluator import Evaluator


# ============================================================
# Helper: prompt user for yes/no confirmation
# ============================================================
def confirm_action(prompt_message):
    """
    Prompts the user for a Yes/No answer. Returns True for Yes, False for No.
    """
    while True:
        response = input(prompt_message + " [y/N]: ").strip().lower()
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no', '']:
            return False
        print("Please enter 'y' or 'n'.")


# ============================================================
# Helper: collect all image paths from a subject directory
# ============================================================
def collect_images_in_directory(directory_path):
    """
    Returns a sorted list of all image file paths found directly inside
    the given directory. Supports common biometric image formats.
    """
    supported_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')
    all_files = sorted([
        os.path.join(directory_path, fname)
        for fname in os.listdir(directory_path)
        if fname.lower().endswith(supported_extensions)
    ])
    return all_files


# ============================================================
# Helper: persist a feature dictionary (user -> list of vecs) to CSV
# ============================================================
def save_feature_dict_to_csv(feature_dict, output_csv_path):
    """
    Serializes a dictionary mapping Virtual_User_ID -> list_of_vectors to CSV.
    Each row contains the user ID followed by the feature values.
    Assignment requires all extracted features saved in .csv format for submission.
    """
    rows = []
    total_tuples = sum(len(vec_list) for vec_list in feature_dict.values())

    with tqdm(total=total_tuples,
              desc=f"  Writing {os.path.basename(output_csv_path)}",
              unit="row", leave=False, colour='cyan') as pbar:
        for user_id, vector_list in feature_dict.items():
            for feature_vector in vector_list:
                row = {"Virtual_User_ID": user_id}
                row.update({f"feat_{dim_idx}": float(val)
                             for dim_idx, val in enumerate(feature_vector)})
                rows.append(row)
                pbar.update(1)

    if rows:
        pd.DataFrame(rows).to_csv(output_csv_path, index=False)
        log.csv(output_csv_path, len(rows))
    else:
        log.warn(f"No feature data to write for: {os.path.basename(output_csv_path)}")


# ============================================================
# Helper: load a feature dictionary from CSV
# ============================================================
def load_feature_dict_from_csv(csv_path):
    """
    Loads a dictionary mapping Virtual_User_ID -> list_of_vectors from CSV.
    Used to skip Phase 2 extraction if the CSV files already exist on disk.
    """
    if not os.path.exists(csv_path):
        return None

    df = pd.read_csv(csv_path, dtype={'Virtual_User_ID': str})
    feature_cols = sorted([c for c in df.columns if c.startswith('feat_')],
                          key=lambda c: int(c.split('_')[1]))
    feature_dict = {}
    for uid, group in df.groupby('Virtual_User_ID'):
        feature_dict[uid] = list(group[feature_cols].values)

    return feature_dict


# ============================================================
# Phase 1: Dataset Mapping
# ============================================================
def phase1_load_or_create_mapping():
    """
    Ensures the dataset mapping CSV exists.
    Prompts user before regenerating if mapping is missing.
    """
    log.phase("Dataset Mapping (Phase 1)")

    if not os.path.exists(Config.MAPPING_FILE):
        log.warn(f"No existing mapping found at: {Config.MAPPING_FILE}")
        if not confirm_action("Mapping CSV is missing. Generate it now?"):
            log.error("Cannot proceed without dataset mapping. Exiting.")
            sys.exit(1)
        log.info("Generating dataset mapping CSV...")
        generate_full_mapping()
        log.ok(f"Mapping generated → {Config.MAPPING_FILE}")
    else:
        log.ok(f"  [CACHE HIT]  Mapping CSV found.")
        if confirm_action("Do you want to use the cached Mapping CSV? (N to regenerate from scratch)"):
            log.info(f"  Loading from disk: {Config.MAPPING_FILE}")
        else:
            log.info("Regenerating dataset mapping CSV based on your request...")
            generate_full_mapping()
            log.ok(f"Mapping regenerated → {Config.MAPPING_FILE}")

    mapping_df = pd.read_csv(Config.MAPPING_FILE, dtype=str)
    d1_count = len(mapping_df[mapping_df['Dataset'] == 'Dataset_1'])
    d2_count = len(mapping_df[mapping_df['Dataset'] == 'Dataset_2'])
    log.info(f"  Dataset 1: {d1_count} virtual users")
    log.info(f"  Dataset 2: {d2_count} virtual users")
    log.info(f"  Total    : {len(mapping_df)} virtual users")
    log.phase_done("Dataset Mapping")
    return mapping_df


# ============================================================
# Phase 2 Multiprocessing Setup (CPU Worker for preprocessing)
# ============================================================
w_face_prep   = None
w_iris_prep   = None
w_sig_prep    = None
w_texture_ext = None

def _init_cpu_worker():
    global w_face_prep, w_iris_prep, w_sig_prep, w_texture_ext
    w_face_prep   = FacePreprocessor()
    w_iris_prep   = IrisPreprocessor()
    w_sig_prep    = SignaturePreprocessor()
    w_texture_ext = TextureExtractor()

def _cpu_worker(args):
    loop_idx, virtual_uid, actual_n, face_image_paths, iris_image_paths, sig_image_paths = args
    u_face_ulbp, u_iris_ulbp = [], []
    u_face_raw, u_iris_raw, u_sig_raw = [], [], []
    user_tuple_errors = 0

    for tuple_idx in range(actual_n):
        face_img_path = face_image_paths[tuple_idx]
        iris_img_path = iris_image_paths[tuple_idx]
        sig_img_path  = sig_image_paths[tuple_idx]

        # Face LBP texture
        try:
            rois = w_face_prep.extract_rois(face_img_path)
            u_face_ulbp.append(w_texture_ext.process_face_rois(rois))
        except Exception:
            user_tuple_errors += 1

        # Face raw (for deep features on GPU)
        try:
            raw_face_bgr = cv2.imread(face_img_path)
            gray = cv2.cvtColor(raw_face_bgr, cv2.COLOR_BGR2GRAY)
            dlib_faces = w_face_prep.dlib_detector(gray, 1)
            if len(dlib_faces) > 0:
                rect = dlib_faces[0]
                x1 = max(0, rect.left())
                y1 = max(0, rect.top())
                x2 = min(raw_face_bgr.shape[1], rect.right())
                y2 = min(raw_face_bgr.shape[0], rect.bottom())
                cropped = raw_face_bgr[y1:y2, x1:x2]
                if cropped.size > 0:
                    raw_face_bgr = cropped
            raw_face_rgb = cv2.cvtColor(raw_face_bgr, cv2.COLOR_BGR2RGB)
            raw_face_rgb = cv2.resize(raw_face_rgb, (224, 224))
            u_face_raw.append(raw_face_rgb)
        except Exception:
            user_tuple_errors += 1

        # Iris LBP texture
        try:
            strips = w_iris_prep.extract_strips(iris_img_path)
            u_iris_ulbp.append(w_texture_ext.process_iris_strips(strips))
        except Exception:
            user_tuple_errors += 1

        # Iris raw (for deep features on GPU)
        try:
            raw_iris_bgr = cv2.imread(iris_img_path)
            gray = cv2.cvtColor(raw_iris_bgr, cv2.COLOR_BGR2GRAY)
            pupil, iris = w_iris_prep.find_pupil_and_iris(gray)
            ix, iy, ir = iris
            x1 = max(0, ix - ir)
            y1 = max(0, iy - ir)
            x2 = min(raw_iris_bgr.shape[1], ix + ir)
            y2 = min(raw_iris_bgr.shape[0], iy + ir)
            cropped_iris = raw_iris_bgr[y1:y2, x1:x2]
            if cropped_iris.size > 0:
                raw_iris_bgr = cropped_iris
            raw_iris_rgb = cv2.cvtColor(raw_iris_bgr, cv2.COLOR_BGR2RGB)
            raw_iris_rgb = cv2.resize(raw_iris_rgb, (224, 224))
            u_iris_raw.append(raw_iris_rgb)
        except Exception:
            user_tuple_errors += 1

        # Signature binary image
        try:
            bin_sig = w_sig_prep.process_signature(sig_img_path)
            u_sig_raw.append(bin_sig)
        except Exception:
            user_tuple_errors += 1

    return loop_idx, virtual_uid, actual_n, user_tuple_errors, u_face_ulbp, u_face_raw, u_iris_ulbp, u_iris_raw, u_sig_raw


# ============================================================
# Phase 2: Feature Extraction over all N image tuples per user
# ============================================================
def phase2_extract_all_features(mapping_df, face_prep, iris_prep, sig_prep,
                                 texture_ext, se_alexnet_model, wi_alexnet_model,
                                 transform_for_se_alexnet, device, dataset_label):
    """
    Iterates over every virtual user defined in the mapping CSV.
    For each user, collects all available image tuples up to Min_Samples_N.

    Returns a dict of dicts: { "face_ulbp": {user_id: [vec, vec, ...]}, ... }

    CPU-bound tasks are parallelised via ProcessPoolExecutor (4 workers).
    GPU-bound tasks are run sequentially on the main thread.
    """
    log.phase(f"Feature Extraction — {dataset_label} (Phase 2)")
    log.info(f"Processing {len(mapping_df)} virtual users across 5 modalities...")
    log.separator()

    all_face_ulbp = {}
    all_iris_ulbp = {}
    all_face_deep = {}
    all_iris_deep = {}
    all_sig_deep  = {}

    total_user_count       = len(mapping_df)
    users_with_errors      = 0
    total_tuples_extracted = 0

    worker_args = []
    for loop_idx, (_, user_row) in enumerate(mapping_df.iterrows(), start=1):
        virtual_uid = user_row['Virtual_User_ID']
        dataset_tag = user_row['Dataset']
        face_sid    = str(user_row['Face_Source_ID'])
        iris_sid    = str(user_row['Iris_Source_ID'])
        sig_sid     = str(user_row['Signature_Source_ID'])
        min_samples = int(user_row.get('Min_Samples_N', 1))

        if dataset_tag == "Dataset_1":
            face_dir = os.path.join(Config.CASIA_DIR,         face_sid)
            iris_dir = os.path.join(Config.CASIA_DIR,         iris_sid)
            sig_dir  = os.path.join(Config.BHSIG_BENGALI_DIR, sig_sid)
        else:
            face_dir = os.path.join(Config.LFW_DIR,           face_sid)
            iris_dir = os.path.join(Config.IITD_DIR,          iris_sid)
            sig_dir  = os.path.join(Config.BHSIG_HINDI_DIR,   sig_sid)

        face_image_paths = collect_images_in_directory(face_dir) if os.path.isdir(face_dir) else []
        iris_image_paths = collect_images_in_directory(iris_dir) if os.path.isdir(iris_dir) else []
        sig_image_paths  = collect_images_in_directory(sig_dir)  if os.path.isdir(sig_dir)  else []

        actual_n = min(len(face_image_paths), len(iris_image_paths), len(sig_image_paths), min_samples)

        if actual_n == 0:
            log.skip(f"{virtual_uid} — no usable image tuples")
            users_with_errors += 1
            continue

        worker_args.append((loop_idx, virtual_uid, actual_n, face_image_paths, iris_image_paths, sig_image_paths))
        all_face_ulbp.setdefault(virtual_uid, [])
        all_iris_ulbp.setdefault(virtual_uid, [])
        all_face_deep.setdefault(virtual_uid, [])
        all_iris_deep.setdefault(virtual_uid, [])
        all_sig_deep.setdefault(virtual_uid,  [])

    log.info(f"  Dispatching {len(worker_args)} users to 4 CPU workers for parallel preprocessing...")

    # CPU Heavy: Preprocessing + ULBP in 4 parallel subprocesses
    with concurrent.futures.ProcessPoolExecutor(max_workers=4, initializer=_init_cpu_worker) as executor:
        futures = {executor.submit(_cpu_worker, arg): arg for arg in worker_args}

        for idx, future in enumerate(tqdm(concurrent.futures.as_completed(futures),
                                          total=len(worker_args),
                                          desc="  Preprocessing + ULBP",
                                          colour='cyan'), start=1):
            result = future.result()
            loop_idx, virtual_uid, actual_n, user_tuple_errors, u_face_ulbp, u_face_raw, u_iris_ulbp, u_iris_raw, u_sig_raw = result

            all_face_ulbp[virtual_uid].extend(u_face_ulbp)
            all_iris_ulbp[virtual_uid].extend(u_iris_ulbp)

            # GPU: Deep feature extraction (sequential — CUDA context cannot be shared)
            for raw_face_rgb in u_face_raw:
                try:
                    face_tensor      = transform_for_se_alexnet(raw_face_rgb).unsqueeze(0).to(device)
                    face_deep_vector = se_alexnet_model.extract_features(face_tensor).cpu().detach().numpy().flatten()
                    all_face_deep[virtual_uid].append(face_deep_vector)
                except Exception:
                    user_tuple_errors += 1

            for raw_iris_rgb in u_iris_raw:
                try:
                    iris_tensor      = transform_for_se_alexnet(raw_iris_rgb).unsqueeze(0).to(device)
                    iris_deep_vector = se_alexnet_model.extract_features(iris_tensor).cpu().detach().numpy().flatten()
                    all_iris_deep[virtual_uid].append(iris_deep_vector)
                except Exception:
                    user_tuple_errors += 1

            for bin_sig in u_sig_raw:
                try:
                    sig_tensor      = torch.tensor(bin_sig, dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(device)
                    sig_deep_vector = wi_alexnet_model.extract_features(sig_tensor).cpu().detach().numpy().flatten()
                    all_sig_deep[virtual_uid].append(sig_deep_vector)
                except Exception:
                    user_tuple_errors += 1

            total_tuples_extracted += actual_n

    log.separator()
    log.ok(f"Feature extraction complete: {total_tuples_extracted} total image tuples processed")
    if users_with_errors > 0:
        log.warn(f"{users_with_errors} user(s) skipped due to missing image directories")
    log.phase_done(f"Feature Extraction — {dataset_label}")

    return {
        "face_ulbp": all_face_ulbp,
        "iris_ulbp": all_iris_ulbp,
        "face_deep": all_face_deep,
        "iris_deep": all_iris_deep,
        "sig_deep":  all_sig_deep,
    }


# ============================================================
# Phase 3 Evaluation: Picklable subprocess worker
#
#   - For each enrolled user U: load their trained SVM from disk
#   - Score probe samples from every user against U's SVM
#   - Decision fusion: majority vote (>=3 of 5 classifiers)
# ============================================================
def _eval_worker_batch(args):
    """
    Picklable worker: evaluates a batch of enrolled users against probe samples.
    Loads SVM models from disk.

    Decision fusion: majority vote of 5 unimodal SVMs.
    y_true = 1 when probe genuinely belongs to the SVM owner.

    Args:
        args: tuple of (enroll_uid_batch, probe_true_uids, X_dict,
                        svm_cache_dir, dataset_label, fold_num)
    Returns:
        dict mapping result_key -> list of {y_true, y_prob} dicts
    """
    enroll_uid_batch, probe_true_uids, X_dict, svm_cache_dir, dataset_label, fold_num = args

    from src.classification.svm_verification import SVMVerifier
    import numpy as np

    n_samples   = len(probe_true_uids)
    modalities  = ["face_ulbp", "iris_ulbp", "face_deep", "iris_deep", "sig_deep", "feature_fused"]
    result_keys = ["Face_ULBP", "Iris_ULBP", "Face_Deep", "Iris_Deep", "Sig_Deep",
                   "Feature_Fusion", "Decision_Fusion"]
    chunk = {k: [] for k in result_keys}

    def _zeros():
        return np.zeros(n_samples, dtype=float)

    for enroll_uid in enroll_uid_batch:
        probs = {}
        for mk in modalities:
            modality_name_for_cache = f"{mk}_{dataset_label}"
            verifier = SVMVerifier.load_from_cache(
                svm_cache_dir, dataset_label, fold_num, modality_name_for_cache, enroll_uid
            )
            if verifier is not None:
                X = X_dict.get(mk)
                if X is not None and len(X) > 0:
                    _, p = verifier.verify_batch(X)
                    probs[mk] = p
                else:
                    probs[mk] = _zeros()
            else:
                probs[mk] = _zeros()

        # Assignment §5.2: Decision Fusion = majority vote of 5 unimodal binary decisions
        unimodal_keys = ["face_ulbp", "iris_ulbp", "face_deep", "iris_deep", "sig_deep"]
        vote_sum = sum((probs[mk] > 0.5).astype(float) for mk in unimodal_keys)
        # D_final = 1 if vote_sum >= 3 (per assignment Eq. 5)
        decision_fusion_prob = (vote_sum >= 3).astype(float)

        # y_true = 1 if this probe genuinely belongs to this enrolled user
        true_labels = [1 if enroll_uid == t else 0 for t in probe_true_uids]

        for i in range(n_samples):
            t = true_labels[i]
            chunk["Face_ULBP"].append({"y_true": t, "y_prob": float(probs["face_ulbp"][i])})
            chunk["Iris_ULBP"].append({"y_true": t, "y_prob": float(probs["iris_ulbp"][i])})
            chunk["Face_Deep"].append({"y_true": t, "y_prob": float(probs["face_deep"][i])})
            chunk["Iris_Deep"].append({"y_true": t, "y_prob": float(probs["iris_deep"][i])})
            chunk["Sig_Deep"].append({"y_true": t,  "y_prob": float(probs["sig_deep"][i])})
            chunk["Feature_Fusion"].append({"y_true": t, "y_prob": float(probs["feature_fused"][i])})
            chunk["Decision_Fusion"].append({"y_true": t, "y_prob": float(decision_fusion_prob[i])})

    return chunk


def phase3_run_cross_validation(feature_bundle, evaluator, dataset_label, force_recompute=False):
    """
    Runs the 5-fold cross-validation loop.

    1. Assemble N tuples per user based on min samples across modalities.
    2. Split these N tuples across 5 folds.
    3. Train per-user SVMs per fold using balanced class weights and a 1:3 
       genuine:impostor ratio to handle class imbalance.
    4. Evaluate test tuples against each SVM.
    5. Perform Decision Fusion (majority vote).
    """
    log.phase(f"5-Fold Cross-Validation — {dataset_label} (Phase 3)")

    face_ulbp_data = feature_bundle["face_ulbp"]
    iris_ulbp_data = feature_bundle["iris_ulbp"]
    face_deep_data = feature_bundle["face_deep"]
    iris_deep_data = feature_bundle["iris_deep"]
    sig_deep_data  = feature_bundle["sig_deep"]

    feature_fusion_module = FeatureFusion()

    # --------------------------------------------------------
    # STEP 1: Build tuples per user
    # N = min samples across all modalities
    # --------------------------------------------------------
    log.info("  Assembling tuples per user (N = min samples across modalities)...")
    user_tuples = {}   # uid -> list of (fu, iu, fd, id_, sd, fused_vec)

    eligible_user_ids = []
    for uid in face_ulbp_data:
        if (uid not in iris_ulbp_data or uid not in face_deep_data
                or uid not in iris_deep_data or uid not in sig_deep_data):
            continue
        n_samples = min(
            len(face_ulbp_data[uid]), len(iris_ulbp_data[uid]),
            len(face_deep_data[uid]),  len(iris_deep_data[uid]),
            len(sig_deep_data[uid])
        )
        if n_samples < Config.CV_FOLDS:
            # Need at least 5 samples to have one in each fold
            continue
        tuples = []
        for s in range(n_samples):
            fv_fu = face_ulbp_data[uid][s]
            fv_iu = iris_ulbp_data[uid][s]
            fv_fd = face_deep_data[uid][s]
            fv_id = iris_deep_data[uid][s]
            fv_sd = sig_deep_data[uid][s]
            fused = feature_fusion_module.concatenate_features(
                face_ulbp=fv_fu, face_deep=fv_fd,
                iris_ulbp=fv_iu, iris_deep=fv_id,
                sig_deep=fv_sd
            )
            tuples.append((fv_fu, fv_iu, fv_fd, fv_id, fv_sd, fused))
        user_tuples[uid] = tuples
        eligible_user_ids.append(uid)

    if len(eligible_user_ids) == 0:
        log.error("No eligible users after chimeric tuple assembly — aborting CV.")
        return

    log.info(f"  Eligible users: {len(eligible_user_ids)} | "
             f"Avg tuples/user: {np.mean([len(user_tuples[u]) for u in eligible_user_ids]):.1f}")
    log.separator()

    svm_cache_dir = os.path.join(Config.RESULTS_DIR, "svm_cache")
    rng = np.random.default_rng(42)

    # --------------------------------------------------------
    # STEP 2: 5-fold CV on tuples per-user
    # Each user's tuples are independently partitioned into folds.
    # --------------------------------------------------------
    # Pre-compute fold assignments per user
    user_fold_indices = {}   # uid -> array of fold_id (0..4) per tuple index
    for uid in eligible_user_ids:
        n = len(user_tuples[uid])
        fold_ids = np.zeros(n, dtype=int)
        # Spread tuples as evenly as possible across 5 folds
        shuffled_idx = rng.permutation(n)
        for rank, idx in enumerate(shuffled_idx):
            fold_ids[idx] = rank % Config.CV_FOLDS
        user_fold_indices[uid] = fold_ids

    # Ask the user only ONCE per dataset about using Phase 3 fold results cache
    use_phase3_cache = None

    for fold_number in range(1, Config.CV_FOLDS + 1):
        test_fold_id = fold_number - 1   # 0-indexed fold used as test

        log.step(f"Fold {fold_number}/{Config.CV_FOLDS}  |  "
                 f"All {len(eligible_user_ids)} users — 4/5 tuples train, 1/5 test")

        # Check fold result cache first
        fold_results_cache_path = os.path.join(
            svm_cache_dir, f"fold_results_{dataset_label}_fold{fold_number:02d}.pkl"
        )
        if not force_recompute:
            if os.path.exists(fold_results_cache_path):
                log.ok(f"  [CACHE HIT] Fold {fold_number} already evaluated.")
                if use_phase3_cache is None:
                    use_phase3_cache = confirm_action(f"Do you want to use the cached results for Phase 3 folds if available? (Say N to re-evaluate)")
                
                if use_phase3_cache:
                    with open(fold_results_cache_path, "rb") as f:
                        fold_test_results = pickle.load(f)
                    evaluator.evaluate_cross_val_fold(fold_number, dataset_label, fold_test_results)
                    log.ok(f"  Fold {fold_number}/{Config.CV_FOLDS} complete (from cache)")
                    continue
                else:
                    log.info(f"  Re-evaluating Fold {fold_number} based on user request...")
            else:
                if use_phase3_cache is True:
                    log.warn(f"  [CACHE MISS] Fold {fold_number} missing. Evaluating automatically...")
                elif use_phase3_cache is None:
                    use_phase3_cache = False

        # --------------------------------------------------------
        # STEP 3: Build per-user train/test splits for this fold
        # --------------------------------------------------------
        train_samples = {}
        test_samples  = {}
        for uid in eligible_user_ids:
            fold_ids = user_fold_indices[uid]
            tuples   = user_tuples[uid]
            train_samples[uid] = [t for i, t in enumerate(tuples) if fold_ids[i] != test_fold_id]
            test_samples[uid]  = [t for i, t in enumerate(tuples) if fold_ids[i] == test_fold_id]

        n_train_total = sum(len(v) for v in train_samples.values())
        n_test_total  = sum(len(v) for v in test_samples.values())
        log.info(f"  train tuples: {n_train_total} | test tuples: {n_test_total}")

        # --------------------------------------------------------
        # STEP 4: Train/Load per-user SVMs with sampled impostors
        # Positive = user's train tuples
        # Negative = randomly sampled other users' tuples at 1:3 ratio
        # --------------------------------------------------------
        IMPOSTOR_RATIO = 3   # 1 genuine sample → 3 impostor samples

        modality_specs = [
            ("face_ulbp",     0),   # index into chimeric tuple
            ("iris_ulbp",     1),
            ("face_deep",     2),
            ("iris_deep",     3),
            ("sig_deep",      4),
            ("feature_fused", 5),
        ]

        log.info("  Training/Loading per-user SVMs (cached, sampled impostors 1:3):")

        svm_cache = {}   # (uid, modality_key) -> SVMVerifier

        for modality_key, feat_idx in modality_specs:
            modality_name_for_cache = f"{modality_key}_{dataset_label}"

            def _train_or_load_sv(target_uid,
                                  _mk=modality_key, _fi=feat_idx,
                                  _mnfc=modality_name_for_cache,
                                  _fold=fold_number):
                """Cache-aware training with sampled impostors at 1:3 ratio."""
                # Try disk cache first
                if not force_recompute:
                    cached = SVMVerifier.load_from_cache(
                        svm_cache_dir, dataset_label, _fold, _mnfc, target_uid
                    )
                    if cached is not None:
                        return target_uid, cached, "loaded"

                # Build positive samples: all train tuples for this user
                pos_feats = [t[_fi] for t in train_samples[target_uid]]
                n_pos = len(pos_feats)
                if n_pos == 0:
                    return target_uid, None, "failed"

                # Build impostor pool: all train tuples from OTHER users
                all_impostor_feats = []
                for other_uid, other_tuples in train_samples.items():
                    if other_uid == target_uid:
                        continue
                    all_impostor_feats.extend(t[_fi] for t in other_tuples)

                # Sample negatives at 1:3 ratio
                n_neg_target = min(n_pos * IMPOSTOR_RATIO, len(all_impostor_feats))
                if n_neg_target == 0:
                    return target_uid, None, "failed"

                rng_local = np.random.default_rng(hash(target_uid) % (2**31))
                neg_indices = rng_local.choice(len(all_impostor_feats), size=n_neg_target, replace=False)
                neg_feats   = [all_impostor_feats[i] for i in neg_indices]

                flat_feats  = pos_feats + neg_feats
                flat_labels = [target_uid] * n_pos + ["impostor"] * n_neg_target

                # Train binary SVM with balanced class weights
                verifier = SVMVerifier(user_id=target_uid, modality_name=_mnfc)
                success  = verifier.train_user_model(flat_feats, flat_labels)
                if success:
                    verifier.save_to_cache(svm_cache_dir, dataset_label, _fold)
                    return target_uid, verifier, "trained"
                return target_uid, None, "failed"

            trained_count = loaded_count = failed_count = 0

            with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
                results = list(tqdm(
                    executor.map(_train_or_load_sv, eligible_user_ids),
                    total=len(eligible_user_ids),
                    desc=f"    SVM [{modality_key:15s}]",
                    leave=False, colour='magenta'
                ))

            for uid, verifier, status in results:
                if status == "loaded":
                    svm_cache[(uid, modality_key)] = verifier
                    loaded_count += 1
                elif status == "trained":
                    svm_cache[(uid, modality_key)] = verifier
                    trained_count += 1
                else:
                    failed_count += 1

            cache_msg = (f"loaded: {loaded_count}" if loaded_count > 0
                         else f"trained: {trained_count}")
            log.info(f"    SVM [{modality_key:15s}] {cache_msg}  |  failed: {failed_count}")

        # --------------------------------------------------------
        # STEP 5: Evaluation — Score test tuples per enrolled user
        # Ratio: 1:3 (genuine:impostor) evaluating subset to balance metrics
        # --------------------------------------------------------
        EVAL_IMPOSTOR_RATIO = 3

        log.info("  Evaluating: per-enrolled-user scoring with 1:3 genuine:impostor sampling...")

        fold_test_results = {
            "Face_ULBP": [], "Iris_ULBP": [], "Face_Deep": [],
            "Iris_Deep": [], "Sig_Deep":  [], "Feature_Fusion": [], "Decision_Fusion": [],
        }

        # ---- Inner worker: score one enrolled user's SVMs against their probes ----
        def _score_enrolled_user(enrolled_uid):
            """
            Scores one enrolled user's SVMs against their genuine + sampled impostor probes.
            All inputs (svm_cache, test_samples, eligible_user_ids) captured from enclosing scope.
            Returns a list of (y_true, probs_dict) rows, or empty list if nothing to score.
            """
            svms = {mk: svm_cache.get((enrolled_uid, mk)) for mk, _ in modality_specs}

            genuine_tuples = test_samples.get(enrolled_uid, [])

            all_other_test = [
                t
                for other_uid in eligible_user_ids
                if other_uid != enrolled_uid
                for t in test_samples.get(other_uid, [])
            ]

            n_genuine  = len(genuine_tuples)
            n_imp_need = min(n_genuine * EVAL_IMPOSTOR_RATIO, len(all_other_test))

            if n_genuine == 0 or n_imp_need == 0:
                return []

            rng_eval = np.random.default_rng(hash(enrolled_uid) % (2**31) + fold_number)
            selected_imp_idx = rng_eval.choice(len(all_other_test), size=n_imp_need, replace=False)
            impostor_tuples  = [all_other_test[i] for i in selected_imp_idx]

            # Build feature arrays
            all_probe_tuples = [(t, 1) for t in genuine_tuples] + [(t, 0) for t in impostor_tuples]
            probe_X = {mk: [] for mk, _ in modality_specs}
            probe_y = []

            for (tpl, label) in all_probe_tuples:
                probe_X["face_ulbp"].append(tpl[0])
                probe_X["iris_ulbp"].append(tpl[1])
                probe_X["face_deep"].append(tpl[2])
                probe_X["iris_deep"].append(tpl[3])
                probe_X["sig_deep"].append(tpl[4])
                probe_X["feature_fused"].append(tpl[5])
                probe_y.append(label)

            if len(probe_y) == 0:
                return []

            for mk in probe_X:
                probe_X[mk] = np.array(probe_X[mk])

            # Run verify_batch for each modality
            scores = {}
            decisions = {}
            for modality_key, _ in modality_specs:
                svm = svms.get(modality_key)
                if svm is not None and len(probe_X[modality_key]) > 0:
                    d, s = svm.verify_batch(probe_X[modality_key])
                    scores[modality_key] = s
                    decisions[modality_key] = d
                else:
                    scores[modality_key] = np.zeros(len(probe_y), dtype=float)
                    decisions[modality_key] = np.zeros(len(probe_y), dtype=int)

            # -------------------------------------------------------------------------
            # Decision Fusion - Soft Probability Averaging
            # -------------------------------------------------------------------------
            # Averaging probability scores yields a continuous value for proper ROC plotting.
            unimodal_vote_keys = ["face_ulbp", "iris_ulbp", "face_deep", "iris_deep", "sig_deep"]
            
            # Hard prediction is still majority vote (for optimal Accuracy at default 0.5 threshold)
            vote_sum = sum(decisions[mk] for mk in unimodal_vote_keys)
            decision_fusion_pred = (vote_sum >= 3).astype(int)
            
            # Soft prediction is the average of the raw confidence scores
            prob_sum = sum(scores[mk] for mk in unimodal_vote_keys)
            decision_fusion_score = prob_sum / len(unimodal_vote_keys)

            rows = []
            for i, y in enumerate(probe_y):
                rows.append((y, {
                    "Face_ULBP":       {"score": float(scores["face_ulbp"][i]), "pred": int(decisions["face_ulbp"][i])},
                    "Iris_ULBP":       {"score": float(scores["iris_ulbp"][i]), "pred": int(decisions["iris_ulbp"][i])},
                    "Face_Deep":       {"score": float(scores["face_deep"][i]), "pred": int(decisions["face_deep"][i])},
                    "Iris_Deep":       {"score": float(scores["iris_deep"][i]), "pred": int(decisions["iris_deep"][i])},
                    "Sig_Deep":        {"score": float(scores["sig_deep"][i]),  "pred": int(decisions["sig_deep"][i])},
                    "Feature_Fusion":  {"score": float(scores["feature_fused"][i]), "pred": int(decisions["feature_fused"][i])},
                    "Decision_Fusion": {"score": float(decision_fusion_score[i]), "pred": int(decision_fusion_pred[i])},
                }))
            return rows

        # ---- Parallel evaluation: all enrolled users scored concurrently ----
        n_eval_workers = min(os.cpu_count() or 4, len(eligible_user_ids))
        log.info(f"  Parallel scoring: {len(eligible_user_ids)} enrolled users × "
                 f"{n_eval_workers} threads...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_eval_workers) as eval_exec:
            eval_futures = {eval_exec.submit(_score_enrolled_user, uid): uid
                            for uid in eligible_user_ids}

            for future in tqdm(
                concurrent.futures.as_completed(eval_futures),
                total=len(eligible_user_ids),
                desc=f"  Fold {fold_number} — scoring",
                leave=False, colour='cyan'
            ):
                user_rows = future.result()
                for y, p_dict in user_rows:
                    fold_test_results["Face_ULBP"].append({"y_true": y, "y_prob": p_dict["Face_ULBP"]["score"], "y_pred": p_dict["Face_ULBP"]["pred"]})
                    fold_test_results["Iris_ULBP"].append({"y_true": y, "y_prob": p_dict["Iris_ULBP"]["score"], "y_pred": p_dict["Iris_ULBP"]["pred"]})
                    fold_test_results["Face_Deep"].append({"y_true": y, "y_prob": p_dict["Face_Deep"]["score"], "y_pred": p_dict["Face_Deep"]["pred"]})
                    fold_test_results["Iris_Deep"].append({"y_true": y, "y_prob": p_dict["Iris_Deep"]["score"], "y_pred": p_dict["Iris_Deep"]["pred"]})
                    fold_test_results["Sig_Deep"].append({"y_true": y,  "y_prob": p_dict["Sig_Deep"]["score"], "y_pred": p_dict["Sig_Deep"]["pred"]})
                    fold_test_results["Feature_Fusion"].append({"y_true": y, "y_prob": p_dict["Feature_Fusion"]["score"], "y_pred": p_dict["Feature_Fusion"]["pred"]})
                    fold_test_results["Decision_Fusion"].append({"y_true": y, "y_prob": p_dict["Decision_Fusion"]["score"], "y_pred": p_dict["Decision_Fusion"]["pred"]})

        total_pairs = len(fold_test_results["Face_ULBP"])
        genuine_cnt  = sum(1 for e in fold_test_results["Face_ULBP"] if e["y_true"] == 1)
        impostor_cnt = total_pairs - genuine_cnt
        log.info(f"  Fold {fold_number} — pairs: {total_pairs} "
                 f"(genuine: {genuine_cnt}, impostor: {impostor_cnt})")

        # Cache fold results to disk so re-runs skip this fold entirely
        with open(fold_results_cache_path, "wb") as f:
            pickle.dump(fold_test_results, f)
        log.ok(f"  Fold {fold_number} results cached to disk.")

        evaluator.evaluate_cross_val_fold(fold_number, dataset_label, fold_test_results)
        log.ok(f"  Fold {fold_number}/{Config.CV_FOLDS} complete")


    log.info("All folds done. Computing final averaged metrics...")
    evaluator.finalize_results()
    log.phase_done(f"5-Fold Cross-Validation — {dataset_label}")


# ============================================================
# Entry point
# ============================================================
def main():
    print()
    print("=" * 60)
    print("  Multimodal Biometric Recognition System")
    print("  Assignment 2  |  SIL775/7175 Biometric Security")
    print("=" * 60)
    print()

    Config.setup_directories()
    log.ok("Output directories initialised")
    log.info(f"  Features : {Config.FEATURES_DIR}")
    log.info(f"  Results  : {Config.RESULTS_DIR}")
    log.info(f"  Visuals  : {Config.VISUALS_DIR}")

    # -----------------------------------------------------------
    # Phase 1: Dataset mapping (skipped if CSV exists)
    # -----------------------------------------------------------
    full_mapping_df = phase1_load_or_create_mapping()

    face_preprocessor = iris_preprocessor = signature_preprocessor = None
    texture_feature_ext = se_alexnet = wi_alexnet = se_transform = None
    compute_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.model(f"Compute device: {compute_device}")
    evaluator = Evaluator()
    log.ok("Evaluator ready")

    # -----------------------------------------------------------
    # Phases 2 + 3: Feature extraction and CV — run per dataset
    # -----------------------------------------------------------
    for dataset_identifier in ["Dataset_1", "Dataset_2"]:
        subset_df = full_mapping_df[full_mapping_df['Dataset'] == dataset_identifier].copy()
        log.info(f"\n{'=' * 50}")
        log.info(f"  Processing {dataset_identifier} ({len(subset_df)} virtual users)")
        log.info(f"{'=' * 50}")

        if subset_df.empty:
            log.skip(f"{dataset_identifier} — no records in mapping file. Skipping.")
            continue

        csv_specs = [
            ("face_ulbp", f"{dataset_identifier}_face_ulbp_features.csv"),
            ("iris_ulbp", f"{dataset_identifier}_iris_ulbp_features.csv"),
            ("face_deep", f"{dataset_identifier}_face_deep_features.csv"),
            ("iris_deep", f"{dataset_identifier}_iris_deep_features.csv"),
            ("sig_deep",  f"{dataset_identifier}_sig_deep_features.csv"),
        ]
        all_csvs_exist = all(
            os.path.exists(os.path.join(Config.FEATURES_DIR, spec[1])) for spec in csv_specs
        )

        feature_bundle = {}
        use_cache = False

        if all_csvs_exist:
            # ---- PHASE 2 CACHE HIT: Ask user ----
            log.warn(f"  [CACHE FOUND] Pre-extracted feature CSVs exist for {dataset_identifier}.")
            use_cache = confirm_action(f"Do you want to use the cached features for {dataset_identifier}? (Say N to extract new features)")
            
            if use_cache:
                log.info(f"  All 5 feature CSVs found. Loading in parallel...")

                def load_single_csv(spec):
                    modality_key, csv_name = spec
                    csv_path = os.path.join(Config.FEATURES_DIR, csv_name)
                    data = load_feature_dict_from_csv(csv_path)
                    log.info(f"  Loaded {csv_name}  ({sum(len(v) for v in data.values())} vectors)")
                    return modality_key, data

                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    for modality_key, data in executor.map(load_single_csv, csv_specs):
                        feature_bundle[modality_key] = data

                log.ok(f"  All features loaded from disk for {dataset_identifier}. Phase 2 skipped.")
            else:
                log.info(f"  Discarding cached features and forcing re-extraction...")

        if not use_cache or not all_csvs_exist:
            # ---- PHASE 2 CACHE MISS OR USER REJECT: ask user, then extract ----
            missing_csvs = [spec[1] for spec in csv_specs
                            if not os.path.exists(os.path.join(Config.FEATURES_DIR, spec[1]))]
            if missing_csvs:
                log.warn(f"  Missing feature CSVs for {dataset_identifier}: {missing_csvs}")

            if missing_csvs and not confirm_action(
                f"Feature CSVs for {dataset_identifier} are missing. Run extraction now? (~4 min)"
            ):
                log.warn(f"Skipping {dataset_identifier} — extraction declined.")
                continue

            # Lazy-init models only once when actually needed
            if se_alexnet is None:
                log.step("Initialising Pipeline Modules for Feature Extraction")
                face_preprocessor      = FacePreprocessor();      log.ok("FacePreprocessor ready")
                iris_preprocessor      = IrisPreprocessor();      log.ok("IrisPreprocessor ready")
                signature_preprocessor = SignaturePreprocessor(); log.ok("SignaturePreprocessor ready")
                texture_feature_ext    = TextureExtractor();      log.ok("TextureExtractor ready")

                se_weights = os.path.join(Config.RESULTS_DIR, "se_alexnet_finetuned.pth")
                if os.path.exists(se_weights):
                    se_alexnet = SEAlexNet(pretrained=False).to(compute_device)
                    ckpt = torch.load(se_weights, map_location=compute_device, weights_only=False)
                    ckpt.pop("classifier.6.weight", None); ckpt.pop("classifier.6.bias", None)
                    missing, _ = se_alexnet.load_state_dict(ckpt, strict=False)
                    log.model(f"SE-AlexNet: fine-tuned weights loaded ({len(missing)} head keys excluded)")
                else:
                    se_alexnet = SEAlexNet(pretrained=True).to(compute_device)
                    log.warn("SE-AlexNet: using ImageNet pretrained weights (not fine-tuned).")

                wi_weights = os.path.join(Config.RESULTS_DIR, "wi_alexnet_trained.pth")
                if os.path.exists(wi_weights):
                    wi_alexnet = AlexNet_N().to(compute_device)
                    ckpt = torch.load(wi_weights, map_location=compute_device, weights_only=False)
                    ckpt.pop("classifier.8.weight", None); ckpt.pop("classifier.8.bias", None)
                    missing, _ = wi_alexnet.load_state_dict(ckpt, strict=False)
                    log.model(f"AlexNet_N (WI): trained weights loaded ({len(missing)} head keys excluded)")
                else:
                    wi_alexnet = AlexNet_N().to(compute_device)
                    log.warn("AlexNet_N (WI): using random weights.")

                se_transform = transforms.Compose([
                    transforms.ToTensor(),
                    transforms.Resize((224, 224), antialias=True),
                ])

            feature_bundle = phase2_extract_all_features(
                mapping_df               = subset_df,
                face_prep                = face_preprocessor,
                iris_prep                = iris_preprocessor,
                sig_prep                 = signature_preprocessor,
                texture_ext              = texture_feature_ext,
                se_alexnet_model         = se_alexnet,
                wi_alexnet_model         = wi_alexnet,
                transform_for_se_alexnet = se_transform,
                device                   = compute_device,
                dataset_label            = dataset_identifier,
            )

            log.step(f"Saving Feature CSVs — {dataset_identifier} (parallel, 5 threads)")

            def save_single_csv(spec):
                modality_key, csv_filename = spec
                save_feature_dict_to_csv(
                    feature_bundle[modality_key],
                    os.path.join(Config.FEATURES_DIR, csv_filename)
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(csv_specs), 4)) as executor:
                list(executor.map(save_single_csv, csv_specs))

            log.ok(f"  All feature CSVs saved for {dataset_identifier}.")

        # ---- PHASE 3: 5-fold Cross-Validation ----
        phase3_run_cross_validation(
            feature_bundle  = feature_bundle,
            evaluator       = evaluator,
            dataset_label   = dataset_identifier,
            force_recompute = not use_cache
        )

    # Final banner
    print()
    print("=" * 60)
    print("  Pipeline execution complete.")
    print(f"  Results  → {Config.RESULTS_DIR}")
    print(f"  Features → {Config.FEATURES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
