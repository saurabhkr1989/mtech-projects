import numpy as np

class FeatureFusion:
    """
    Implements Feature-Level Fusion by concatenating the unnormalized
    feature vectors from Face, Iris, and Offline Signature modalities.
    """
    def __init__(self):
        pass

    def concatenate_features(self, face_ulbp, face_deep, iris_ulbp, iris_deep, sig_deep):
        """
        Concatenates 5 feature vectors into a single vector.
        
        Args:
            face_ulbp: np.array (Dimensions depend on ULBP config)
            face_deep: np.array (4096,)
            iris_ulbp: np.array (Dimensions depend on ULBP config)
            iris_deep: np.array (4096,)
            sig_deep: np.array (4096,)
            
        Returns:
            np.array (1D concatenated vector)
        """
        # Ensure all inputs are 1D arrays
        f1 = np.ravel(face_ulbp)
        f2 = np.ravel(face_deep)
        f3 = np.ravel(iris_ulbp)
        f4 = np.ravel(iris_deep)
        f5 = np.ravel(sig_deep)
        
        fused_vector = np.concatenate([f1, f2, f3, f4, f5])
        return fused_vector


class DecisionFusion:
    """
    Implements Decision-Level Fusion via Majority Voting.
    Fuses the binary decisions {0, 1} from 5 independent SVM classifiers.
    """
    def __init__(self):
        pass
        
    def majority_vote(self, decisions):
        """
        Takes exactly 5 binary decisions (1=Match, 0=Impostor).
        Returns 1 if sum >= 3, else 0.
        
        Args:
           decisions: List or Array of 5 integers [d1, d2, d3, d4, d5]
        """
        if len(decisions) != 5:
            raise ValueError(f"Decision-Level Fusion requires exactly 5 decisions. Got {len(decisions)}.")
            
        vote_sum = sum(decisions)
        result = 1 if vote_sum >= 3 else 0
        
        return result

    def soft_fusion_sum(self, probabilities):
         """
         Optional: Sum rule for soft probabilities.
         """
         if len(probabilities) != 5:
             raise ValueError("Requires 5 probabilities.")
             
         avg_prob = sum(probabilities) / 5.0
         return avg_prob

if __name__ == "__main__":
    print("Testing Fusion Logic...")
    
    # Test Decision Fusion
    df = DecisionFusion()
    print("Vote [1, 1, 0, 0, 1] =", df.majority_vote([1, 1, 0, 0, 1])) # Should be 1
    print("Vote [0, 1, 0, 0, 1] =", df.majority_vote([0, 1, 0, 0, 1])) # Should be 0
    
    # Test Feature Fusion
    ff = FeatureFusion()
    v1 = np.ones(10)
    v2 = np.ones(20) * 2
    merged = ff.concatenate_features(v1, v2, v1, v2, v1)
    print(f"Concatenated Vector Shape: {merged.shape}") # Should be 10+20+10+20+10 = 70
