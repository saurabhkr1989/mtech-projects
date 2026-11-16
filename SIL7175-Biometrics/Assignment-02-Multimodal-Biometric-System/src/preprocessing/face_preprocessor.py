import os
import cv2
import numpy as np
import dlib
from sys import path

# Ensure we can import config
path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import Config


class FacePreprocessor:
    """
    Handles Face Modality Pre-processing.
    1. Detects facial landmarks using DLIB shape predictor or Haar cascades.
    2. Extracts overlapping sub-regions (30x30 pixels).
    3. Applies Histogram Equalization and Mean-Variance normalization.
    """
    def __init__(self):
        self.predictor_path = os.path.join(Config.BASE_DIR, "resources", "shape_predictor_68_face_landmarks.dat")

        self.dlib_detector = dlib.get_frontal_face_detector()
        if not os.path.exists(self.predictor_path):
            raise FileNotFoundError(
                f"Strict Assignment Requirement: {self.predictor_path} not found. "
                "Please run download_dlib_model.py first."
            )
        self.dlib_predictor = dlib.shape_predictor(self.predictor_path)

        # Haar eye cascade: fallback for near-infrared CASIA images where DLib HOG fails.
        eye_cascade_xml = cv2.data.haarcascades + 'haarcascade_eye.xml'
        self.eye_cascade = cv2.CascadeClassifier(eye_cascade_xml)

    def _build_face_rect_from_eyes(self, eyes, img_shape):
        """
        Given two eye bounding boxes (x, y, w, h), estimate the face bounding rect.
        The face is assumed to span from slightly above the top eye to below the chin,
        and horizontally from left-eye-left to right-eye-right.
        Returns a dlib.rectangle.
        """
        # Sort eyes left-to-right by x coordinate
        eyes_sorted = sorted(eyes[:2], key=lambda e: e[0])
        left_eye = eyes_sorted[0]
        right_eye = eyes_sorted[1]

        # Eye center points
        lx, ly = left_eye[0] + left_eye[2] // 2, left_eye[1] + left_eye[3] // 2
        rx, ry = right_eye[0] + right_eye[2] // 2, right_eye[1] + right_eye[3] // 2

        # Inter-ocular distance
        eye_distance = abs(rx - lx)

        # Estimate face bounding box using standard facial geometry ratios.
        face_left   = max(0, lx - int(eye_distance * 0.7))
        face_right  = min(img_shape[1], rx + int(eye_distance * 0.7))
        face_top    = max(0, min(ly, ry) - int(eye_distance * 0.8))
        face_bottom = min(img_shape[0], max(ly, ry) + int(eye_distance * 2.0))

        return dlib.rectangle(face_left, face_top, face_right, face_bottom)

    def enhance_roi(self, roi):
        """Applies Histogram Equalization followed by Mean-Variance normalization."""
        if len(roi.shape) == 3:
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray_roi = roi

        eq_roi = cv2.equalizeHist(gray_roi)

        float_roi = eq_roi.astype(np.float32)
        mean, std = cv2.meanStdDev(float_roi)
        std = max(std[0][0], 1e-6)
        norm_roi = (float_roi - mean[0][0]) / std

        return eq_roi, norm_roi

    def extract_rois(self, image_path):
        """
        Extracts 15 landmark-centered regions of 30x30 pixels.
        Returns a list of 15 enhanced and normalized ROI matrices.
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image at {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_h, img_w = gray.shape[:2]

        # --- Stage 1: Locate face rectangle ---
        # Strategy A: Try DLib directly on a scaled version
        scale = 0.25 if img_h > 1000 else 1.0
        detect_gray = cv2.resize(gray, (0, 0), fx=scale, fy=scale) if scale != 1.0 else gray

        face_rect = None
        dlib_faces = self.dlib_detector(detect_gray, 1)

        if len(dlib_faces) > 0:
            raw_rect = dlib_faces[0]
            if scale != 1.0:
                face_rect = dlib.rectangle(
                    int(raw_rect.left()   / scale),
                    int(raw_rect.top()    / scale),
                    int(raw_rect.right()  / scale),
                    int(raw_rect.bottom() / scale)
                )
            else:
                face_rect = raw_rect

        else:
            # Strategy B: Use Haar Eye Cascade to estimate face bounding box
            detect_for_eyes = cv2.resize(gray, (0, 0), fx=scale, fy=scale) if scale != 1.0 else gray
            eyes = self.eye_cascade.detectMultiScale(
                detect_for_eyes, scaleFactor=1.1, minNeighbors=3, minSize=(15, 15)
            )

            if len(eyes) >= 2:
                # Scale eye coordinates back to full-res
                if scale != 1.0:
                    eyes = [(int(x/scale), int(y/scale), int(w/scale), int(h/scale))
                            for (x, y, w, h) in eyes]
                face_rect = self._build_face_rect_from_eyes(eyes, gray.shape)
            else:
                raise ValueError(
                    f"Strict Requirement: Could not locate face or eyes in {image_path}. "
                    "DLib HOG and Haar Eye Cascade both failed."
                )

        # --- Stage 2: Extract 68 landmarks using DLIB on the located face region ---
        shape = self.dlib_predictor(gray, face_rect)

        # 15 landmark indices covering eyes, nose, mouth, and jaw regions
        key_indices = [36, 39, 42, 45, 27, 30, 31, 35, 48, 51, 54, 57, 0, 8, 16]

        rois = []
        half_size = Config.FACE_ROI_SIZE // 2

        for idx in key_indices:
            pt = shape.part(idx)
            x, y = pt.x, pt.y

            x1 = max(0, x - half_size)
            y1 = max(0, y - half_size)
            x2 = min(img_w, x + half_size)
            y2 = min(img_h, y + half_size)

            # Skip degenerate crops
            if (x2 - x1) <= 0 or (y2 - y1) <= 0:
                continue

            crop = gray[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            crop = cv2.resize(crop, (Config.FACE_ROI_SIZE, Config.FACE_ROI_SIZE))
            _, norm_roi = self.enhance_roi(crop)
            rois.append(norm_roi)

        if len(rois) == 0:
            raise ValueError(f"No valid ROIs could be extracted from {image_path}.")

        # Pad with copies if fewer than 15 survived boundary checks
        while len(rois) < Config.NUM_FACE_ROIS:
            rois.append(rois[-1])

        return rois[:Config.NUM_FACE_ROIS]


if __name__ == "__main__":
    print("Testing Face Preprocessor Initialization...")
    preprocessor = FacePreprocessor()
    print("Successfully instantiated Face Preprocessor.")
