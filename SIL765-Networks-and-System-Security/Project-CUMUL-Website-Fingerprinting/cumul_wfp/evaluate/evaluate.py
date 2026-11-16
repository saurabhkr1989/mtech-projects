"""
Evaluation Module
=================
Evaluate trained SVM classifier.
Outputs detailed reports to files, key metrics to console.
"""

import os
import sys
import json
from datetime import datetime

# Set environment
os.environ['WIRESHARK_MANUF'] = r'C:\Program Files\Wireshark\manuf'
if 'SSLKEYLOGFILE' in os.environ:
    del os.environ['SSLKEYLOGFILE']

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def print_step(step_num, total_steps, description):
    """Print step header."""
    print(f"\nStep {step_num}/{total_steps}: {description}")
    print("-" * 60)


def get_results_dir():
    """Get/create results directory."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    return results_dir


def check_dependencies():
    """Check dependencies for evaluation."""
    print_step(1, 4, "Checking dependencies")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    deps_ok = True
    
    try:
        import numpy as np
        print("  [OK] NumPy")
    except ImportError:
        print("  [MISSING] NumPy")
        deps_ok = False
    
    try:
        from sklearn.metrics import accuracy_score, confusion_matrix
        print("  [OK] Scikit-learn")
    except ImportError:
        print("  [MISSING] Scikit-learn")
        deps_ok = False
    
    # Check model files
    model_path = os.path.join(base_dir, "data", "models", "svm_model.pkl")
    if os.path.exists(model_path):
        print("  [OK] Model file")
    else:
        print("  [ERROR] Model not found - run training first")
        deps_ok = False
    
    if os.path.exists(os.path.join(base_dir, "data", "models", "scaler.pkl")):
        print("  [OK] Scaler")
    else:
        print("  [ERROR] Scaler not found")
        deps_ok = False
    
    features_path = os.path.join(base_dir, "data", "processed", "features.npy")
    if os.path.exists(features_path):
        import numpy as np
        X = np.load(features_path)
        print(f"  [OK] Features: {X.shape}")
    else:
        print("  [ERROR] Features not found")
        deps_ok = False
    
    return deps_ok


def load_model_and_data():
    """Load trained model and data."""
    print_step(2, 4, "Loading model and data")
    
    import numpy as np
    import joblib
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Load model
    model = joblib.load(os.path.join(base_dir, "data", "models", "svm_model.pkl"))
    scaler = joblib.load(os.path.join(base_dir, "data", "models", "scaler.pkl"))
    le = joblib.load(os.path.join(base_dir, "data", "models", "label_encoder.pkl"))
    
    # Load data
    X = np.load(os.path.join(base_dir, "data", "processed", "features.npy"))
    y = np.load(os.path.join(base_dir, "data", "processed", "labels.npy"), allow_pickle=True)
    
    # Separate monitored and background
    bg_sites = set(config.BACKGROUND_SITES.keys())
    monitored_mask = np.array([str(label) not in bg_sites for label in y])
    
    n_monitored = monitored_mask.sum()
    n_background = len(y) - n_monitored
    
    print(f"  [OK] Model loaded ({len(le.classes_)} classes)")
    print(f"  [OK] Data: {X.shape[0]} samples ({n_monitored} monitored, {n_background} background)")
    
    return model, scaler, le, X, y, monitored_mask


def cross_validate(X, y, model, scaler, le, monitored_mask):
    """Perform cross-validation on monitored sites."""
    print_step(3, 4, "Cross-validation")
    
    import numpy as np
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from collections import Counter
    
    results_dir = get_results_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Scale and encode
    X_scaled = scaler.transform(X)
    y_encoded = le.transform(y)
    
    # Get monitored subset
    X_monitored = X_scaled[monitored_mask]
    y_monitored_encoded = y_encoded[monitored_mask]
    
    # Calculate CV folds
    class_counts = Counter(y_monitored_encoded)
    min_class_count = min(class_counts.values())
    cv_folds = min(10, min_class_count)
    
    print(f"\n  Monitored samples: {len(y_monitored_encoded)}")
    print(f"  CV folds: {cv_folds} (min class has {min_class_count} samples)")
    
    # Run cross-validation
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
    scores = cross_val_score(model, X_monitored, y_monitored_encoded, cv=cv, scoring='accuracy')
    
    mean_acc = scores.mean()
    std_acc = scores.std()
    
    print(f"\n  Mean Accuracy: {mean_acc:.2%}")
    print(f"  Std Deviation: {std_acc:.2%}")
    
    # Save CV results to file
    cv_results = {
        'timestamp': timestamp,
        'cv_folds': cv_folds,
        'fold_scores': scores.tolist(),
        'mean_accuracy': float(mean_acc),
        'std_deviation': float(std_acc),
        'n_samples': int(len(y_monitored_encoded)),
        'n_classes': int(len(set(y_monitored_encoded)))
    }
    
    cv_file = os.path.join(results_dir, f"cv_results_{timestamp}.json")
    with open(cv_file, 'w') as f:
        json.dump(cv_results, f, indent=2)
    
    print(f"  [Saved] {cv_file}")
    
    return mean_acc, std_acc, scores


def generate_reports(X, y, model, scaler, le, monitored_mask, cv_mean, cv_std):
    """Generate detailed classification reports."""
    print_step(4, 4, "Classification reports")
    
    import numpy as np
    from sklearn.metrics import confusion_matrix, classification_report
    
    results_dir = get_results_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Predictions
    X_scaled = scaler.transform(X)
    y_encoded = le.transform(y)
    y_pred_encoded = model.predict(X_scaled)
    y_pred = le.inverse_transform(y_pred_encoded)
    
    # Get monitored-only predictions for clean metrics
    y_monitored = y[monitored_mask]
    y_pred_monitored = y_pred[monitored_mask]
    
    # Overall accuracy (all data)
    accuracy = np.mean(y_pred_encoded == y_encoded)
    print(f"\n  Training Accuracy (all data): {accuracy:.2%}")
    
    # Monitored-only accuracy
    monitored_acc = np.mean(y_pred_monitored == y_monitored)
    print(f"  Training Accuracy (monitored only): {monitored_acc:.2%}")
    
    # Classification report (monitored only)
    classes = [c for c in le.classes_ if c not in config.BACKGROUND_SITES]
    
    print(f"\n  Detailed report saved to results folder")
    
    # Generate report for monitored sites
    report = classification_report(y_monitored, y_pred_monitored, labels=classes, 
                                  output_dict=True, zero_division=0)
    
    # Confusion matrix
    cm = confusion_matrix(y_monitored, y_pred_monitored, labels=classes)
    
    # Save detailed report
    report_data = {
        'timestamp': timestamp,
        'cv_accuracy_mean': float(cv_mean),
        'cv_accuracy_std': float(cv_std),
        'training_accuracy_all': float(accuracy),
        'training_accuracy_monitored': float(monitored_acc),
        'n_samples': int(len(y)),
        'n_monitored': int(monitored_mask.sum()),
        'n_background': int(len(y) - monitored_mask.sum()),
        'classes': {
            c: {
                'precision': float(report[c]['precision']),
                'recall': float(report[c]['recall']),
                'f1': float(report[c]['f1-score']),
                'support': int(report[c]['support'])
            } for c in classes if c in report
        },
        'macro_avg': {
            'precision': float(report['macro avg']['precision']),
            'recall': float(report['macro avg']['recall']),
            'f1': float(report['macro avg']['f1-score'])
        },
        'weighted_avg': {
            'precision': float(report['weighted avg']['precision']),
            'recall': float(report['weighted avg']['recall']),
            'f1': float(report['weighted avg']['f1-score'])
        }
    }
    
    report_file = os.path.join(results_dir, f"evaluation_report_{timestamp}.json")
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    # Save confusion matrix
    cm_file = os.path.join(results_dir, f"confusion_matrix_{timestamp}.csv")
    with open(cm_file, 'w') as f:
        f.write("," + ",".join(classes) + "\n")
        for i, c in enumerate(classes):
            f.write(c + "," + ",".join(map(str, cm[i])) + "\n")
    
    print(f"  [Saved] {report_file}")
    print(f"  [Saved] {cm_file}")
    
    # Print summary table to console
    print(f"\n  Per-Class Performance (F1 Score):")
    print("  " + "-" * 45)
    print(f"  {'Site':<18} {'P':>7} {'R':>7} {'F1':>7}")
    print("  " + "-" * 45)
    
    for c in classes:
        if c in report:
            p = report[c]['precision']
            r = report[c]['recall']
            f = report[c]['f1-score']
            s = int(report[c]['support'])
            print(f"  {c:<18} {p:6.1%} {r:6.1%} {f:6.1%}")
    
    print("  " + "-" * 45)
    print(f"  {'Macro Avg':<18} {report['macro avg']['precision']:6.1%} {report['macro avg']['recall']:6.1%} {report['macro avg']['f1-score']:6.1%}")
    print(f"  {'Weighted Avg':<18} {report['weighted avg']['precision']:6.1%} {report['weighted avg']['recall']:6.1%} {report['weighted avg']['f1-score']:6.1%}")
    
    return accuracy, monitored_acc, report


def run():
    """Main evaluation pipeline."""
    # Check dependencies
    if not check_dependencies():
        print("\n  [ERROR] Cannot proceed - missing dependencies")
        return
    
    # Load model and data
    model, scaler, le, X, y, monitored_mask = load_model_and_data()
    
    # Cross-validation
    cv_mean, cv_std, scores = cross_validate(X, y, model, scaler, le, monitored_mask)
    
    # Reports
    accuracy, monitored_acc, report = generate_reports(X, y, model, scaler, le, monitored_mask, cv_mean, cv_std)
    
    # Summary
    print("\n" + "=" * 60)
    print("  EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  Cross-Validation Accuracy: {cv_mean:.2%} (+/- {cv_std:.2%})")
    print(f"  Training Accuracy (monitored): {monitored_acc:.2%}")
    print(f"  Macro F1-Score: {report['macro avg']['f1-score']:.2%}")
    print(f"  Weighted F1-Score: {report['weighted avg']['f1-score']:.2%}")
    print("=" * 60)
    print(f"\n  Reports saved to: results/")
    
    # Generate visualizations
    print("\n  Generating visualizations...")
    try:
        from . import visualize
        visualize.run()
    except Exception as e:
        print(f"  [WARNING] Could not generate visualizations: {e}")


if __name__ == "__main__":
    run()
