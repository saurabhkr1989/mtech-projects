"""
File: cumul.py
Module: features
Phase: Phase 3 - Feature Extraction (CUMUL Core)

Purpose:
    Implements the CUMUL feature extraction algorithm from the paper.
    Converts packet sequences into 104-dimensional feature vectors.

Paper reference:
    Panchenko et al., "Website Fingerprinting at Internet Scale", NDSS 2016.
    Section VI: C(T) cumulative representation

Windows adaptation notes: None - pure mathematical implementation

Dependencies:
    - numpy: Numerical computations

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-03-17
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def build_cumulative(T):
    """
    Build cumulative representation C(T) from signed packet sequence.
    
    Implements the CUMUL algorithm from Section VI of the paper:
        C(T) = ((0,0), (a1,c1), ..., (aN,cN))
    
    where:
        c1 = p1,          a1 = |p1|
        ci = c(i-1) + pi, ai = a(i-1) + |pi|   for i = 2..N
    
    The 'a' axis represents total bytes transferred (x-axis).
    The 'c' axis represents cumulative signed sum (y-axis).
    
    Args:
        T: List of signed packet sizes (positive=incoming, negative=outgoing)
    
    Returns:
        Tuple of (a_vals, c_vals) arrays
    """
    if not T:
        return [], []
    
    n = len(T)
    a_vals = [0.0] * (n + 1)
    c_vals = [0.0] * (n + 1)
    
    # Starting point (0, 0)
    a_vals[0] = 0.0
    c_vals[0] = 0.0
    
    # Build cumulative sums
    for i in range(1, n + 1):
        pi = T[i - 1]
        c_vals[i] = c_vals[i - 1] + pi
        a_vals[i] = a_vals[i - 1] + abs(pi)
    
    return a_vals, c_vals


def sample_features(a_vals, c_vals, n_points=100):
    """
    Sample the cumulative curve at equidistant points.
    
    Uses piecewise linear interpolation to sample the C(T) curve
    at n_points equidistant positions along the 'a' (bytes) axis.
    
    This normalizes variable-length traces to fixed-length vectors.
    
    Args:
        a_vals: List of cumulative bytes values (x-axis)
        c_vals: List of cumulative signed sums (y-axis)
        n_points: Number of interpolation points (default: 100)
    
    Returns:
        List of n_points sampled c values
    """
    if not a_vals or not c_vals:
        return [0.0] * n_points
    
    # Sample points along the a-axis
    a_max = a_vals[-1]
    if a_max == 0:
        return [0.0] * n_points
    
    sample_points = np.linspace(0, a_max, n_points)
    
    # Interpolate c values at sample points
    sampled = np.interp(sample_points, a_vals, c_vals)
    
    return sampled.tolist()


def extract_global_stats(T):
    """
    Extract global statistics from packet sequence.
    
    Returns four global features that complement the interpolated
    cumulative representation:
        Nin  - count of incoming packets
        Nout - count of outgoing packets  
        Sin  - sum of incoming packet sizes
        Sout - sum of outgoing packet sizes
    
    Args:
        T: List of signed packet sizes
    
    Returns:
        Tuple (Nin, Nout, Sin, Sout)
    """
    nin = sum(1 for p in T if p > 0)
    nout = sum(1 for p in T if p < 0)
    sin = sum(p for p in T if p > 0)
    sout = sum(abs(p) for p in T if p < 0)
    
    return nin, nout, sin, sout


def build_feature_vector(pcap_path, layer='cells'):
    """
    Full CUMUL feature extraction pipeline.
    
    1. Parse PCAP file into signed packet sequence
    2. Build cumulative representation C(T)
    3. Sample at n_points (100) equidistant positions
    4. Extract global statistics
    5. Concatenate into 104-dimensional vector
    
    Args:
        pcap_path: Path to PCAP file
        layer: Extraction layer ('tcp', 'tls', or 'cells')
    
    Returns:
        numpy array of shape (104,)
    
    Vector layout:
        [0:100]   = 100 interpolated cumulative sum samples
        [100]     = Nin (incoming packet count)
        [101]     = Nout (outgoing packet count)
        [102]     = Sin (total incoming bytes)
        [103]     = Sout (total outgoing bytes)
    """
    # Parse PCAP to get signed packet sequence
    T = parse_pcap(pcap_path, layer)
    
    if not T or len(T) < 10:
        # Return zero vector for invalid/empty traces
        return np.zeros(104)
    
    # Build cumulative representation
    a_vals, c_vals = build_cumulative(T)
    
    # Sample features
    n_points = getattr(config, 'N_FEATURES', 100)
    sampled = sample_features(a_vals, c_vals, n_points)
    
    # Get global statistics
    nin, nout, sin, sout = extract_global_stats(T)
    
    # Combine into 104-dim vector
    global_stats = [nin, nout, sin, sout]
    vector = np.array(sampled + global_stats, dtype=np.float64)
    
    return vector


def parse_pcap(pcap_path, layer='cells'):
    """
    Parse PCAP file into signed packet size sequence.
    
    Args:
        pcap_path: Path to PCAP file
        layer: Extraction layer ('tcp', 'tls', or 'cells')
    
    Returns:
        List of signed packet sizes
    """
    try:
        from scapy.all import rdpcap, TCP, IP
        packets = rdpcap(pcap_path)
        
        T = []
        for pkt in packets:
            if layer == 'cells':
                # Tor cells are 512 bytes
                if hasattr(pkt, 'load'):
                    size = len(pkt.load)
                    if size == 512:
                        T.append(size)
            else:
                # TCP layer - use all TCP packet sizes (no port filtering)
                if TCP in pkt and IP in pkt:
                    size = len(pkt['TCP'].payload)
                    if size > 0:
                        # Positive = incoming (server -> client)
                        # Negative = outgoing (client -> server)
                        direction = 1 if pkt['IP'].dst == '127.0.0.1' else -1
                        T.append(direction * size)
        
        return T
    except Exception as e:
        print(f"Error parsing {pcap_path}: {e}")
        return []


def extract_all_features(pcap_dir, output_path):
    """
    Extract features from all PCAP files in a directory.
    
    Args:
        pcap_dir: Directory containing PCAP files
        output_path: Path to save feature matrix
    
    Returns:
        Tuple (X, y, labels) where:
            X: Feature matrix (n_samples, 104)
            y: Label array
            labels: List of site labels
    """
    import os
    
    if not os.path.exists(pcap_dir):
        print(f"Directory not found: {pcap_dir}")
        return None, None, None
    
    pcap_files = [f for f in os.listdir(pcap_dir) 
                  if f.endswith('.pcap') or f.endswith('.pcapng')]
    
    if not pcap_files:
        print("No PCAP files found")
        return None, None, None
    
    print(f"Extracting features from {len(pcap_files)} files...")
    
    vectors = []
    labels = []
    
    layer = getattr(config, 'EXTRACTION_LAYER', 'cells')
    
    for i, pcap_file in enumerate(pcap_files):
        if (i + 1) % 10 == 0:
            print(f"  Processed {i+1}/{len(pcap_files)}")
        
        pcap_path = os.path.join(pcap_dir, pcap_file)
        vector = build_feature_vector(pcap_path, layer)
        vectors.append(vector)
        
        # Extract label from filename (e.g., "reddit_com_001.pcap" -> "reddit_com")
        label = pcap_file.split('_')[0]
        labels.append(label)
    
    X = np.array(vectors)
    y = np.array(labels)
    
    print(f"Feature extraction complete: X.shape = {X.shape}")
    
    # Save to disk
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    np.save(output_path, X)
    
    # Save labels
    label_path = output_path.replace('.npy', '_labels.npy')
    np.save(label_path, y)
    
    print(f"Saved features to {output_path}")
    print(f"Saved labels to {label_path}")
    
    return X, y, labels


if __name__ == "__main__":
    # Test CUMUL with dummy data
    print("Testing CUMUL feature extraction...")
    
    # Create dummy packet sequence
    dummy_packets = [
        -512, -512, -512,  # Client requests (outgoing)
        1024, 2048, 512,   # Server responses (incoming)
        -256, -256,        # Client ACKs
        1500, 1500, 1500,  # More data
        -100, -100         # Final ACKs
    ]
    
    a_vals, c_vals = build_cumulative(dummy_packets)
    print(f"Cumulative points: {len(a_vals)}")
    
    sampled = sample_features(a_vals, c_vals, 100)
    print(f"Sampled points: {len(sampled)}")
    
    nin, nout, sin, sout = extract_global_stats(dummy_packets)
    print(f"Global stats: Nin={nin}, Nout={nout}, Sin={sin}, Sout={sout}")
    
    vector = np.array(sampled + [nin, nout, sin, sout])
    print(f"Feature vector shape: {vector.shape}")
    print("CUMUL test complete!")
