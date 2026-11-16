"""
CUMUL Website Fingerprinting - Main Launcher
==========================================
Entry point for all operations.
Panchenko et al., "Website Fingerprinting at Internet Scale", NDSS 2016

Usage:
    python cumul_wfp/main.py
    or
    python -m cumul_wfp.main
"""

import os
import sys

# Set Wireshark manuf path for Scapy
os.environ['WIRESHARK_MANUF'] = r'C:\Program Files\Wireshark\manuf'
if 'SSLKEYLOGFILE' in os.environ:
    del os.environ['SSLKEYLOGFILE']


def print_header():
    """Print application header."""
    print("=" * 60)
    print("  CUMUL Website Fingerprinting")
    print("  Panchenko et al., NDSS 2016")
    print("=" * 60)


def print_menu():
    """Print main menu."""
    print()
    print("  1. Data Collection     - Capture website fingerprints")
    print("  2. Feature Extraction - Extract CUMUL features")
    print("  3. Train Classifier   - Train SVM model")
    print("  4. Evaluate Model    - Evaluate accuracy & generate charts")
    print("  5. View Status       - Show collection status")
    print("  6. Exit")
    print()


def check_dependencies():
    """
    Check if all required dependencies are available.
    
    Returns:
        dict: Status of each dependency
    """
    deps = {}
    
    # Check NumPy
    try:
        import numpy
        deps['numpy'] = True
    except ImportError:
        deps['numpy'] = False
    
    # Check Scikit-learn
    try:
        import sklearn
        deps['sklearn'] = True
    except ImportError:
        deps['sklearn'] = False
    
    # Check Scapy
    try:
        from scapy.all import rdpcap
        deps['scapy'] = True
    except ImportError:
        deps['scapy'] = False
    
    # Check Selenium
    try:
        import selenium
        deps['selenium'] = True
    except ImportError:
        deps['selenium'] = False
    
    # Check Tor port
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 9050))
        sock.close()
        deps['tor'] = (result == 0)
    except:
        deps['tor'] = False
    
    return deps


def main():
    """Main entry point."""
    print_header()
    
    # Check dependencies
    print("\nChecking dependencies...")
    deps = check_dependencies()
    
    print("  [OK]" if deps['numpy'] else "  [MISSING] NumPy", end=" ")
    print("  [OK]" if deps['sklearn'] else "  [MISSING] Scikit-learn", end=" ")
    print("  [OK]" if deps['scapy'] else "  [MISSING] Scapy", end=" ")
    print("  [OK]" if deps['selenium'] else "  [MISSING] Selenium", end=" ")
    print("  [OK]" if deps['tor'] else "  [MISSING] Tor Proxy", end=" ")
    print()
    
    while True:
        print_menu()
        choice = input("  Select option: ").strip()
        
        if choice == '1':
            print("\n" + "=" * 60)
            print("  DATA COLLECTION")
            print("=" * 60)
            from collect.collection_menu import run as collection_run
            collection_run()
            
        elif choice == '2':
            print("\n" + "=" * 60)
            print("  FEATURE EXTRACTION")
            print("=" * 60)
            from features.extract_features import run as feature_run
            feature_run()
            
        elif choice == '3':
            print("\n" + "=" * 60)
            print("  TRAIN CLASSIFIER")
            print("=" * 60)
            from classifier.train import run as train_run
            train_run()
            
        elif choice == '4':
            print("\n" + "=" * 60)
            print("  EVALUATE MODEL")
            print("=" * 60)
            from evaluate.evaluate import run as eval_run
            eval_run()
            
        elif choice == '5':
            print("\n" + "=" * 60)
            print("  COLLECTION STATUS")
            print("=" * 60)
            from utils.show_status import run as status_run
            status_run()
            
        elif choice == '6':
            print("\nExiting...")
            break
            
        else:
            print("\n  Invalid option. Please try again.")


if __name__ == "__main__":
    main()
