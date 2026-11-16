"""
File: closed_world.py
Module: evaluate
Phase: Phase 5 - Closed-World Evaluation

Purpose:
    Evaluates classifier in closed-world scenario (all sites monitored).
    Reports accuracy, confusion matrix, and per-class metrics.

Paper reference:
    Panchenko et al., NDSS 2016 - Section VII evaluation methodology

Windows adaptation notes: None

Dependencies:
    - scikit-learn: Metrics
    - matplotlib: Visualization

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-03-17
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from classifier.svm_model import load_model, predict
from features.scaler import transform


def run_closed_world_eval(X, y, save_dir=None):
    """
    Run closed-world evaluation.
    
    Uses 10-fold cross-validation to evaluate accuracy.
    
    Args:
        X: Feature matrix (n_samples, 104)
        y: Labels (n_samples,)
        save_dir: Directory to save results
    
    Returns:
        Dictionary with evaluation metrics
    """
    from sklearn.model_selection import cross_val_predict
    
    print("=" * 60)
    print("  Closed-World Evaluation")
    print("=" * 60)
    
    # Scale features
    print("Scaling features...")
    X_scaled = transform(X)
    
    # Load or train model
    model = load_model()
    
    if model is None:
        print("No trained model found. Training new model...")
        from classifier.svm_model import train
        model = train(X_scaled, y, grid_search=False)
    
    # Cross-validation predictions
    print("Performing 10-fold cross-validation...")
    from sklearn.model_selection import cross_val_score
    from sklearn.svm import SVC
    
    C = getattr(config, 'SVM_C', 1.0)
    gamma = getattr(config, 'SVM_GAMMA', 'scale')
    cv_clf = SVC(kernel='rbf', C=C, gamma=gamma)
    
    cv_scores = cross_val_score(cv_clf, X_scaled, y, cv=10, n_jobs=-1)
    
    print(f"\nCross-validation results:")
    print(f"  Mean accuracy: {cv_scores.mean():.4f}")
    print(f"  Std deviation: {cv_scores.std():.4f}")
    print(f"  Per-fold: {cv_scores}")
    
    # Train/test split for detailed metrics
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )
    
    clf = SVC(kernel='rbf', C=C, gamma=gamma)
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\nTest set accuracy (80/20 split): {accuracy:.4f}")
    
    # Classification report
    print("\nClassification Report:")
    report = classification_report(y_test, y_pred)
    print(report)
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    print("\nConfusion Matrix:")
    print(cm)
    
    # Plot confusion matrix
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        plot_confusion_matrix(cm, y_test, save_dir)
    
    results = {
        'cv_accuracy_mean': cv_scores.mean(),
        'cv_accuracy_std': cv_scores.std(),
        'cv_scores': cv_scores.tolist(),
        'test_accuracy': accuracy,
        'confusion_matrix': cm.tolist()
    }
    
    return results


def plot_confusion_matrix(cm, labels, save_dir):
    """
    Plot and save confusion matrix.
    
    Args:
        cm: Confusion matrix
        labels: Class labels
        save_dir: Directory to save plot
    """
    plt.figure(figsize=(10, 8))
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title('Confusion Matrix - Closed World')
    plt.colorbar()
    
    tick_marks = np.arange(len(labels))
    plt.xticks(tick_marks, labels, rotation=45)
    plt.yticks(tick_marks, labels)
    
    # Add text annotations
    thresh = cm.max() / 2.
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(j, i, format(cm[i, j], 'd'),
                    horizontalalignment="center",
                    color="white" if cm[i, j] > thresh else "black")
    
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.tight_layout()
    
    save_path = os.path.join(save_dir, 'confusion_matrix.png')
    plt.savefig(save_path)
    print(f"Saved confusion matrix to {save_path}")
    plt.close()


if __name__ == "__main__":
    print("Testing closed-world evaluation...")
    
    # Would load actual data
    print("This module requires feature data to run.")
    print("After collecting PCAP data and running feature extraction,")
    print("call run_closed_world_eval() with the feature matrix.")
