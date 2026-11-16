import os
import cv2
import numpy as np
from sys import path

path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import Config

class IrisPreprocessor:
    """
    Handles Iris Modality Pre-processing.
    1. Segments the iris using Hough Circles.
    2. Unrolls into a 512x64 rectangular format (Daugman's rubber sheet).
    3. Divides into 10 horizontal strips (32x512 pixels, stride 4).
    4. Applies Histogram Equalization and Mean Variance normalization per strip.
    """
    def __init__(self):
        pass
        
    def find_pupil_and_iris(self, gray_image):
        """
        Approximate localization using Hough Gradient Method.
        Returns (pupil_x, pupil_y, pupil_r), (iris_x, iris_y, iris_r)
        """
        # Downscale for detection to 25% if image is very large
        scale = 1.0
        if gray_image.shape[0] > 1000:
            scale = 0.25
            detect_gray = cv2.resize(gray_image, (0, 0), fx=scale, fy=scale)
        else:
            detect_gray = gray_image
            
        # Enhance for pupil
        blurred = cv2.GaussianBlur(detect_gray, (7, 7), 0)
        
        # Dynamically scale search radii based on image resolution
        img_h = detect_gray.shape[0]
        
        # Determine dynamic parameters. CASIA (1728x2352) vs IITD (320x240)
        is_high_res = img_h > 1000
        
        pupil_min_r = int(img_h * 0.01) # Typically 1-5% of image height
        pupil_max_r = int(img_h * 0.15)
        
        # Adaptive Hough threshold sweep for pupil detection.
        pupil = None
        for hough_threshold in [25, 20, 15, 10, 8, 5]:
            circles_pupil = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=img_h // 8,
                param1=200, param2=hough_threshold,
                minRadius=pupil_min_r, maxRadius=pupil_max_r
            )
            if circles_pupil is not None:
                pupil = np.round(circles_pupil[0][0]).astype("int")
                break

        if pupil is None:
            # Hough sweep failed — try contour-based pupil estimation.
            for brightness_cutoff in [30, 40, 50, 60]:
                _, thresh = cv2.threshold(blurred, brightness_cutoff, 255, cv2.THRESH_BINARY_INV)
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    continue
                c = max(contours, key=cv2.contourArea)
                (x, y), r = cv2.minEnclosingCircle(c)
                # Accept up to 20% of image height as valid pupil radius
                # (slightly relaxed from the Hough upper bound to handle NIR glare)
                pupil_max_r_ext = int(img_h * 0.20)
                if pupil_min_r < r < pupil_max_r_ext:
                    pupil = (int(x), int(y), int(r))
                    break

        if pupil is None:
            raise ValueError("Pupil localization failed.")

        px, py, pr = pupil
        
        iris_min_r = int(pr + (img_h * 0.05))
        iris_max_r = int(pr * 4.0)
        
        # 2. Finding Iris boundary (Larger circle around pupil). Same adaptive sweep strategy.
        iris = None
        for iris_hough_threshold in [10, 15, 20, 30, 40]:
            circles_iris = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=img_h // 8,
                param1=100, param2=iris_hough_threshold,
                minRadius=iris_min_r, maxRadius=iris_max_r
            )
            if circles_iris is not None:
                iris_candidates = np.round(circles_iris[0]).astype("int")
                # Pick the candidate closest to pupil center
                best_dist = float('inf')
                for (ix, iy, ir) in iris_candidates:
                    dist = np.sqrt((ix - px)**2 + (iy - py)**2)
                    if dist < best_dist and ir > pr:
                        best_dist = dist
                        iris = (ix, iy, ir)
                if iris is not None:
                    break

        if iris is None:
            raise ValueError("Iris boundary localization failed.")
             
        # Scale back to original resolution
        if scale != 1.0:
             pupil = (int(pupil[0]/scale), int(pupil[1]/scale), int(pupil[2]/scale))
             iris = (int(iris[0]/scale), int(iris[1]/scale), int(iris[2]/scale))
             
        return pupil, iris

    def daugman_rubber_sheet(self, image, pupil, iris):
        """
        Unrolls the iris ring into a rectangular matrix 512x64.
        """
        px, py, pr = pupil
        ix, iy, ir = iris
        
        theta = np.linspace(0, 2 * np.pi, Config.IRIS_NORM_W)
        r = np.linspace(0, 1, Config.IRIS_NORM_H)
        
        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)

        inner_x = px + pr * cos_theta
        inner_y = py + pr * sin_theta
        
        # Assume iris center is close to pupil center for simplified Daugman
        outer_x = ix + ir * cos_theta
        outer_y = iy + ir * sin_theta

        # Broadcast r (H, 1) to multiply with inner/outer coords (W,)
        r_mat = r[:, np.newaxis]
        
        x_unrolled = (1 - r_mat) * inner_x + r_mat * outer_x
        y_unrolled = (1 - r_mat) * inner_y + r_mat * outer_y
        
        x_unrolled = x_unrolled.astype(np.float32)
        y_unrolled = y_unrolled.astype(np.float32)
                
        # Remap
        normalized = cv2.remap(image, x_unrolled, y_unrolled, cv2.INTER_LINEAR)
        return normalized

    def enhance_strip(self, strip):
        """Applies Histogram Equalization and Mean-Variance normalization."""
        eq_strip = cv2.equalizeHist(strip)
        
        float_strip = eq_strip.astype(np.float32)
        mean, std = cv2.meanStdDev(float_strip)
        std = max(std[0][0], 1e-6)
        
        norm_strip = (float_strip - mean[0][0]) / std
        return eq_strip, norm_strip

    def extract_strips(self, image_path):
        """
        Full pipeline: Segment -> Normalize -> Slice into 10 overlapping strips.
        Returns a list of 10 enhanced/normalized strip matrices.
        """
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"Could not load image at {image_path}")
            
        pupil, iris = self.find_pupil_and_iris(img)
        normalized_img = self.daugman_rubber_sheet(img, pupil, iris)
        
        strips = []
        # Create 10 horizontal strips of 32x512 pixels with 4-pixel stride
        # Output unrolled is 64(H) x 512(W).
        # We need strips of 32x512
        
        start_y = 0
        for i in range(Config.NUM_IRIS_STRIPS):
            y1 = start_y
            y2 = start_y + Config.IRIS_STRIP_H
            if y2 > Config.IRIS_NORM_H:
                # If we hit the boundary, just take the last 32 rows
                y2 = Config.IRIS_NORM_H
                y1 = y2 - Config.IRIS_STRIP_H
                
            strip = normalized_img[y1:y2, :]
            _, norm_strip = self.enhance_strip(strip)
            strips.append(norm_strip)
            
            start_y += Config.IRIS_STRIP_STRIDE
            
        # Ensure exactly 10 strips
        if len(strips) != Config.NUM_IRIS_STRIPS:
             print(f"Warning: Expected 10 iris strips, got {len(strips)}. Extrapolating.")
        
        return strips[:Config.NUM_IRIS_STRIPS]

if __name__ == "__main__":
    print("Testing Iris Preprocessor Initialization...")
    preprocessor = IrisPreprocessor()
    print("Successfully instantiated Iris Preprocessor.")
