"""
Feature Extraction Module
========================
Extract CUMUL features from PCAP files.
"""

import os
import sys
import glob
import json

# Set environment
os.environ['WIRESHARK_MANUF'] = r'C:\Program Files\Wireshark\manuf'
if 'SSLKEYLOGFILE' in os.environ:
    del os.environ['SSLKEYLOGFILE']

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_progress(current, total, prefix="", bar_length=40):
    """Print progress bar."""
    percent = current / total if total > 0 else 0
    filled = int(bar_length * percent)
    bar = "#" * filled + "-" * (bar_length - filled)
    sys.stdout.write(f"\r{prefix} [{bar}] {current}/{total}")
    sys.stdout.flush()


def print_step(step_num, total_steps, description):
    """Print step header."""
    print(f"\nStep {step_num}/{total_steps}: {description}")
    print("-" * 60)


def check_dependencies():
    """Check dependencies for feature extraction."""
    print_step(1, 3, "Checking dependencies")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pcap_dir = os.path.join(base_dir, "data", "raw")
    
    deps_ok = True
    
    # Check NumPy
    try:
        import numpy as np
        print("  [OK] NumPy available")
    except ImportError:
        print("  [MISSING] NumPy not found")
        deps_ok = False
    
    # Check Scapy
    try:
        from scapy.all import rdpcap
        print("  [OK] Scapy available")
    except ImportError:
        print("  [MISSING] Scapy not found")
        deps_ok = False
    
    # Check PCAP files
    pcap_files = glob.glob(os.path.join(pcap_dir, "*.pcap"))
    if pcap_files:
        print(f"  [OK] {len(pcap_files)} PCAP files found")
    else:
        print(f"  [ERROR] No PCAP files in {pcap_dir}/")
        deps_ok = False
    
    return deps_ok, pcap_files


def extract_features(pcap_files):
    """Extract features from PCAP files."""
    print_step(2, 3, "Extracting features")
    
    from features.cumul import build_feature_vector
    import numpy as np
    
    vectors = []
    labels = []
    failed = []
    
    print(f"  Processing {len(pcap_files)} files...")
    print()
    
    for i, pcap_file in enumerate(pcap_files):
        basename = os.path.basename(pcap_file)
        print_progress(i + 1, len(pcap_files), f"  Extracting")
        
        try:
            vector = build_feature_vector(pcap_file, layer='tcp')
            
            if vector is not None and len(vector) == 104:
                vectors.append(vector)
                # Extract label from filename
                label = basename.split('_')[0]
                if label == 'bg':
                    parts = basename.replace('.pcap', '').split('_')
                    label = parts[1] if len(parts) > 1 else 'unknown'
                labels.append(label)
            else:
                failed.append(basename)
                
        except Exception as e:
            failed.append(basename)
    
    print()  # Clear progress line
    
    X = np.array(vectors)
    y = np.array(labels)
    
    print(f"  Successfully extracted: {len(vectors)}")
    if failed:
        print(f"  Failed: {len(failed)}")
        for f in failed[:5]:
            print(f"    - {f}")
        if len(failed) > 5:
            print(f"    ... and {len(failed) - 5} more")
    
    return X, y


def save_features(X, y):
    """Save extracted features."""
    print_step(3, 3, "Saving features")
    
    import numpy as np
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    proc_dir = os.path.join(base_dir, "data", "processed")
    pcap_dir = os.path.join(base_dir, "data", "raw")
    
    os.makedirs(proc_dir, exist_ok=True)
    
    np.save(os.path.join(proc_dir, "features.npy"), X)
    np.save(os.path.join(proc_dir, "labels.npy"), y)
    
    print(f"  [OK] Saved features.npy ({X.shape})")
    print(f"  [OK] Saved labels.npy ({y.shape})")
    
    # Update valid traces
    pcap_files = glob.glob(os.path.join(pcap_dir, "*.pcap"))
    pcap_files = [f.replace('\\', '/') for f in pcap_files]
    pcap_files.sort()
    
    with open(os.path.join(proc_dir, "valid_traces.json"), 'w') as f:
        json.dump(pcap_files, f, indent=2)
    print(f"  [OK] Updated valid_traces.json")


def run():
    """Main feature extraction pipeline."""
    # Check dependencies
    deps_ok, pcap_files = check_dependencies()
    
    if not deps_ok:
        print("\n  [ERROR] Cannot proceed - missing dependencies")
        return
    
    # Extract features
    X, y = extract_features(pcap_files)
    
    if len(X) == 0:
        print("\n  [ERROR] No features extracted!")
        return
    
    # Save features
    save_features(X, y)
    
    # Summary
    print("\n" + "=" * 60)
    print("  FEATURE EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"  Total samples: {len(X)}")
    print(f"  Features per sample: {X.shape[1]}")
    print(f"  Unique classes: {len(set(y))}")
    print("=" * 60)


if __name__ == "__main__":
    run()
