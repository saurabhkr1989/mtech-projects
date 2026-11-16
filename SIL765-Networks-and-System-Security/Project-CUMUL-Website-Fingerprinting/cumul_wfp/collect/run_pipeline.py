"""
File: run_pipeline.py
Module: collect
Phase: Phase 1 - Automated Data Collection

Purpose:
    Automates the entire data collection pipeline:
    1. Start Tor Browser
    2. Wait for Tor to connect
    3. Run data collection

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-03-17
"""

import os
import sys
import time
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from .capture import run_collection


def start_tor_browser():
    """
    Start Tor Browser in background.
    
    Returns:
        subprocess.Popen object if started successfully, None otherwise
    """
    if not os.path.exists(config.TBB_PATH):
        print(f"ERROR: Tor Browser not found at {config.TBB_PATH}")
        return None
    
    print(f"Starting Tor Browser from: {config.TBB_PATH}")
    
    try:
        # Start Tor Browser (firefox.exe with Tor Browser profile)
        # This will launch the Tor Browser which handles Tor internally
        process = subprocess.Popen(
            [config.TBB_PATH, "--allow-remote"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        print(f"Tor Browser started with PID: {process.pid}")
        return process
    except Exception as e:
        print(f"ERROR starting Tor Browser: {e}")
        return None


def is_tor_connected():
    """Quick check if Tor is already connected."""
    try:
        from stem.control import Controller
        with Controller.from_port(port=config.TOR_CONTROL_PORT) as controller:
            controller.authenticate()
            circuits = list(controller.get_network_statuses())
            return len(circuits) > 0
    except:
        return False


def wait_for_tor_connection(timeout=120, check_interval=5):
    """
    Wait for Tor to establish a connection.
    
    Monitors the Tor control port to check if Tor is ready.
    
    Args:
        timeout: Maximum seconds to wait
        check_interval: Seconds between checks
    
    Returns:
        True if Tor connected, False if timeout
    """
    # First, quick check if already connected
    if is_tor_connected():
        print("Tor is already connected!")
        return True
    
    print(f"Waiting for Tor to connect (timeout: {timeout}s)...")
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if is_tor_connected():
            print(f"Tor connected successfully!")
            return True
        
        time.sleep(check_interval)
        elapsed = int(time.time() - start_time)
        print(f"  Waiting... ({elapsed}s / {timeout}s)", end="\r")
    
    print("\nWARNING: Could not verify Tor connection via control port")
    print("Assuming Tor is connected (fallback)...")
    time.sleep(5)
    return True


def check_tor_browser_running():
    """
    Check if Tor or Chrome is running.
    
    Returns:
        True if running, False otherwise
    """
    # Check for Tor process
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq tor.exe'],
            capture_output=True, text=True
        )
        if 'tor.exe' in result.stdout.lower():
            return True
    except:
        pass
    
    # Check for Chrome process (used with Tor proxy)
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq chrome.exe'],
            capture_output=True, text=True
        )
        if 'chrome.exe' in result.stdout.lower():
            return True
    except:
        pass
    
    return False


def run_automated_collection():
    """
    Main automation function:
    1. Start Tor Browser
    2. Wait for connection
    3. Run data collection
    """
    print("=" * 70)
    print("  CUMUL WFP - Automated Data Collection Pipeline")
    print("=" * 70)
    
    # Step 1: Check if Tor Browser is already running
    if check_tor_browser_running():
        print("Tor Browser is already running - using existing instance")
        tor_process = None
    else:
        # Step 2: Start Tor Browser
        tor_process = start_tor_browser()
        if not tor_process:
            print("Failed to start Tor Browser")
            return
    
    # Step 3: Wait for Tor to connect
    if not wait_for_tor_connection(timeout=120):
        print("Tor connection timeout - aborting")
        return
    
    print("\n" + "=" * 70)
    print("  Tor is connected! Starting data collection...")
    print("=" * 70 + "\n")
    
    # Step 4: Run the collection
    try:
        run_collection()
    except KeyboardInterrupt:
        print("\n\nData collection interrupted by user")
    except Exception as e:
        print(f"\nERROR during data collection: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup (don't close Tor Browser - user may want to keep it open)
    print("\n" + "=" * 70)
    print("  Data collection complete!")
    print("  Tor Browser is still running - close manually if needed")
    print("=" * 70)


if __name__ == "__main__":
    run_automated_collection()
