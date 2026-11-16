"""
File: main.py
Purpose:
    Entry point - menu (or command-line argument) for the YouTube-over-Tor
    capture app.

Usage (from this folder, terminal opened "as Administrator" for Npcap):
    python main.py              interactive menu
    python main.py collect      capture config.INSTANCES complete playbacks
    python main.py collect 1    capture a single instance (quick test)
    python main.py status       what has been captured so far
    python main.py check        verify Tor Browser, tor, dumpcap, interface

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import os
import sys

import stem

import config
import capture
import collector
from tor_control import port_is_listening, slot_ports


def print_header():
    print("=" * 64)
    print("  YouTube Video Fingerprinting over Tor - capture tool")
    print("=" * 64)


def check_setup():
    def report(is_ok, label, detail=""):
        print(f"  [{'OK' if is_ok else '!!'}] {label}{(' - ' + detail) if detail else ''}")

    print("\n  Configuration")
    try:
        target = collector.validate_video_settings()
        if config.MODE == "playlist":
            report(True, "Mode", f"playlist - {target}, one random video per instance")
        else:
            report(True, "Video link", f"{config.YOUTUBE_VIDEO_URL} (id {target})")
    except ValueError as setting_error:
        report(False, "Video link", str(setting_error))
    report(config.BROWSER in ("tor_browser", "chrome_tor"), "Browser mode", config.BROWSER)
    report(config.NAVIGATION in ("browse", "direct"), "Navigation",
           "browse: entry page -> random wait/scroll -> click the video" if config.NAVIGATION == "browse"
           else "direct: video link opened directly")
    report(config.BROWSER_WINDOW in ("behind", "offscreen", "headless", "visible"), "Browser window", config.BROWSER_WINDOW)
    report(os.path.exists(config.TBB_FIREFOX_EXE), "Tor Browser firefox.exe", config.TBB_FIREFOX_EXE)
    report(os.path.exists(config.TBB_PROFILE_DIR), "Tor Browser profile", config.TBB_PROFILE_DIR)
    report(os.path.exists(config.TOR_EXE_PATH), "tor.exe", config.TOR_EXE_PATH)

    print(f"\n  Tor ports ({config.PARALLEL_INSTANCES} parallel slots)")
    for slot_index in range(config.PARALLEL_INSTANCES):
        socks_port, control_port = slot_ports(slot_index)
        if port_is_listening(control_port):
            report(True, f"Slot {slot_index + 1}: {socks_port}/{control_port}", "tor already running - will attach")
        elif port_is_listening(socks_port):
            report(False, f"Slot {slot_index + 1}: {socks_port}/{control_port}",
                   "SOCKS port used by another program - change TOR_BASE_SOCKS_PORT")
        else:
            report(True, f"Slot {slot_index + 1}: {socks_port}/{control_port}", "free")

    print("\n  Packet capture")
    report(is_administrator(), "Running as Administrator", "" if is_administrator() else
           "packet capture needs it - use the Run_YouTubeWFP.bat launcher or an Administrator terminal")
    report(capture.npcap_installed() and os.path.exists(config.DUMPCAP_PATH), "Wireshark + Npcap (optional)",
           "found" if capture.npcap_installed() and os.path.exists(config.DUMPCAP_PATH)
           else "not installed - the built-in raw socket capture will be used")
    try:
        selected_interface = capture.resolve_capture_interface()
        report(True, "Interface", f"{selected_interface.description} ({selected_interface.ip_address})")
        os.makedirs(config.DATA_RAW_DIR, exist_ok=True)
        capture.choose_working_engine(selected_interface, config.DATA_RAW_DIR,
                                      report=lambda message: print(f"  [..] {message}"))
    except (ValueError, RuntimeError, FileNotFoundError, OSError) as capture_error:
        report(False, "Capture", str(capture_error))
    print("\n  Interfaces with an IPv4 address (description | IP | NPF name):")
    for description, ip_address, npcap_name in capture.list_capture_interfaces():
        print(f"    {description[:40]:<40} | {ip_address:<15} | {npcap_name}")


def is_administrator():
    if os.name != "nt":
        return os.geteuid() == 0
    import ctypes
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def run_collection_reporting_errors(instance_count=None):
    """Run a collection; set-up errors are printed instead of crashing the menu."""
    try:
        collector.run_collection(instance_count)
    except (ValueError, RuntimeError, FileNotFoundError, TimeoutError, OSError,
            stem.ControllerError) as setup_error:
        print(f"\n  [ERROR] {type(setup_error).__name__}: {setup_error}")


def interactive_menu():
    while True:
        print(f"\n  1. Start / resume capture   ({config.INSTANCES} instances, {config.PARALLEL_INSTANCES} at a time)")
        print("  2. Capture one test instance")
        print("  3. Show status")
        print("  4. Check setup")
        print("  5. Exit")
        choice = input("\n  Select option: ").strip()
        if choice == "1":
            run_collection_reporting_errors()
        elif choice == "2":
            run_collection_reporting_errors(instance_count=1)
        elif choice == "3":
            collector.show_status()
        elif choice == "4":
            check_setup()
        elif choice == "5":
            return
        else:
            print("  Invalid option.")


def main():
    print_header()
    command = sys.argv[1].lower() if len(sys.argv) > 1 else None
    try:
        if command is None:
            interactive_menu()
        elif command == "collect":
            instance_count = int(sys.argv[2]) if len(sys.argv) > 2 else None
            run_collection_reporting_errors(instance_count)
        elif command == "status":
            collector.show_status()
        elif command == "check":
            check_setup()
        else:
            print(__doc__)
    except KeyboardInterrupt:
        print("\n  Stopped by user. Completed captures are kept; run again to resume.")


if __name__ == "__main__":
    main()
