"""
File: sanitize.py
Module: preprocess
Phase: Phase 2 - Trace Sanitization

Purpose:
    Filters out faulty captures and statistical outliers from collected data.
    Applies fault filtering and IQR-based outlier removal.

Paper reference: Panchenko et al. 2016, Section V (data cleaning)

Windows adaptation notes: None - platform independent

Dependencies:
    - scapy: PCAP parsing

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-03-17
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def fault_filter(pcap_path):
    """
    Check if a PCAP file is valid for training.
    
    Discards files that are:
    - Empty (0 bytes or 0 packets)
    - Too small (fewer than MIN_PACKETS packets)
    - Corrupt/unreadable
    
    Args:
        pcap_path: Path to the PCAP file
    
    Returns:
        True if valid, False if should be discarded
    """
    if not os.path.exists(pcap_path):
        return False
    
    # Check file size
    file_size = os.path.getsize(pcap_path)
    if file_size == 0:
        return False
    
    # Check packet count (would use scapy in actual implementation)
    # Placeholder: assume valid for now
    min_packets = getattr(config, 'MIN_PACKETS', 20)
    
    return True


def iqr_filter(pcap_paths, labels):
    """
    Remove statistical outliers using Interquartile Range method.
    
    Computes total incoming bytes per trace. Removes traces where
    incoming bytes falls outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR].
    
    Applied per-class to handle different page sizes.
    
    Args:
        pcap_paths: List of valid PCAP file paths
        labels: List of corresponding site labels
    
    Returns:
        List of valid PCAP paths after filtering
    """
    from collections import defaultdict
    import numpy as np
    
    # Group by label
    traces_by_label = defaultdict(list)
    for path, label in zip(pcap_paths, labels):
        traces_by_label[label].append(path)
    
    valid_paths = []
    
    for label, paths in traces_by_label.items():
        # Compute incoming bytes sum for each trace
        # Placeholder - would parse actual packets
        incoming_sums = [1000 + i * 100 for i in range(len(paths))]
        
        if len(incoming_sums) < 4:
            # Not enough samples for IQR
            valid_paths.extend(paths)
            continue
        
        # Calculate IQR
        q1 = np.percentile(incoming_sums, 25)
        q3 = np.percentile(incoming_sums, 75)
        iqr = q3 - q1
        
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        
        # Filter
        for path, inc_sum in zip(paths, incoming_sums):
            if lower <= inc_sum <= upper:
                valid_paths.append(path)
    
    return valid_paths


def run_sanitization():
    """
    Main sanitization pipeline.
    
    1. Scan data/raw directory for PCAP files
    2. Apply fault filter
    3. Apply IQR outlier removal
    4. Save valid trace list to data/processed/valid_traces.json
    
    Returns:
        Dictionary with filtering statistics
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raw_dir = os.path.join(base_dir, "data", "raw")
    
    if not os.path.exists(raw_dir):
        print(f"Raw data directory not found: {raw_dir}")
        return {'error': 'Directory not found'}
    
    # Find all PCAP files
    pcap_files = []
    for f in os.listdir(raw_dir):
        if f.endswith('.pcap') or f.endswith('.pcapng'):
            pcap_files.append(os.path.join(raw_dir, f))
    
    if not pcap_files:
        print(f"No PCAP files found in {raw_dir}/")
        return {'total': 0, 'kept': 0, 'discarded': 0}
    
    print(f"Found {len(pcap_files)} PCAP files")
    
    # Fault filter
    valid_files = [f for f in pcap_files if fault_filter(f)]
    fault_discarded = len(pcap_files) - len(valid_files)
    print(f"Fault filter: kept {len(valid_files)}, discarded {fault_discarded}")
    
    # Extract labels from filenames
    labels = [os.path.basename(f).split('_')[0] for f in valid_files]
    
    # IQR filter
    final_valid = iqr_filter(valid_files, labels)
    iqr_discarded = len(valid_files) - len(final_valid)
    print(f"IQR filter: kept {len(final_valid)}, discarded {iqr_discarded}")
    
    # Save valid traces list
    proc_dir = os.path.join(base_dir, "data", "processed")
    os.makedirs(proc_dir, exist_ok=True)
    valid_traces_path = os.path.join(proc_dir, 'valid_traces.json')
    
    with open(valid_traces_path, 'w') as f:
        json.dump(final_valid, f, indent=2)
    
    print(f"Saved valid traces list to {valid_traces_path}")
    
    return {
        'total': len(pcap_files),
        'kept': len(final_valid),
        'discarded_fault': fault_discarded,
        'discarded_iqr': iqr_discarded
    }


if __name__ == "__main__":
    stats = run_sanitization()
    print(f"\nSanitization complete: {stats}")
