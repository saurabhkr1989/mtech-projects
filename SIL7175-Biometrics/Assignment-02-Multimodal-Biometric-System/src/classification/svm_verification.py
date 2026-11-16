import numpy as np
import os
import sys

import joblib
from sklearn.svm import SVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.logger import log


class SVMVerifier:
    """
    Per-user binary SVM verifier (one instance per Virtual_User_ID per modality).
    Caches the fitted model and scaler to disk.
    """

    def __init__(self, user_id: str, modality_name: str):
        self.user_id       = user_id
        self.modality_name = modality_name

        # We use a standard SVM (probability=False) and use decision_function for ROC curves.
        self.model  = SVC(kernel='rbf', class_weight='balanced', probability=False, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False

    # ------------------------------------------------------------------ #
    # Cache paths                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _cache_filename(cache_dir: str, dataset: str, fold_num: int,
                        modality: str, user_id: str) -> str:
        """
        Builds a deterministic filename for cache.
        """
        # Sanitise modality name — it can contain slashes or spaces
        safe_modality = modality.replace("/", "_").replace(" ", "_")
        safe_user     = str(user_id).replace("/", "_")
        fname = f"{dataset}_fold{fold_num:02d}_{safe_modality}_{safe_user}.joblib"
        return os.path.join(cache_dir, fname)

    # ------------------------------------------------------------------ #
    # Public: save after training                                           #
    # ------------------------------------------------------------------ #

    def save_to_cache(self, cache_dir: str, dataset: str, fold_num: int):
        """
        Persists the trained model + scaler to disk.
        """
        if not self.is_trained:
            log.warn(f"save_to_cache called on untrained verifier "
                     f"({self.user_id}, {self.modality_name}) — skipping.")
            return

        os.makedirs(cache_dir, exist_ok=True)
        cache_path = self._cache_filename(
            cache_dir, dataset, fold_num, self.modality_name, self.user_id
        )
        payload = {
            "model":        self.model,
            "scaler":       self.scaler,
            "user_id":      self.user_id,
            "modality":     self.modality_name,
            "fold":         fold_num,
            "dataset":      dataset,
        }
        joblib.dump(payload, cache_path, compress=3)
        # Verbose cache-save log only at DEBUG level to avoid flooding console;
        # the caller logs a summary count instead.

    # ------------------------------------------------------------------ #
    # Public: load from cache (classmethod — returns instance or None)     #
    # ------------------------------------------------------------------ #

    @classmethod
    def load_from_cache(cls, cache_dir: str, dataset: str, fold_num: int,
                        modality: str, user_id: str) -> "SVMVerifier | None":
        """
        Attempts to load a previously trained verifier from disk.
        """
        cache_path = cls._cache_filename(cache_dir, dataset, fold_num,
                                          modality, user_id)
        if not os.path.exists(cache_path):
            return None

        try:
            payload    = joblib.load(cache_path)
            instance   = cls.__new__(cls)                # bypass __init__
            instance.user_id       = payload["user_id"]
            instance.modality_name = payload["modality"]
            instance.model         = payload["model"]
            instance.scaler        = payload["scaler"]
            instance.is_trained    = True
            return instance
        except Exception as load_err:
            log.warn(f"SVM cache load failed for {user_id}/{modality}/fold{fold_num}: "
                     f"{load_err}  — will retrain.")
            return None

    # ------------------------------------------------------------------ #
    # Core: train                                                           #
    # ------------------------------------------------------------------ #

    def train_user_model(self, all_features, all_labels) -> bool:
        """
        Trains the binary SVM for this user.
        Positive class  (+1) = this user's samples.
        Negative class  (0)  = random 1:3 subset of other users' samples.

        Returns True on success, False when no positive samples exist.
        """
        features_np   = np.array(all_features)
        labels_np     = np.array(all_labels)
        binary_labels = np.where(labels_np == self.user_id, 1, 0)

        pos_indices = np.where(binary_labels == 1)[0]
        neg_indices = np.where(binary_labels == 0)[0]

        if len(pos_indices) == 0:
            log.warn(f"No positive samples for '{self.user_id}' "
                     f"[{self.modality_name}]. SVM skipped.")
            return False

        # Caller pre-samples negatives at 1:3 ratio.
        selected  = np.concatenate([pos_indices, neg_indices])
        X_train   = features_np[selected]
        y_train   = binary_labels[selected]

        X_scaled  = self.scaler.fit_transform(X_train)

        # Fit the standard RBF SVM

        self.model.fit(X_scaled, y_train)
        self.is_trained = True
        return True

    # ------------------------------------------------------------------ #
    # Core: verify                                                          #
    # ------------------------------------------------------------------ #

    def verify(self, feature_vector) -> tuple:
        """
        Returns (binary_decision, match_probability) for a single test vector.
        binary_decision : 1 = Genuine match, 0 = Impostor
        match_probability : float [0, 1] used for ROC/EER curves
        """
        if not self.is_trained:
            raise ValueError(
                f"SVMVerifier for '{self.user_id}' ({self.modality_name}) "
                f"is not trained yet."
            )
        X_test  = np.array(feature_vector).reshape(1, -1)
        X_scaled = self.scaler.transform(X_test)
        decision  = int(self.model.predict(X_scaled)[0])
        score     = float(self.model.decision_function(X_scaled)[0])
        return decision, score

    def verify_batch(self, feature_vectors) -> tuple:
        """
        Returns (array of decisions, array of probabilities) for a batch of test vectors.
        """
        if not self.is_trained:
            raise ValueError(f"SVMVerifier '{self.user_id}' ({self.modality_name}) is not trained yet.")
        X_test = np.array(feature_vectors)
        if len(X_test.shape) == 1:
            X_test = X_test.reshape(1, -1)
        X_scaled = self.scaler.transform(X_test)
        decisions = self.model.predict(X_scaled).astype(int)
        scores = self.model.decision_function(X_scaled).astype(float)
        return decisions, scores


if __name__ == "__main__":
    print("Smoke test: SVMVerifier with caching...")
    import tempfile

    X = np.random.randn(50, 128)
    Y = ["U1"] * 10 + ["U2"] * 10 + ["U3"] * 10 + ["U4"] * 10 + ["U5"] * 10

    with tempfile.TemporaryDirectory() as tmpdir:
        # Train and save
        v = SVMVerifier("U1", "test_modality")
        assert v.train_user_model(X, Y) is True
        v.save_to_cache(tmpdir, "Dataset_1", fold_num=1)

        # Load from cache
        v2 = SVMVerifier.load_from_cache(tmpdir, "Dataset_1", 1,
                                          "test_modality", "U1")
        assert v2 is not None and v2.is_trained

        # Verify consistency
        d1, p1 = v.verify(X[0])
        d2, p2 = v2.verify(X[0])
        assert d1 == d2 and abs(p1 - p2) < 1e-6, "Cache mismatch!"

        # Missing cache returns None
        missing = SVMVerifier.load_from_cache(tmpdir, "Dataset_1", 2,
                                               "test_modality", "U99")
        assert missing is None

    print("All assertions passed — SVMVerifier caching works correctly.")
