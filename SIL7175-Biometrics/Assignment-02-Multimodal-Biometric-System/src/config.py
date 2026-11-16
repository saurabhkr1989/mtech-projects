import os

class Config:
    """
    Configuration definitions for the Biometric Pipeline.
    """
    
    # Base Data Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RAW_DATASET_DIR = os.path.join(BASE_DIR, "Raw Dataset")
    
    # Specific Dataset Paths
    CASIA_DIR = os.path.join(RAW_DATASET_DIR, "CASIA-Iris-Distance")
    LFW_DIR = os.path.join(RAW_DATASET_DIR, "lfw")
    IITD_DIR = os.path.join(RAW_DATASET_DIR, "IITD Database")
    BHSIG_BENGALI_DIR = os.path.join(RAW_DATASET_DIR, "BHSig260", "Bengali")
    BHSIG_HINDI_DIR = os.path.join(RAW_DATASET_DIR, "BHSig260", "Hindi")
    
    # Pipeline Parameters
    NUM_VIRTUAL_USERS = 100
    CV_FOLDS = 5
    
    # Pre-processing Parameters
    FACE_ROI_SIZE = 30
    FACE_ROI_STRIDE = 5
    NUM_FACE_ROIS = 15
    
    IRIS_NORM_W = 512
    IRIS_NORM_H = 64
    IRIS_STRIP_H = 32
    # Assignment specifies an overlapping stride of 4 pixels
    IRIS_STRIP_STRIDE = 4
    NUM_IRIS_STRIPS = 10
    
    SIG_RESIZE_W = 242
    SIG_RESIZE_H = 170
    
    # Feature Extraction (ULBP)
    ULBP_P = 8
    ULBP_R = 1
    FACE_BLOCK_SIZE = 10
    IRIS_BLOCK_SIZE = 16
    
    # Directories for Outputs
    MAPPING_FILE = os.path.join(BASE_DIR, "dataset_mapping.csv")
    FEATURES_DIR = os.path.join(BASE_DIR, "extracted_features")
    RESULTS_DIR = os.path.join(BASE_DIR, "results")
    VISUALS_DIR = os.path.join(BASE_DIR, "visualizations")

    @classmethod
    def setup_directories(cls):
        """Creates output directories if they do not exist."""
        os.makedirs(cls.FEATURES_DIR, exist_ok=True)
        os.makedirs(cls.RESULTS_DIR, exist_ok=True)
        os.makedirs(cls.VISUALS_DIR, exist_ok=True)

if __name__ == "__main__":
    Config.setup_directories()
    print("Configuration initialized and directories created.")
