"""
Classifier Module
=================
Train SVM classifier with grid search optimization.
"""

import os
import sys
import warnings

# Set environment
os.environ['WIRESHARK_MANUF'] = r'C:\Program Files\Wireshark\manuf'
if 'SSLKEYLOGFILE' in os.environ:
    del os.environ['SSLKEYLOGFILE']

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def print_progress(current, total, prefix="", bar_length=40):
    """Print progress bar."""
    percent = current / total if total > 0 else 0
    filled = int(bar_length * percent)
    bar = "#" * filled + "-" * (bar_length - filled)
    sys.stdout.write(f"\r{prefix} [{bar}] {current}/{total}")
    sys.stdout.flush()


def print_step(step_num, total_steps, description):
    """Print step header."""
    print(f"\nStep {step_num}/{total_steps}: {description}")
    print("-" * 60)


def check_dependencies():
    """Check dependencies for training."""
    print_step(1, 4, "Checking dependencies")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    deps_ok = True
    
    try:
        import numpy as np
        print("  [OK] NumPy available")
    except ImportError:
        print("  [MISSING] NumPy not found")
        deps_ok = False
    
    try:
        from sklearn.svm import SVC
        from sklearn.preprocessing import LabelEncoder, StandardScaler
        from sklearn.model_selection import cross_val_score, StratifiedKFold, GridSearchCV
        print("  [OK] Scikit-learn available")
    except ImportError:
        print("  [MISSING] Scikit-learn not found")
        deps_ok = False
    
    # Check features file
    features_path = os.path.join(base_dir, "data", "processed", "features.npy")
    if os.path.exists(features_path):
        import numpy as np
        X = np.load(features_path)
        print(f"  [OK] Features found: {X.shape}")
    else:
        print("  [ERROR] features.npy not found")
        print("         Run Feature Extraction first")
        deps_ok = False
    
    return deps_ok


def load_data():
    """Load feature data."""
    print_step(2, 4, "Loading data")
    
    import numpy as np
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    X = np.load(os.path.join(base_dir, "data", "processed", "features.npy"))
    y = np.load(os.path.join(base_dir, "data", "processed", "labels.npy"), allow_pickle=True)
    
    print(f"  [OK] Loaded {X.shape[0]} samples")
    print(f"  [OK] {X.shape[1]} features per sample")
    print(f"  [OK] {len(set(y))} classes: {sorted(set(y))}")
    
    return X, y


def train_with_grid_search(X, y):
    """Train SVM with grid search."""
    print_step(3, 4, "Training with grid search")
    
    import numpy as np
    from sklearn.svm import SVC
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score
    import joblib
    
    # Separate monitored and background sites
    # Labels are just site names (e.g., 'msn', 'abcnews') - check against config
    bg_sites = set(config.BACKGROUND_SITES.keys())
    monitored_mask = np.array([str(label) not in bg_sites for label in y])
    X_monitored = X[monitored_mask]
    y_monitored = y[monitored_mask]
    
    print(f"\n  Splitting data:")
    print(f"    Monitored sites: {X_monitored.shape[0]} samples")
    print(f"    Background sites: {X.shape[0] - X_monitored.shape[0]} samples (excluded from CV)")
    
    # Encode ALL labels first (for final model), then get monitored subset
    le = LabelEncoder()
    y_all_encoded = le.fit_transform(y)
    y_monitored_encoded = y_all_encoded[monitored_mask]
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_monitored_scaled = scaler.transform(X_monitored)
    
    print(f"  [OK] Applied StandardScaler")
    
    # Grid search parameters
    param_grid = {
        'C': config.GRID_SEARCH_C,
        'gamma': config.GRID_SEARCH_GAMMA
    }
    
    print(f"\n  Grid search parameters:")
    print(f"    C: {param_grid['C']}")
    print(f"    gamma: {param_grid['gamma']}")
    print(f"    Total combinations: {len(param_grid['C']) * len(param_grid['gamma'])}")
    
    # 10-fold CV on monitored sites only
    # Note: Use min(n_splits, smallest_class_count) to handle incomplete classes
    from collections import Counter
    class_counts = Counter(y_monitored_encoded)
    min_class_count = min(class_counts.values())
    cv_folds = min(config.CV_FOLDS, min_class_count)
    
    if cv_folds < config.CV_FOLDS:
        print(f"\n  Note: Some classes have < {config.CV_FOLDS} samples (min={min_class_count})")
        print(f"  Using {cv_folds}-fold CV for stratified splits")
    
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
    
    print(f"\n  Running grid search...")
    print(f"  {cv_folds}-fold cross-validation on {X_monitored.shape[0]} monitored samples")
    print()
    
    # Fit with progress
    best_score = 0
    total_fits = len(param_grid['C']) * len(param_grid['gamma']) * cv_folds
    fit_count = 0
    
    for C in param_grid['C']:
        for gamma in param_grid['gamma']:
            for fold_idx in range(cv_folds):
                fit_count += 1
                print_progress(fit_count, total_fits, "    Training")
            
            # Test this combination on monitored sites only
            test_svm = SVC(kernel='rbf', C=C, gamma=gamma)
            scores = cross_val_score(test_svm, X_monitored_scaled, y_monitored_encoded, cv=cv)
            mean_score = scores.mean()
            
            if mean_score > best_score:
                best_score = mean_score
                best_params = {'C': C, 'gamma': gamma}
    
    print()  # Clear progress line
    
    print(f"\n  Best parameters found:")
    print(f"    C: {best_params['C']}")
    print(f"    gamma: {best_params['gamma']}")
    print(f"    CV Accuracy: {best_score:.2%}")
    
    # Train final model with best parameters on ALL data (monitored + background)
    print(f"\n  Training final model on all {X.shape[0]} samples...")
    final_model = SVC(kernel='rbf', C=best_params['C'], gamma=best_params['gamma'])
    final_model.fit(X_scaled, y_all_encoded)
    
    # Save models
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    models_dir = os.path.join(base_dir, "data", "models")
    os.makedirs(models_dir, exist_ok=True)
    
    model_path = os.path.join(models_dir, "svm_model.pkl")
    scaler_path = os.path.join(models_dir, "scaler.pkl")
    le_path = os.path.join(models_dir, "label_encoder.pkl")
    
    joblib.dump(final_model, model_path)
    joblib.dump(scaler, scaler_path)
    joblib.dump(le, le_path)
    
    print(f"  [OK] Saved svm_model.pkl")
    print(f"  [OK] Saved scaler.pkl")
    print(f"  [OK] Saved label_encoder.pkl")
    
    return final_model, scaler, le


def evaluate_model(X, y, model, scaler, le):
    """Evaluate trained model."""
    print_step(4, 4, "Evaluating model")
    
    import numpy as np
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.metrics import confusion_matrix, classification_report
    
    # Scale features
    X_scaled = scaler.transform(X)
    y_encoded = le.transform(y)
    
    # Separate monitored and background sites
    # Labels are just site names (e.g., 'msn', 'abcnews') - check against config
    bg_sites = set(config.BACKGROUND_SITES.keys())
    monitored_mask = np.array([str(label) not in bg_sites for label in y])
    X_monitored = X_scaled[monitored_mask]
    y_monitored_encoded = y_encoded[monitored_mask]
    
    # Cross-validation on monitored sites only
    from collections import Counter
    class_counts = Counter(y_monitored_encoded)
    min_class_count = min(class_counts.values())
    cv_folds = min(config.CV_FOLDS, min_class_count)
    
    if cv_folds < config.CV_FOLDS:
        print(f"\n  Note: Some classes have < {config.CV_FOLDS} samples (min={min_class_count})")
        print(f"  Using {cv_folds}-fold CV for stratified splits")
    
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_monitored, y_monitored_encoded, cv=cv, scoring='accuracy')
    
    print(f"\n  {cv_folds}-Fold Cross-Validation (monitored sites only):")
    print(f"    Mean Accuracy: {cv_scores.mean():.2%}")
    print(f"    Std Dev: {cv_scores.std():.2%}")
    print(f"    Per-fold: {[f'{s:.1%}' for s in cv_scores]}")
    
    # Training accuracy on all data
    train_preds = model.predict(X_scaled)
    train_acc = np.mean(train_preds == y_encoded)
    print(f"\n  Training Accuracy (all data): {train_acc:.2%}")
    
    # Per-class accuracy
    print("\n  Per-Class Accuracy:")
    train_preds_labels = le.inverse_transform(train_preds)
    for i, label in enumerate(le.classes_):
        mask = y == label
        if mask.sum() > 0:
            class_acc = np.mean(train_preds_labels[mask] == y[mask])
            count = mask.sum()
            print(f"    {label:15s}: {class_acc:.1%} ({count} samples)")


def run():
    """Main training pipeline."""
    # Check dependencies
    if not check_dependencies():
        print("\n  [ERROR] Cannot proceed - missing dependencies")
        return
    
    # Load data
    X, y = load_data()
    
    # Train with grid search
    model, scaler, le = train_with_grid_search(X, y)
    
    # Evaluate
    evaluate_model(X, y, model, scaler, le)
    
    # Summary
    print("\n" + "=" * 60)
    print("  TRAINING COMPLETE")
    print("=" * 60)
    print(f"  Model: data/models/svm_model.pkl")
    print(f"  Classes: {len(le.classes_)}")
    print("=" * 60)


if __name__ == "__main__":
    run()
