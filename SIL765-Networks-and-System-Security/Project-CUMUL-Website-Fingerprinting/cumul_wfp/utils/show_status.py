"""
Status View Module
=================
Show collection status.
"""

import os
import sys
import glob
from collections import Counter

# Set environment
os.environ['WIRESHARK_MANUF'] = r'C:\Program Files\Wireshark\manuf'
if 'SSLKEYLOGFILE' in os.environ:
    del os.environ['SSLKEYLOGFILE']

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def get_capture_counts():
    """Get capture counts by site."""
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
            # bg_urlname_000.pcap
            site_name = parts[1] if len(parts) > 1 else 'unknown'
            if site_name not in background:
                background[site_name] = 0
            background[site_name] += 1
        else:
            if label not in monitored:
                monitored[label] = 0
            monitored[label] += 1
    
    return monitored, background


def print_bar(count, target, width=20):
    """Print a progress bar."""
    filled = int((count / target) * width) if target > 0 else 0
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}]"


def run():
    """Show collection status."""
    print("=" * 60)
    print("  COLLECTION STATUS")
    print("=" * 60)
    
    # Get base dir for paths
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pcap_dir = os.path.join(base_dir, "data", "raw")
    
    # Get counts
    monitored, background = get_capture_counts()
    
    # Config targets
    target_monitored = len(config.MONITORED_SITES)
    target_background = len(config.BACKGROUND_SITES)
    instances = config.INSTANCES_PER_CLASS
    bg_instances = config.BG_INSTANCES_PER_CLASS
    
    # Monitored sites status
    print("\nMONITORED SITES")
    print("-" * 60)
    print(f"{'Site':<20} {'Progress':<25} {'Count':<10} {'Status'}")
    print("-" * 60)
    
    total_collected = 0
    total_target = 0
    
    for site in sorted(config.MONITORED_SITES.keys()):
        count = monitored.get(site, 0)
        total_collected += count
        total_target += instances
        
        bar = print_bar(count, instances)
        status = "OK" if count >= instances else ("PARTIAL" if count > 0 else "MISSING")
        
        print(f"{site:<20} {bar} {count:>2}/{instances:<4} {status}")
    
    # Background sites status
    if target_background > 0:
        print("\nBACKGROUND SITES (UNMONITORED)")
        print("-" * 60)
        print(f"{'Site':<20} {'Progress':<25} {'Count':<10} {'Status'}")
        print("-" * 60)
        
        for site in sorted(config.BACKGROUND_SITES.keys()):
            count = background.get(site, 0)
            bar = print_bar(count, bg_instances)
            status = "OK" if count >= bg_instances else ("PARTIAL" if count > 0 else "MISSING")
            
            print(f"bg_{site:<17} {bar} {count:>2}/{bg_instances:<4} {status}")
    
    # Summary
    pcap_files = glob.glob(os.path.join(pcap_dir, "*.pcap"))
    
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Total PCAP files: {len(pcap_files)}")
    print(f"  Monitored: {total_collected}/{total_target} "
          f"({(total_collected/total_target)*100:.1f}%)")
    print(f"  Background: {sum(background.values())}/{target_background * bg_instances}")
    print(f"  Sites configured: {target_monitored + target_background}")
    print("=" * 60)
    
    # Check for issues
    print("\n  NOTES:")
    
    partial = [s for s in config.MONITORED_SITES.keys() 
               if 0 < monitored.get(s, 0) < instances]
    if partial:
        print(f"  - {len(partial)} sites need more captures")
        for s in partial[:5]:
            print(f"    * {s}: {monitored[s]}/{instances}")
    
    missing = [s for s in config.MONITORED_SITES.keys() 
               if monitored.get(s, 0) == 0]
    if missing:
        print(f"  - {len(missing)} sites not captured")
        for s in missing[:5]:
            print(f"    * {s}")
    
    if not partial and not missing:
        print("  - All selected sites have complete captures")


if __name__ == "__main__":
    run()
