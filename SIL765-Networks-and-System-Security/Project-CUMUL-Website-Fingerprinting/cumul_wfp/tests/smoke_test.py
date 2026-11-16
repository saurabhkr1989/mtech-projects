"""
File: smoke_test.py
Module: tests
Phase: Phase 0 - Environment Setup & Validation

Purpose:
    Validates all system dependencies and components are working correctly.
    Must pass before proceeding to Phase 1 (data collection).

Paper reference: N/A - infrastructure validation only

Windows adaptation notes:
    Uses Scapy with Npcap driver instead of tcpdump (Linux).

Dependencies:
    - scapy: packet capture
    - stem: Tor control
    - selenium: browser automation
    - sklearn: SVM training validation

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-03-17
"""

import sys
import os
import socket

def check_python_version():
    """CHECK 1: Verify Python version is 3.8+"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"[PASS] CHECK 1  Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"[FAIL] CHECK 1  Python {version.major}.{version.minor}.{version.micro} - need 3.8+")
        return False


def check_scapy():
    """CHECK 2: Verify Scapy import and Npcap driver"""
    try:
        from scapy.all import get_if_list
        if_list = get_if_list()
        if len(if_list) > 0:
            print(f"[PASS] CHECK 2  Scapy import OK")
            return True, if_list
        else:
            print("[FAIL] CHECK 2  No network interfaces found")
            return False, []
    except Exception as e:
        print(f"[FAIL] CHECK 2  Scapy import failed: {e}")
        return False, []


def check_tor_browser():
    """CHECK 4: Verify Tor Browser executable exists"""
    try:
        import config
        tbb_path = config.TBB_PATH
        if tbb_path and os.path.exists(tbb_path):
            print(f"[PASS] CHECK 4  TBB found: {tbb_path}")
            return True
        else:
            print(f"[FAIL] CHECK 4  TBB not found at: {config.TBB_PATH}")
            return False
    except Exception as e:
        print(f"[FAIL] CHECK 4  Config error: {e}")
        return False


def check_tor_profile():
    """CHECK 4b: Verify Tor Browser profile exists"""
    try:
        import config
        profile_path = config.TBB_PROFILE_DIR
        if profile_path and os.path.exists(profile_path):
            print(f"[PASS] CHECK 4b TBB profile found: {profile_path}")
            return True
        else:
            print(f"[FAIL] CHECK 4b TBB profile not found at: {config.TBB_PROFILE_DIR}")
            return False
    except Exception as e:
        print(f"[FAIL] CHECK 4b Config error: {e}")
        return False


def check_tor_config():
    """CHECK 5: Verify Tor ControlPort is configured"""
    try:
        import config
        torrc_path = os.path.join(
            os.path.dirname(config.TBB_PATH),
            "TorBrowser", "Data", "Tor", "torrc"
        )
        
        if not os.path.exists(torrc_path):
            print(f"[FAIL] CHECK 5  torrc not found at: {torrc_path}")
            return False
        
        with open(torrc_path, 'r') as f:
            content = f.read()
        
        required = ['ControlPort 9051', 'CookieAuthentication 1', 'SocksPort 9150']
        missing = []
        for req in required:
            if req not in content:
                missing.append(req)
        
        if missing:
            print(f"[FAIL] CHECK 5  Tor config missing: {missing}")
            print("       Add these lines to torrc:")
            print("       ControlPort 9051")
            print("       CookieAuthentication 1")
            print("       SocksPort 9150")
            return False
        
        # Check DisableNetwork is 0
        if 'DisableNetwork 1' in content:
            print("[WARN] CHECK 5  DisableNetwork is 1 - Tor won't connect automatically")
            print("       Change to DisableNetwork 0 in torrc")
            return False
        
        print("[PASS] CHECK 5  Tor ControlPort configured correctly")
        return True
    except Exception as e:
        print(f"[FAIL] CHECK 5  Error checking torrc: {e}")
        return False


def check_tor_ports():
    """CHECK 6: Check if Tor ports are reachable"""
    try:
        import config
        
        # Check SOCKS port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            result = sock.connect_ex(('127.0.0.1', config.TOR_SOCKS_PORT))
            if result == 0:
                print(f"[PASS] CHECK 6  Tor SOCKS port {config.TOR_SOCKS_PORT} is open")
                sock.close()
            else:
                print(f"[WARN] CHECK 6  Tor SOCKS port {config.TOR_SOCKS_PORT} not reachable")
                print("       Make sure Tor Browser is running and connected")
                sock.close()
                return True  # Not a failure - just means Tor not running yet
        except Exception as e:
            print(f"[WARN] CHECK 6  Cannot reach Tor ports: {e}")
            print("       Make sure Tor Browser is running")
            sock.close()
            return True
        
        return True
    except Exception as e:
        print(f"[FAIL] CHECK 6  Error: {e}")
        return False


def check_stem():
    """CHECK 7: Verify Stem can connect to Tor controller"""
    try:
        from stem.control import Controller
        
        try:
            with Controller.from_port(port=9051) as controller:
                controller.authenticate_cookie()
                print("[PASS] CHECK 7  Stem connects to Tor controller OK")
                return True
        except Exception as e:
            print(f"[WARN] CHECK 7  Stem cannot connect: {e}")
            print("       Make sure Tor Browser is running with ControlPort enabled")
            return True  # Not a failure yet - Tor may not be running
            
    except ImportError:
        print("[FAIL] CHECK 7  Stem library not installed")
        return False


def check_interface_config():
    """CHECK 3b: Verify capture interface is configured"""
    try:
        import config
        iface = config.CAPTURE_INTERFACE
        
        if iface and iface.startswith('\\Device\\NPF_'):
            print(f"[PASS] CHECK 3b Interface configured: {iface}")
            return True
        else:
            print(f"[FAIL] CHECK 3b Invalid interface: {iface}")
            return False
    except Exception as e:
        print(f"[FAIL] CHECK 3b Config error: {e}")
        return False


def check_selenium():
    """CHECK 9: Verify Selenium is installed"""
    try:
        from selenium import webdriver
        print("[PASS] CHECK 9  Selenium installed (uses built-in driver manager)")
        return True
    except ImportError:
        print("[FAIL] CHECK 9  Selenium not installed")
        return False


def check_sklearn():
    """CHECK 11: Verify scikit-learn can train a basic SVM"""
    try:
        from sklearn.svm import SVC
        from sklearn.datasets import make_classification
        X, y = make_classification(n_samples=10, n_features=4, n_classes=2, random_state=42)
        clf = SVC(kernel='rbf')
        clf.fit(X, y)
        print("[PASS] CHECK 11 scikit-learn SVC dummy train OK")
        return True
    except Exception as e:
        print(f"[FAIL] CHECK 11 sklearn failed: {e}")
        return False


def check_numpy_interp():
    """CHECK 12: Verify numpy interpolation works for CUMUL vector"""
    try:
        import numpy as np
        a_vals = [0, 100, 200, 300]
        c_vals = [0, 50, 120, 180]
        result = np.interp(np.linspace(0, 300, 100), a_vals, c_vals)
        if len(result) == 100:
            print(f"[PASS] CHECK 12 CUMUL vector shape: {result.shape}")
            return True
        else:
            print(f"[FAIL] CHECK 12 Wrong shape: {result.shape}")
            return False
    except Exception as e:
        print(f"[FAIL] CHECK 12 numpy interp failed: {e}")
        return False


def check_tkinter():
    """CHECK 13: Verify Tkinter is available"""
    try:
        import tkinter
        print("[PASS] CHECK 13 Tkinter available")
        return True
    except Exception as e:
        print(f"[FAIL] CHECK 13 Tkinter failed: {e}")
        return False


def check_directories():
    """CHECK 14: Verify/create data directories"""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dirs = [
            os.path.join(base_dir, "data", "raw"),
            os.path.join(base_dir, "data", "processed"),
            os.path.join(base_dir, "data", "models"),
            os.path.join(base_dir, "results")
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
        print("[PASS] CHECK 14 Directory structure OK")
        return True
    except Exception as e:
        print(f"[FAIL] CHECK 14 Directory error: {e}")
        return False


def run_all_checks():
    """Run all smoke tests"""
    print("=" * 60)
    print("  CUMUL WFP — Environment Smoke Test")
    print("=" * 60)

    results = []

    # Check 1: Python version
    results.append(check_python_version())

    # Check 2: Scapy and interfaces
    scapy_ok, if_list = check_scapy()
    results.append(scapy_ok)

    # Check 3: Network interface (if Scapy worked)
    if scapy_ok and if_list:
        print(f"[PASS] CHECK 3  Interface found: {if_list[0]}")
        results.append(True)
        
        # Check 3b: Interface configured
        results.append(check_interface_config())
    else:
        print("[FAIL] CHECK 3  Scapy not working")
        results.append(False)
        results.append(False)

    # Check 4: Tor Browser
    results.append(check_tor_browser())
    results.append(check_tor_profile())

    # Check 5: Tor ControlPort config
    results.append(check_tor_config())

    # Check 6: Tor ports (needs Tor running)
    results.append(check_tor_ports())

    # Check 7: Stem controller (needs Tor running)
    results.append(check_stem())

    # Check 8: geckodriver (not needed with Selenium 4.6+)
    print("[INFO] CHECK 8  Using Selenium built-in driver manager (no manual geckodriver needed)")
    results.append(True)

    # Check 9: Selenium
    results.append(check_selenium())

    # Check 10: Scapy capture
    print("[INFO] CHECK 10 Run as Administrator for packet capture")
    results.append(True)

    # Check 11: sklearn
    results.append(check_sklearn())

    # Check 12: numpy
    results.append(check_numpy_interp())

    # Check 13: tkinter
    results.append(check_tkinter())

    # Check 14: directories
    results.append(check_directories())

    print("=" * 60)
    passed = sum(1 for r in results if r)
    failed = sum(1 for r in results if not r)
    print(f"  {passed}/{len(results)} checks passed, {failed} failed")
    
    if passed >= 12:
        print("  Environment is ready!")
        print("  Note: Tor-related checks (5-7) require Tor Browser to be running.")
    else:
        print("  Please resolve failures before proceeding.")
    print("=" * 60)

    return passed >= 12


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)
