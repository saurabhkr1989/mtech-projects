import os
import glob
import pandas as pd
import random
from collections import defaultdict
import sys

# Append the src directory to sys.path so we can import config
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.append(src_dir)
from config import Config

def collect_subject_samples(base_path, extension="*.*", is_lfw=False):
    """
    Returns a dictionary mapping a Subject_ID -> list of file paths.
    """
    subject_map = defaultdict(list)
    if not os.path.exists(base_path):
        return subject_map
        
    for sub_dir in sorted(os.listdir(base_path)):
        sub_dir_path = os.path.join(base_path, sub_dir)
        if os.path.isdir(sub_dir_path):
            files = glob.glob(os.path.join(sub_dir_path, extension))
            # Optional filtering if needed
            valid_files = [f for f in files if f.lower().endswith(('.jpg', '.png', '.bmp', '.tif', '.jpeg'))]
            if valid_files:
                subject_map[sub_dir] = valid_files
    return subject_map

def map_chimeric_dataset_1():
    print("Mapping Dataset 1 (CASIA Face + CASIA Iris + BHSig Bengali)...")
    casia_face = collect_subject_samples(Config.CASIA_DIR)
    casia_iris = casia_face # Dataset 1 uses same CASIA subset
    bhsig_bengali = collect_subject_samples(Config.BHSIG_BENGALI_DIR)
    
    # We must construct 100 Virtual Users
    casia_keys = sorted(list(casia_face.keys()))[:100]
    bhsig_keys = sorted(list(bhsig_bengali.keys()))[:100]
    
    dataset_1_records = []
    
    for i in range(100):
        # Get available user directories per modality
        c_key = casia_keys[i]
        b_key = bhsig_keys[i]
        
        # Calculate N: minimum samples across all 3 traits
        n_face = len(casia_face[c_key])
        n_iris = len(casia_iris[c_key])
        n_sig = len(bhsig_bengali[b_key])
        
        N = min(n_face, n_iris, n_sig)
        
        dataset_1_records.append({
            "Virtual_User_ID": f"User_D1_{i+1:03d}",
            "Face_Source_ID": c_key,
            "Iris_Source_ID": c_key,
            "Signature_Source_ID": b_key,
            "Min_Samples_N": N,
            "Dataset": "Dataset_1"
        })
        
    return dataset_1_records

from src.preprocessing.face_preprocessor import FacePreprocessor

def map_chimeric_dataset_2():
    print("Mapping Dataset 2 (LFW Face + IITD Iris + BHSig Hindi)...")
    lfw_face = collect_subject_samples(Config.LFW_DIR)
    iitd_iris = collect_subject_samples(Config.IITD_DIR)
    bhsig_hindi = collect_subject_samples(Config.BHSIG_HINDI_DIR)
    
    # Filter LFW to only subjects with >= 5 extractable faces (for 5-fold CV)
    print("  Pre-filtering LFW subjects to ensure strictly >= 5 extractable faces per subject...")
    preprocessor = FacePreprocessor()
    lfw_valid_keys = []
    
    for k, v in lfw_face.items():
        if len(v) < 5:
            continue
            
        success_count = 0
        for img_path in sorted(v):
            try:
                res = preprocessor.extract_rois(img_path)
                if res is not None:
                    success_count += 1
            except Exception:
                pass
            
            # Optimization: break early if we hit 5 successes
            if success_count >= 5:
                break
                
        if success_count >= 5:
            lfw_valid_keys.append(k)
            
        if len(lfw_valid_keys) == 100:
            break
    
    # Ensure we have at least 100
    if len(lfw_valid_keys) < 100:
        print(f"WARNING: Found only {len(lfw_valid_keys)} LFW subjects with >= 5 extractable images.")
    
    lfw_keys = sorted(lfw_valid_keys)[:100]
    iitd_keys = sorted(list(iitd_iris.keys()))[:100]
    bhsig_keys = sorted(list(bhsig_hindi.keys()))[:100]
    
    dataset_2_records = []
    
    for i in range(100):
        l_key = lfw_keys[i]
        iit_key = iitd_keys[i]
        b_key = bhsig_keys[i]
        
        n_face = len(lfw_face[l_key])
        n_iris = len(iitd_iris[iit_key])
        n_sig = len(bhsig_hindi[b_key])
        
        N = min(n_face, n_iris, n_sig)
        
        dataset_2_records.append({
            "Virtual_User_ID": f"User_D2_{i+1:03d}",
            "Face_Source_ID": l_key,
            "Iris_Source_ID": iit_key,
            "Signature_Source_ID": b_key,
            "Min_Samples_N": N,
            "Dataset": "Dataset_2"
        })
        
    return dataset_2_records

def generate_full_mapping():
    Config.setup_directories()
    
    d1_records = map_chimeric_dataset_1()
    d2_records = map_chimeric_dataset_2()
    
    all_records = d1_records + d2_records
    
    df = pd.DataFrame(all_records)
    
    # Save the mapping to the root directory as per assignment instruction
    df.to_csv(Config.MAPPING_FILE, index=False)
    print(f"Successfully generated mapping file at {Config.MAPPING_FILE}")
    print(df.head())

if __name__ == "__main__":
    generate_full_mapping()
