"""
File: main.py
Purpose:
    Entry point - menu (or command-line argument) for the X/Twitter post
    capture app (no Tor, private Firefox).

Usage (the portable launcher Run_TwitterWFP.bat does this as Administrator):
    python main.py              interactive menu
    python main.py collect      INSTANCES_PER_POST successful captures of every post
    python main.py test         one browser session of the first post (1 load + refreshes)
    python main.py status       what has been captured so far
    python main.py check        verify Firefox, driver, posts, packet capture

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import os
import sys

import config
import capture
import collector
from tor_control import port_is_listening, slot_ports


def is_administrator():
    if os.name != "nt":
        return os.geteuid() == 0
    import ctypes
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def check_setup():
    def report(is_ok, label, detail=""):
        print(f"  [{'OK' if is_ok else '!!'}] {label}{(' - ' + detail) if detail else ''}")

    print("\n  Configuration")
    try:
        collector.validate_post_settings()
        report(True, "Posts", f"{len(config.TWITTER_POSTS)} post(s) x {config.INSTANCES_PER_POST} instances")
        for label, url in config.TWITTER_POSTS.items():
            print(f"         {label}: {url}")
    except ValueError as settings_error:
        report(False, "Posts", str(settings_error))
    report(config.BROWSER in ("tor_browser", "firefox_private"), "Browser", config.BROWSER)
    if config.BROWSER == "tor_browser":
        report(os.path.exists(config.TBB_FIREFOX_EXE), "Tor Browser", config.TBB_FIREFOX_EXE)
        report(os.path.exists(config.TOR_EXE_PATH), "tor.exe", config.TOR_EXE_PATH)
        for slot_index in range(config.PARALLEL_INSTANCES):
            socks_port, control_port = slot_ports(slot_index)
            port_busy = port_is_listening(socks_port) and not port_is_listening(control_port)
            report(not port_busy, f"Slot {slot_index + 1} tor ports {socks_port}/{control_port}",
                   "used by another program - change TOR_BASE_SOCKS_PORT" if port_busy else "ok")
    else:
        report(os.path.exists(config.FIREFOX_EXE), "Firefox", config.FIREFOX_EXE)
    report(config.GECKODRIVER_PATH is not None, "geckodriver",
           config.GECKODRIVER_PATH or "not bundled - Selenium will download it (needs internet)")
    report(True, "Parallel browsers", f"{config.PARALLEL_INSTANCES}, window mode '{config.BROWSER_WINDOW}'")
    report(config.NAVIGATION in ("browse", "direct"), "Navigation",
           "browse: profile -> random wait/scroll -> click the post" if config.NAVIGATION == "browse"
           else "direct: post link opened directly")

    print("\n  Packet capture")
    report(is_administrator(), "Running as Administrator",
           "" if is_administrator() else "needed for capture - use Run_TwitterWFP.bat")
    try:
        selected_interface = capture.resolve_capture_interface()
        report(True, "Interface", f"{selected_interface.description} ({selected_interface.ip_address})")
        capture.choose_working_engine(selected_interface, report=lambda message: print(f"  [..] {message}"))
    except (ValueError, RuntimeError, OSError) as capture_error:
        report(False, "Capture", str(capture_error))
    finally:
        capture.stop_capture_engine()


def run_collection_reporting_errors(**collection_options):
    try:
        collector.run_collection(**collection_options)
    except (ValueError, RuntimeError, FileNotFoundError, OSError) as setup_error:
        print(f"\n  [ERROR] {type(setup_error).__name__}: {setup_error}")


def interactive_menu():
    while True:
        print(f"\n  1. Start / resume capture   ({len(config.TWITTER_POSTS)} post(s) x "
              f"{config.INSTANCES_PER_POST}, {config.PARALLEL_INSTANCES} at a time)")
        print(f"  2. Test: one browser session of the first post (1 load + {config.REFRESHES_PER_SESSION} refreshes)")
        print("  3. Show status")
        print("  4. Check setup")
        print("  5. Exit")
        choice = input("\n  Select option: ").strip()
        if choice == "1":
            run_collection_reporting_errors()
        elif choice == "2":
            run_collection_reporting_errors(instances_per_post=1 + config.REFRESHES_PER_SESSION, only_first_post=True)
        elif choice == "3":
            collector.show_status()
        elif choice == "4":
            check_setup()
        elif choice == "5":
            return
        else:
            print("  Invalid option.")


def main():
    print("=" * 76)
    print(f"  X / Twitter Post Fingerprinting - capture tool ({config.BROWSER})")
    print("=" * 76)
    command = sys.argv[1].lower() if len(sys.argv) > 1 else None
    try:
        if command is None:
            interactive_menu()
        elif command == "collect":
            run_collection_reporting_errors()
        elif command == "test":
            run_collection_reporting_errors(instances_per_post=1 + config.REFRESHES_PER_SESSION, only_first_post=True)
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
