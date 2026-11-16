import os
import cv2
import numpy as np
from sys import path

path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import Config

class TextureExtractor:
    """
    Implements Uniform Local Binary Pattern (ULBP) with parameters (P=8, R=1).
    Applies ULBP to:
    - Face ROIs divided into blocks.
    - Iris strips divided into blocks.
    """
    def __init__(self):
        self.P = Config.ULBP_P
        self.R = Config.ULBP_R
        # Precompute the uniform mapping
        self.uniform_mapping = self._get_uniform_mapping()
        self.uniform_mapping_arr = np.array([self.uniform_mapping[i] for i in range(256)], dtype=np.uint8)

    def _get_uniform_mapping(self):
        """
        Creates a map assigning each of the 256 possible 8-bit patterns
        to one of 59 uniform bins. Non-uniform patterns are grouped 
        into a single bin.
        """
        uniform_map = {}
        newMax = 0
        for i in range(256):
            if self._is_uniform(i):
                uniform_map[i] = newMax
                newMax += 1
            else:
                uniform_map[i] = 58 # 58 is the bin for non-uniform patterns
        return uniform_map

    def _is_uniform(self, pattern):
        """
        Calculates the number of spatial transitions (0->1 or 1->0).
        A pattern is uniform if transitions <= 2.
        """
        a = pattern
        b = (a << 1) | (a >> 7) # Circular shift left
        b = b & 0xFF
        transitions = bin(a ^ b).count('1')
        return transitions <= 2

    def extract_ulbp_image(self, img):
        """
        Computes the dense ULBP image given a grayscale ROI.
        """
        # Ensure image is float or int
        if len(img.shape) == 3:
             img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # We need a padded image for R=1
        img = np.pad(img, ((1, 1), (1, 1)), mode='edge')
        # Vectorized numpy slicing instead of slow Python loops
        center = img[1:-1, 1:-1]
        
        pattern = np.zeros_like(center, dtype=np.uint8)
        
        pattern |= (img[0:-2, 0:-2] >= center).astype(np.uint8) << 7
        pattern |= (img[0:-2, 1:-1] >= center).astype(np.uint8) << 6
        pattern |= (img[0:-2, 2:]   >= center).astype(np.uint8) << 5
        pattern |= (img[1:-1, 2:]   >= center).astype(np.uint8) << 4
        pattern |= (img[2:, 2:]     >= center).astype(np.uint8) << 3
        pattern |= (img[2:, 1:-1]   >= center).astype(np.uint8) << 2
        pattern |= (img[2:, 0:-2]   >= center).astype(np.uint8) << 1
        pattern |= (img[1:-1, 0:-2] >= center).astype(np.uint8) << 0
        
        # Apply the precomputed mapping array
        ulbp_img = self.uniform_mapping_arr[pattern]
                
        return ulbp_img

    def compute_histogram(self, ulbp_block):
        """Builds a 59-bin histogram and normalizes it."""
        hist, _ = np.histogram(ulbp_block, bins=59, range=(0, 59))
        hist = hist.astype("float")
        eps = 1e-7
        hist /= (hist.sum() + eps)
        return hist

    def process_face_rois(self, rois):
        """
        Divides ROIs into blocks.
        Computes ULBP histograms and concatenates.
        """
        features = []
        block_size = Config.FACE_BLOCK_SIZE
        
        for roi in rois:
            ulbp = self.extract_ulbp_image(roi)
            h, w = ulbp.shape
            
            for y in range(0, h, block_size):
                for x in range(0, w, block_size):
                    block = ulbp[y:y+block_size, x:x+block_size]
                    hist = self.compute_histogram(block)
                    features.extend(hist)
                    
        return np.array(features, dtype=np.float32)

    def process_iris_strips(self, strips):
        """
        Divides strips into blocks.
        Computes ULBP histograms and concatenates.
        """
        features = []
        block_size = Config.IRIS_BLOCK_SIZE
        
        for strip in strips:
            ulbp = self.extract_ulbp_image(strip)
            h, w = ulbp.shape
            
            for y in range(0, h, block_size):
                for x in range(0, w, block_size):
                    block = ulbp[y:y+block_size, x:x+block_size]
                    hist = self.compute_histogram(block)
                    features.extend(hist)
                    
        return np.array(features, dtype=np.float32)

if __name__ == "__main__":
    print("Testing Texture Extractor Initialization...")
    extractor = TextureExtractor()
    print("Successfully instantiated Texture (ULBP) Extractor.")
