"""
File: scaler.py
Module: features
Phase: Phase 4 - Feature Scaling

Purpose:
    Scales features to [-1, 1] range for SVM training.
    Fits only on training data to prevent data leakage.

Paper reference:
    Panchenko et al., NDSS 2016 - Feature normalization

Windows adaptation notes: None

Dependencies:
    - scikit-learn: MinMaxScaler

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-03-17
"""

import os
import sys
import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class FeatureScaler:
    """
    Scales CUMUL features to [-1, 1] range.
    
    Uses scikit-learn's MinMaxScaler with custom feature range.
    IMPORTANT: Must be fitted ONLY on training data.
    """
    
    def __init__(self, feature_range=(-1, 1)):
        from sklearn.preprocessing import MinMaxScaler
        self.scaler = MinMaxScaler(feature_range=feature_range)
        self.is_fitted = False
    
    def fit(self, X):
        """
        Fit scaler on training data.
        
        Args:
            X: Feature matrix (n_samples, 104)
        """
        self.scaler.fit(X)
        self.is_fitted = True
        return self
    
    def transform(self, X):
        """
        Transform features using fitted scaler.
        
        Args:
            X: Feature matrix
        
        Returns:
            Scaled feature matrix
        """
        if not self.is_fitted:
            raise ValueError("Scaler not fitted. Call fit() first.")
        return self.scaler.transform(X)
    
    def fit_transform(self, X):
        """
        Fit and transform in one step.
        
        Use only on training data!
        
        Args:
            X: Feature matrix
        
        Returns:
            Scaled feature matrix
        """
        self.scaler.fit(X)
        self.is_fitted = True
        return self.scaler.transform(X)
    
    def inverse_transform(self, X_scaled):
        """
        Reverse scaling transformation.
        
        Args:
            X_scaled: Scaled features
        
        Returns:
            Original scale features
        """
        return self.scaler.inverse_transform(X_scaled)
    
    def save(self, path):
        """
        Save fitted scaler to disk.
        
        Args:
            path: Path to save scaler
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.scaler, path)
        print(f"Scaler saved to {path}")
    
    def load(self, path):
        """
        Load fitted scaler from disk.
        
        Args:
            path: Path to saved scaler
        """
        self.scaler = joblib.load(path)
        self.is_fitted = True
        print(f"Scaler loaded from {path}")


def fit_scaler(X):
    """
    Factory function to create and fit scaler.
    
    Args:
        X: Training feature matrix
    
    Returns:
        Fitted FeatureScaler
    """
    scaler = FeatureScaler(feature_range=(-1, 1))
    scaler.fit(X)
    
    # Save to default path
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    scaler_path = os.path.join(base_dir, "data", "models", "scaler.pkl")
    scaler.save(scaler_path)
    
    return scaler


def transform(X, scaler_path=None):
    """
    Transform features using saved scaler.
    
    Args:
        X: Feature matrix
        scaler_path: Path to saved scaler (default from config)
    
    Returns:
        Scaled features
    """
    if scaler_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        scaler_path = os.path.join(base_dir, "data", "models", "scaler.pkl")
    
    if not os.path.exists(scaler_path):
        raise FileNotFoundError(f"Scaler not found at {scaler_path}")
    
    scaler = FeatureScaler()
    scaler.load(scaler_path)
    
    return scaler.transform(X)


def fit_transform(X):
    """
    Fit scaler on training data and transform.
    
    Args:
        X: Training feature matrix
    
    Returns:
        Scaled features
    """
    scaler = FeatureScaler()
    result = scaler.fit_transform(X)
    
    # Save
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    scaler_path = os.path.join(base_dir, "data", "models", "scaler.pkl")
    scaler.save(scaler_path)
    
    return result


if __name__ == "__main__":
    # Test scaler
    print("Testing FeatureScaler...")
    
    # Create dummy data
    X_train = np.random.randn(100, 104) * 1000
    X_test = np.random.randn(20, 104) * 1000
    
    print(f"Original - Train: {X_train.min():.2f} to {X_train.max():.2f}")
    print(f"Original - Test: {X_test.min():.2f} to {X_test.max():.2f}")
    
    # Fit on train only
    scaler = FeatureScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    
    print(f"Scaled - Train: {X_train_scaled.min():.2f} to {X_train_scaled.max():.2f}")
    
    # Transform test (using train's scaler)
    X_test_scaled = scaler.transform(X_test)
    print(f"Scaled - Test: {X_test_scaled.min():.2f} to {X_test_scaled.max():.2f}")
    
    print("Scaler test complete!")
