"""
File: confidence.py
Module: classifier
Phase: Phase 4 - Confidence-based Classification

Purpose:
    Implements confidence-based rejection layer for open-world scenario.
    Labels low-confidence predictions as "Unknown".

Paper reference:
    Panchenko et al., NDSS 2016 - Section on confidence thresholding

Windows adaptation notes: None

Dependencies:
    - numpy: Numerical operations

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-03-17
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from classifier.svm_model import predict, predict_proba_scores, load_model


def classify_with_threshold(X, threshold=None):
    """
    Classify with confidence threshold rejection.
    
    For each sample:
    1. Get raw decision function scores
    2. If max_score < threshold, label as "Unknown"
    3. Otherwise, use predicted class
    
    Args:
        X: Feature matrix (n_samples, 104)
        threshold: Confidence threshold (default from config)
    
    Returns:
        Tuple of (labels, confidence_scores)
            labels: Array of class labels or "Unknown"
            confidence_scores: Array of confidence values
    """
    if threshold is None:
        threshold = getattr(config, 'ALERT_THRESHOLD', 0.60)
    
    # Get confidence scores
    scores = predict_proba_scores(X)
    
    # Get predictions
    model = load_model()
    if model is None:
        raise FileNotFoundError("Model not loaded")
    
    predictions = model.predict(X)
    
    # Apply threshold
    labels = []
    confidences = []
    
    for pred, score in zip(predictions, scores):
        if score < threshold:
            labels.append("Unknown")
        else:
            labels.append(pred)
        confidences.append(score)
    
    return np.array(labels), np.array(confidences)


def sweep_threshold(X, y_true, thresholds=None):
    """
    Sweep threshold values and compute metrics.
    
    Useful for plotting Precision-Recall vs threshold curves.
    
    Args:
        X: Feature matrix
        y_true: True labels
        thresholds: Array of threshold values (default: 0.1 to 0.9)
    
    Returns:
        DataFrame with metrics per threshold
    """
    if thresholds is None:
        thresholds = getattr(config, 'THRESHOLD_SWEEP_VALS', 
                           [i/10 for i in range(1, 10)])
    
    results = []
    
    for threshold in thresholds:
        labels, confidences = classify_with_threshold(X, threshold)
        
        # Compute metrics
        n_known = np.sum(labels != "Unknown")
        n_unknown = np.sum(labels == "Unknown")
        
        # For known predictions, compute accuracy
        if n_known > 0:
            known_mask = labels != "Unknown"
            accuracy = np.mean(labels[known_mask] == y_true[known_mask])
        else:
            accuracy = 0.0
        
        results.append({
            'threshold': threshold,
            'n_known': n_known,
            'n_unknown': n_unknown,
            'accuracy_on_known': accuracy,
            'mean_confidence': np.mean(confidences)
        })
    
    return results


def compute_precision_recall(y_true, y_pred, unknown_label="Unknown"):
    """
    Compute precision and recall for open-world scenario.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels (may contain "Unknown")
        unknown_label: Label for unknown class
    
    Returns:
        Dictionary with precision, recall, F1
    """
    # Filter out unknowns for precision calculation
    known_mask = y_pred != unknown_label
    
    if np.sum(known_mask) == 0:
        return {'precision': 0, 'recall': 0, 'f1': 0}
    
    true_positives = np.sum((y_pred[known_mask] == y_true[known_mask]))
    predicted_positives = np.sum(known_mask)
    actual_positives = np.sum(y_true != unknown_label)
    
    precision = true_positives / predicted_positives if predicted_positives > 0 else 0
    recall = true_positives / actual_positives if actual_positives > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        'precision': precision,
        'recall': recall,
        'f1': f1
    }


if __name__ == "__main__":
    print("Testing confidence module...")
    
    # Create dummy data
    X_test = np.random.randn(20, 104)
    y_test = np.random.choice(['site_a', 'site_b'], size=20)
    
    # Test threshold classification
    print("\nTesting classify_with_threshold...")
    labels, scores = classify_with_threshold(X_test, threshold=0.5)
    print(f"Labels: {labels[:5]}")
    print(f"Scores: {scores[:5]}")
    
    print("\nTesting sweep_threshold...")
    results = sweep_threshold(X_test, y_test)
    for r in results:
        print(f"  threshold={r['threshold']}: known={r['n_known']}, unknown={r['n_unknown']}")
    
    print("\nConfidence module test complete!")
