"""
File: svm_model.py
Module: classifier
Phase: Phase 4 - SVM Classification Engine

Purpose:
    Trains and evaluates RBF-SVM classifier for website fingerprinting.
    Supports grid search for hyperparameter optimization.

Paper reference:
    Panchenko et al., "Website Fingerprinting at Internet Scale", NDSS 2016.
    Section VI: SVM classification with RBF kernel

Windows adaptation notes:
    Uses scikit-learn's SVC which wraps libsvm internally

Dependencies:
    - scikit-learn: SVM implementation
    - joblib: Model serialization

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-03-17
"""

import os
import sys
import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def train(X_train, y_train, grid_search=False):
    """
    Train SVM classifier on labeled feature data.
    
    If grid_search=True, performs 10-fold cross-validation over
    hyperparameter grid to find optimal C and gamma.
    
    If grid_search=False, uses default parameters from config.
    
    Args:
        X_train: Feature matrix (n_samples, 104)
        y_train: Label array (n_samples,)
        grid_search: Whether to perform hyperparameter search
    
    Returns:
        Trained SVC model
    """
    from sklearn.svm import SVC
    from sklearn.model_selection import GridSearchCV
    
    if grid_search:
        print("Performing grid search for optimal hyperparameters...")
        param_grid = {
            'C': getattr(config, 'GRID_SEARCH_C', [2**i for i in range(11, 18)]),
            'gamma': getattr(config, 'GRID_SEARCH_GAMMA', [2**i for i in range(-3, 4)])
        }
        
        cv_folds = getattr(config, 'CV_FOLDS', 10)
        
        svc = SVC(kernel='rbf', decision_function_shape='ovr')
        grid_searcher = GridSearchCV(
            svc, param_grid, 
            cv=cv_folds, 
            n_jobs=-1,
            verbose=1
        )
        grid_searcher.fit(X_train, y_train)
        
        best_model = grid_searcher.best_estimator_
        print(f"Best params: {grid_searcher.best_params_}")
        print(f"Best CV score: {grid_searcher.best_score_:.4f}")
        
        model = best_model
    else:
        print("Training SVM with default parameters...")
        C = getattr(config, 'SVM_C', 1.0)
        gamma = getattr(config, 'SVM_GAMMA', 'scale')
        
        model = SVC(kernel='rbf', C=C, gamma=gamma, decision_function_shape='ovr')
        model.fit(X_train, y_train)
        print("Training complete")
    
    # Save model
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    model_path = os.path.join(base_dir, "data", "models", "svm_model.pkl")
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")
    
    return model


def predict(X):
    """
    Predict website labels for feature vectors.
    
    Args:
        X: Feature matrix (n_samples, 104)
    
    Returns:
        Array of predicted labels
    """
    model = load_model()
    if model is None:
        raise FileNotFoundError("Model not trained or not found")
    
    return model.predict(X)


def predict_proba_scores(X):
    """
    Get raw decision function scores for confidence estimation.
    
    For multi-class (ovr), returns max of absolute decision values.
    
    Args:
        X: Feature matrix
    
    Returns:
        Array of confidence scores
    """
    model = load_model()
    if model is None:
        raise FileNotFoundError("Model not trained or not found")
    
    # Get decision function output
    scores = model.decision_function(X)
    
    # For multi-class, take max absolute score as confidence
    if len(scores.shape) > 1:
        confidence = np.max(np.abs(scores), axis=1)
    else:
        confidence = np.abs(scores)
    
    return confidence


def load_model():
    """
    Load trained SVM model from disk.
    
    Returns:
        Loaded SVC model or None if not found
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    model_path = os.path.join(base_dir, "data", "models", "svm_model.pkl")
    
    if not os.path.exists(model_path):
        print(f"Model not found at {model_path}")
        return None
    
    try:
        model = joblib.load(model_path)
        print(f"Loaded model from {model_path}")
        return model
    except Exception as e:
        print(f"Error loading model: {e}")
        return None


def train_and_evaluate(X, y, test_size=0.2, grid_search=False):
    """
    Train model and evaluate with train/test split.
    
    Args:
        X: Feature matrix
        y: Labels
        test_size: Fraction for test split
        grid_search: Whether to perform grid search
    
    Returns:
        Dictionary with evaluation results
    """
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )
    
    print(f"Training set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    
    # Train
    model = train(X_train, y_train, grid_search=grid_search)
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\nTest Accuracy: {accuracy:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    return {
        'accuracy': accuracy,
        'model': model,
        'X_test': X_test,
        'y_test': y_test,
        'y_pred': y_pred
    }


def cross_validate(X, y, n_folds=10):
    """
    Perform k-fold cross-validation.
    
    Args:
        X: Feature matrix
        y: Labels
        n_folds: Number of folds
    
    Returns:
        Dictionary with CV results
    """
    from sklearn.model_selection import cross_val_score
    from sklearn.svm import SVC
    
    C = getattr(config, 'SVM_C', 1.0)
    gamma = getattr(config, 'SVM_GAMMA', 'scale')
    
    model = SVC(kernel='rbf', C=C, gamma=gamma)
    
    scores = cross_val_score(model, X, y, cv=n_folds, n_jobs=-1)
    
    print(f"Cross-validation results ({n_folds} folds):")
    print(f"  Mean accuracy: {scores.mean():.4f}")
    print(f"  Std deviation: {scores.std():.4f}")
    print(f"  Per-fold: {scores}")
    
    return {
        'scores': scores,
        'mean': scores.mean(),
        'std': scores.std()
    }


if __name__ == "__main__":
    # Test with dummy data
    print("Testing SVM module...")
    
    # Create dummy features (100 samples, 104 features)
    np.random.seed(42)
    X_dummy = np.random.randn(100, 104)
    y_dummy = np.random.choice(['site_a', 'site_b', 'site_c'], size=100)
    
    # Quick train test
    print("Training on dummy data...")
    model = train(X_dummy, y_dummy, grid_search=False)
    
    print("Predicting...")
    preds = predict(X_dummy[:5])
    print(f"Sample predictions: {preds}")
    
    scores = predict_proba_scores(X_dummy[:5])
    print(f"Confidence scores: {scores}")
    
    print("SVM module test complete!")
