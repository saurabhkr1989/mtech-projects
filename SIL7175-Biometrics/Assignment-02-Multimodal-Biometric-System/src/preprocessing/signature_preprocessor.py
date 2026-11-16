import os
import sys
import cv2
import numpy as np
from PIL import Image

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import Config

class SignaturePreprocessor:
    """
    Handles Offline Signature Pre-processing.
    1. Binarize: Otsu's algorithm.
    2. Inversion: Background=0, Ink=1.
    3. Centering: Shift based on center of mass.
    4. Resizing: 170x242 pixels.

    Load via PIL to avoid LibTIFF null-byte warnings on BHSig .tif files.
    """
    def __init__(self):
        self.target_size = (Config.SIG_RESIZE_W, Config.SIG_RESIZE_H)

    def process_signature(self, image_path):
        """
        Executes the full preprocessing pipeline on a signature image.
        Returns the finalised 170x242 binary image matrix (uint8, values 0/1).
        """
        # Load via PIL to avoid LibTIFF null-byte warnings on BHSig .tif files.
        try:
            pil_img = Image.open(image_path).convert('L')
            img = np.array(pil_img, dtype=np.uint8)
        except Exception as load_err:
            raise ValueError(f"Could not load image at {image_path}: {load_err}")

        # 1. Binarization using Otsu's
        # Otsu returns the threshold value and the thresholded image
        _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 2. Inversion (Ink=1, Background=0)
        # Assuming original signature is dark ink on light background
        # Otsu makes dark pixels 0 and light 255. Inversion makes Ink=255.
        inverted = cv2.bitwise_not(binary)
        
        # Scale to 0 and 1 for strict binary logic
        ink_map = (inverted > 0).astype(np.uint8)

        # 3. Centering based on Center of Mass
        # Calculate image moments
        M = cv2.moments(ink_map)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
        else:
            # Fallback if no ink found
            cX, cY = ink_map.shape[1] // 2, ink_map.shape[0] // 2

        # Calculate shift required to bring CoM to image center
        center_x = ink_map.shape[1] // 2
        center_y = ink_map.shape[0] // 2
        
        shift_x = center_x - cX
        shift_y = center_y - cY

        # Create translation matrix
        translation_matrix = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
        
        # Apply translation
        centered = cv2.warpAffine(ink_map, translation_matrix, (ink_map.shape[1], ink_map.shape[0]))

        # 4. Resizing to 170x242
        # Use INTER_NEAREST to preserve the clear binary {0, 1} nature
        final_resized = cv2.resize(centered, self.target_size, interpolation=cv2.INTER_NEAREST)

        return final_resized

if __name__ == "__main__":
    print("Testing Signature Preprocessor Initialization...")
    preprocessor = SignaturePreprocessor()
    print("Successfully instantiated Signature Preprocessor.")
