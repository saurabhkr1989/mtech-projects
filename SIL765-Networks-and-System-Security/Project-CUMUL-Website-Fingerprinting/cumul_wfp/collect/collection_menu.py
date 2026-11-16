"""
Data Collection Menu
===================
Interactive menu for collecting website fingerprints.
"""

import os
import sys
import glob
import time
import random

# Set environment
os.environ['WIRESHARK_MANUF'] = r'C:\Program Files\Wireshark\manuf'
if 'SSLKEYLOGFILE' in os.environ:
    del os.environ['SSLKEYLOGFILE']

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from scapy.all import rdpcap


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


def get_user_input_num(prompt, min_val, max_val, default=None):
    """Get numeric input from user."""
    while True:
        try:
            val = input(f"  {prompt} [{min_val}-{max_val}]: ").strip()
            if val == "" and default is not None:
                return default
            num = int(val)
            if min_val <= num <= max_val:
                return num
            print(f"  Please enter a number between {min_val} and {max_val}")
        except ValueError:
            print("  Please enter a valid number")


def get_existing_captures():
    """
    Scan raw directory and count existing captures by site.
    
    Returns:
        tuple: (monitored_dict, background_dict)
    """
    # Use absolute path from parent directory (cumul_wfp_1)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pcap_dir = os.path.join(base_dir, "data", "raw")
    pcap_files = glob.glob(os.path.join(pcap_dir, "*.pcap"))
    
    monitored = {}
    background = {}
    
    for f in pcap_files:
        basename = os.path.basename(f)
        parts = basename.replace('.pcap', '').split('_')
        label = parts[0]
        
        if label == 'bg':
            site_name = parts[1] if len(parts) > 1 else 'unknown'
            background[site_name] = background.get(site_name, 0) + 1
        else:
            monitored[label] = monitored.get(label, 0) + 1
    
    return monitored, background


def validate_existing_captures():
    """
    Validate existing captures and delete invalid ones.
    
    Returns:
        dict: Summary of validation
    """
    print_step(1, 4, "Validating existing captures")
    
    # Ask user if they want to skip validation
    print()
    print("  Validation checks each PCAP file for minimum packet/byte counts.")
    print("  This may take a while if you have many files.")
    print()
    skip_validation = input("  Skip validation? (y/N): ").strip().lower()
    
    if skip_validation == 'y':
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        pcap_dir = os.path.join(base_dir, "data", "raw")
        pcap_files = glob.glob(os.path.join(pcap_dir, "*.pcap"))
        print(f"  [SKIPPED] Assuming {len(pcap_files)} files are valid")
        return {
            'valid': len(pcap_files),
            'deleted': 0,
            'total': len(pcap_files),
            'skipped': True
        }
    
    MIN_PACKETS = config.MIN_PACKETS
    MIN_BYTES = MIN_PACKETS * 250
    
    # Use absolute path from parent directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pcap_dir = os.path.join(base_dir, "data", "raw")
    pcap_files = glob.glob(os.path.join(pcap_dir, "*.pcap"))
    to_delete = []
    valid_count = 0
    
    print(f"  Checking {len(pcap_files)} files...")
    print()
    
    for i, f in enumerate(sorted(pcap_files)):
        basename = os.path.basename(f)
        print_progress(i + 1, len(pcap_files), f"  Validating")
        
        try:
            packets = rdpcap(f)
            packet_count = len(packets)
            total_bytes = sum(len(pkt.load) for pkt in packets if hasattr(pkt, 'load'))
            
            if packet_count < MIN_PACKETS or total_bytes < MIN_BYTES:
                to_delete.append((basename, packet_count, total_bytes))
            else:
                valid_count += 1
        except Exception as e:
            to_delete.append((basename, 0, 0))
    
    print()  # Clear progress line
    print(f"  Valid: {valid_count} | Invalid: {len(to_delete)}")
    
    if to_delete:
        print("\n  Invalid captures (will be deleted):")
        for basename, packets, bytes_count in to_delete:
            print(f"    - {basename} ({packets} packets, {bytes_count:,} bytes)")
        
        # Auto-delete invalid captures
        for basename, _, _ in to_delete:
            fpath = os.path.join(pcap_dir, basename)
            if os.path.exists(fpath):
                os.remove(fpath)
        
        print(f"\n  [AUTO-DELETED] {len(to_delete)} invalid captures")
    
    return {
        'valid': valid_count,
        'deleted': len(to_delete),
        'total': len(pcap_files)
    }


def show_site_selection(num_monitored, num_background):
    """Show selected sites."""
    print_step(2, 4, "Site Selection Summary")
    
    monitored_list = list(config.MONITORED_SITES.items())[:num_monitored]
    background_list = list(config.BACKGROUND_SITES.items())[:num_background]
    
    print(f"\n  Monitored Sites ({num_monitored}):")
    for i, (label, url) in enumerate(monitored_list, 1):
        print(f"    {i:2d}. {label:15s} - {url}")
    
    if num_background > 0:
        print(f"\n  Background Sites ({num_background}):")
        for i, (label, url) in enumerate(background_list, 1):
            print(f"    {i:2d}. {label:15s} - {url}")


def check_additional_data_warning(num_monitored, num_background):
    """Show warning about additional data."""
    print_step(3, 4, "Data Check")
    
    # Count existing captures
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pcap_dir = os.path.join(base_dir, "data", "raw")
    pcap_files = glob.glob(os.path.join(pcap_dir, "*.pcap"))
    
    # Count by site
    from collections import Counter
    site_counts = Counter()
    for f in pcap_files:
        basename = os.path.basename(f)
        label = basename.split('_')[0]
        if label == 'bg':
            parts = basename.replace('.pcap', '').split('_')
            label = parts[1] if len(parts) > 1 else 'unknown'
        site_counts[label] += 1
    
    total_configured = len(config.MONITORED_SITES) + len(config.BACKGROUND_SITES)
    selected = num_monitored + num_background
    
    print(f"  Sites configured: {total_configured}")
    print(f"  Sites selected: {selected}")
    print(f"  Total captures: {len(pcap_files)}")
    
    # Show detailed status with serial numbers
    print("\n  MONITORED SITES:")
    instances = config.INSTANCES_PER_CLASS
    for i, (site, url) in enumerate(sorted(config.MONITORED_SITES.items()), 1):
        count = site_counts.get(site, 0)
        status = "OK" if count >= instances else ("PARTIAL" if count > 0 else "MISSING")
        print(f"    {i:2d}. {site:<20} [{count:2d}/{instances}] {status}")
    
    print("\n  BACKGROUND SITES:")
    bg_count = 0
    for i, (site, url) in enumerate(sorted(config.BACKGROUND_SITES.items()), 1):
        count = site_counts.get(site, 0)
        status = "OK" if count >= config.BG_INSTANCES_PER_CLASS else ("PARTIAL" if count > 0 else "MISSING")
        print(f"    {i:2d}. {site:<20} [{count:2d}/{config.BG_INSTANCES_PER_CLASS}] {status}")
        bg_count += 1
    
    if selected < total_configured and len(pcap_files) > 0:
        print("\n  " + "!" * 50)
        print("  WARNING: Additional data exists!")
        print("  " + "!" * 50)
        print(f"    - {total_configured} sites configured, {selected} selected")
        print(f"    - {len(pcap_files)} captures exist for all sites")
        print(f"    - Valid captures for unselected sites will be kept")
        print("\n  For clean analysis:")
        print("    - Select all sites OR")
        print("    - Manually delete unwanted captures from data/raw/")
        print()
        
        try:
            input("  Press Enter to continue or Ctrl+C to abort...")
        except KeyboardInterrupt:
            print("\n\n  Aborted by user.")
            sys.exit(0)


def collect_sites(monitored_sites, background_sites, instances):
    """Collect captures for selected sites."""
    print_step(4, 4, "Collection")
    
    # Get base directory for paths
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pcap_dir = os.path.join(base_dir, "data", "raw")
    
    # Check Tor
    print("\n  Checking Tor proxy...")
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 9050))
        sock.close()
        if result == 0:
            print("  [OK] Tor port 9050 is listening")
        else:
            print("  [START] Tor not running, starting...")
            from .capture import start_tor_browser, wait_for_tor
            if not wait_for_tor():
                if not start_tor_browser():
                    print("  [ERROR] Cannot start Tor!")
                    return
                wait_for_tor()
            print("  [OK] Tor started")
    except Exception as e:
        print(f"  [ERROR] {e}")
        return
    
    # Import capture module
    from . import capture
    
    # Get existing captures
    def get_existing(label):
        pattern = os.path.join(pcap_dir, f"{label}_*.pcap")
        files = glob.glob(pattern)
        indices = set()
        for f in files:
            basename = os.path.basename(f)
            parts = basename.replace('.pcap', '').split('_')
            try:
                # For background sites like bg_msn_000.pcap, index is last part
                # For monitored sites like wikipedia_000.pcap, index is second part
                if label.startswith('bg_'):
                    idx = int(parts[-1])  # bg_msn_000 -> 000
                else:
                    idx = int(parts[1])   # wikipedia_000 -> 000
                indices.add(idx)
            except:
                pass
        return indices
    
    # Collect monitored sites
    print("\n  Collecting monitored sites...")
    print(f"  {'No':>3} | {'Site':<20} | Status")
    print("  " + "-" * 45)
    monitored_success = 0
    monitored_total = 0
    
    for i, (label, url) in enumerate(monitored_sites.items(), 1):
        existing = get_existing(label)
        needed = instances - len(existing)
        
        if needed <= 0:
            print(f"  {i:3d} | {label:<20} | [{instances}/{instances}] SKIP")
            monitored_success += instances
            monitored_total += instances
            continue
        
        print(f"  {i:3d} | {label:<20} | [{len(existing)}/{instances}] Collecting {needed}...")
        monitored_total += instances
        
        for j in range(instances):
            if j in existing:
                continue
            
            print(f"       | {'':20} |   Instance {j+1}/{instances}...", end=" ", flush=True)
            
            result = capture.capture_site(url, label, j)
            
            if result:
                monitored_success += 1
                print("OK")
            else:
                print("FAILED")
            
            # Delay between captures
            delay = random.uniform(5, 15)
            time.sleep(delay)
    
    # Collect background sites
    bg_success = 0
    bg_total = 0
    
    if background_sites:
        print("\n  Collecting background sites...")
        print(f"  {'No':>3} | {'Site':<20} | Status")
        print("  " + "-" * 45)
        
        for i, (label, url) in enumerate(background_sites.items(), 1):
            existing = get_existing(f"bg_{label}")
            needed = config.BG_INSTANCES_PER_CLASS - len(existing)
            
            if needed <= 0:
                print(f"  {i:3d} | bg_{label:<17} | [1/1] SKIP")
                bg_success += 1
                bg_total += 1
                continue
            
            print(f"  {i:3d} | bg_{label:<17} | [0/1] Collecting...")
            bg_total += 1
            
            print(f"       | {'':20} |   Instance 1/1...", end=" ", flush=True)
            result = capture.capture_site(url, f"bg_{label}", 0)
            
            if result:
                bg_success += 1
                print("OK")
            else:
                print("FAILED")
            
            time.sleep(random.uniform(5, 15))
    
    # Update valid traces
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pcap_dir = os.path.join(base_dir, "data", "raw")
    proc_dir = os.path.join(base_dir, "data", "processed")
    pcap_files = glob.glob(os.path.join(pcap_dir, "*.pcap"))
    pcap_files = [f.replace('\\', '/') for f in pcap_files]
    pcap_files.sort()
    
    os.makedirs(proc_dir, exist_ok=True)
    with open(os.path.join(proc_dir, 'valid_traces.json'), 'w') as f:
        import json
        json.dump(pcap_files, f, indent=2)
    
    # Summary
    print("\n" + "=" * 60)
    print("  COLLECTION SUMMARY")
    print("=" * 60)
    print(f"  Monitored: {monitored_success}/{monitored_total} captured")
    print(f"  Background: {bg_success}/{bg_total} captured")
    print(f"  Total captures: {len(pcap_files)}")
    print("=" * 60)


def run():
    """Main collection menu."""
    # Step 0: Scan existing data
    print("\n  Scanning existing captures...")
    monitored, background = get_existing_captures()
    
    # Show existing data
    print("\n  EXISTING CAPTURES:")
    print("-" * 60)
    
    if monitored or background:
        for site in sorted(monitored.keys()):
            count = monitored[site]
            instances = config.INSTANCES_PER_CLASS
            status = "OK" if count >= instances else ("PARTIAL" if count > 0 else "-")
            print(f"    [M] {site:<20} {count}/{instances} {status}")
        
        for site in sorted(background.keys()):
            count = background[site]
            status = "OK" if count >= 1 else "-"
            print(f"    [B] bg_{site:<17} {count}/1 {status}")
    else:
        print("    No existing captures found")
    
    print("-" * 60)
    total_existing = len(monitored) + len(background)
    print(f"  Total sites with data: {total_existing}")
    print()
    
    # Step 1: Ask for number of sites to collect
    print("  Site Selection")
    print("-" * 60)
    print(f"  Configured: {len(config.MONITORED_SITES)} monitored, {len(config.BACKGROUND_SITES)} background")
    
    num_monitored = get_user_input_num(
        "How many monitored sites to collect?",
        1, len(config.MONITORED_SITES), len(config.MONITORED_SITES)
    )
    
    num_background = get_user_input_num(
        "How many background sites to collect?",
        0, len(config.BACKGROUND_SITES), 0
    )
    
    # Step 2: Validate existing captures
    validation = validate_existing_captures()
    
    # Step 3: Show selection
    monitored_sites = dict(list(config.MONITORED_SITES.items())[:num_monitored])
    background_sites = dict(list(config.BACKGROUND_SITES.items())[:num_background])
    
    show_site_selection(num_monitored, num_background)
    
    # Step 4: Warning for additional data
    check_additional_data_warning(num_monitored, num_background)
    
    # Step 5: Collect
    collect_sites(monitored_sites, background_sites, config.INSTANCES_PER_CLASS)


if __name__ == "__main__":
    run()
