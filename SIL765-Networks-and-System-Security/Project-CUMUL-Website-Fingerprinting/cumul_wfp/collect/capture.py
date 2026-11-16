"""
File: capture.py
Module: collect
Phase: Phase 1 - Data Collection

Purpose:
    Automates Tor Browser to visit target websites and captures
    network traffic using Scapy for website fingerprinting.

Paper reference: N/A - data collection infrastructure

Windows adaptation notes:
    Uses Scapy with Npcap for packet capture on Windows.
    Uses Selenium's built-in driver manager (no manual geckodriver needed).

Dependencies:
    - selenium: Browser automation (4.6+ has built-in driver manager)
    - scapy: Packet capture
    - stem: Tor control

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-03-17
"""

# FIRST: Set Wireshark manuf path BEFORE any other imports
import os
os.environ['WIRESHARK_MANUF'] = r'C:\Program Files\Wireshark\manuf'

import sys
import time
import random
import warnings
warnings.filterwarnings('ignore')  # Suppress other warnings

from pathlib import Path
from threading import Thread, Event

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Scapy imports for packet capture
try:
    from scapy.all import sniff, wrpcap
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    print("WARNING: Scapy not available - packet capture disabled")

# Stem for Tor control
try:
    from stem import Signal
    from stem.control import Controller
    STEM_AVAILABLE = True
except ImportError:
    STEM_AVAILABLE = False
    print("WARNING: Stem not available - circuit rotation disabled")


def start_tor_browser():
    """Start Tor Browser automatically and wait for connection."""
    import subprocess
    
    tor_path = config.TBB_PATH
    if not tor_path or not os.path.exists(tor_path):
        print(f"ERROR: Tor Browser not found at {tor_path}")
        return False
    
    print("Starting Tor Browser...")
    
    # Start Tor Browser
    try:
        subprocess.Popen([tor_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Error starting Tor: {e}")
        return False
    
    # Wait for Tor to connect
    print("Waiting for Tor to connect...", end=" ", flush=True)
    max_wait = 60  # seconds
    start = time.time()
    
    while time.time() - start < max_wait:
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', config.TOR_SOCKS_PORT))
            sock.close()
            if result == 0:
                print("Connected!")
                return True
        except:
            pass
        time.sleep(2)
        print(".", end="", flush=True)
    
    print("TIMEOUT - Tor not connected")
    return False


def wait_for_tor():
    """Wait for Tor SOCKS port to be available."""
    import socket
    
    print("Waiting for Tor proxy...", end=" ", flush=True)
    max_wait = 30
    start = time.time()
    
    while time.time() - start < max_wait:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', config.TOR_SOCKS_PORT))
            sock.close()
            if result == 0:
                print("Ready!")
                return True
        except:
            pass
        time.sleep(1)
        print(".", end="", flush=True)
    
    print("Tor proxy not available!")
    return False


class PacketCapture:
    """Thread-based packet capture using Scapy."""
    
    def __init__(self, interface, output_file, filter_str="tcp port 9150", timeout=30):
        self.interface = interface
        self.output_file = output_file
        self.filter_str = filter_str
        self.timeout = timeout
        self.packets = []
        self.stop_event = Event()
        self.capture_thread = None
    
    def start(self):
        """Start packet capture in background thread."""
        self.stop_event.clear()
        self.packets = []
        self.capture_thread = Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
    
    def _capture_loop(self):
        """Background capture loop - non-blocking with stop check."""
        if not SCAPY_AVAILABLE:
            return
        
        # Build kwargs
        kwargs = {'filter': self.filter_str}
        if self.interface:
            kwargs['iface'] = self.interface
        
        start_time = time.time()
        
        while not self.stop_event.is_set():
            # Check timeout
            if time.time() - start_time >= self.timeout:
                break
            
            try:
                # Non-blocking sniff with short timeout
                pkts = sniff(timeout=1, **kwargs)
                if pkts:
                    self.packets.extend(pkts)
            except:
                pass
    
    def stop(self):
        """Stop capture and save to file."""
        self.stop_event.set()
        if self.capture_thread:
            self.capture_thread.join(timeout=5)
        
        if self.packets and len(self.packets) > 0:
            try:
                wrpcap(self.output_file, self.packets)
                return len(self.packets)
            except Exception as e:
                print(f"Error saving pcap: {e}")
        return 0


def create_firefox_driver():
    """
    Create Selenium WebDriver for Chrome with Tor SOCKS proxy.
    
    Uses Chrome with Tor as SOCKS5 proxy for website fingerprinting.
    
    Includes stealth measures to avoid bot detection:
    - Custom user-agent (real browser)
    - Disable automation extensions
    - Hide webdriver property
    - Randomize window size
    """
    chrome_options = Options()
    
    # Add Tor SOCKS proxy
    chrome_options.add_argument(f"--proxy-server=socks5://127.0.0.1:{config.TOR_SOCKS_PORT}")
    
    # Disable GPU and sandbox for stability
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    
    # Make window visible and fullscreen
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-extensions")
    
    # STEALTH OPTIONS - Avoid bot detection
    # -------------------------------
    # Randomize user-agent to appear as real browser
    import random
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    ]
    chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
    
    # Disable automation flags
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    
    # Disable webdriver
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Randomize window size slightly
    import random
    widths = [1280, 1366, 1440, 1536, 1600, 1920]
    height = random.randint(700, 900)
    width = random.choice(widths)
    chrome_options.add_argument(f"--window-size={width},{height}")
    
    # Disable some features that might reveal automation
    chrome_options.add_argument("--disable-features=NetworkService,NetworkServiceInProcess")
    chrome_options.add_argument("--disable-features=TranslateUI")
    
    # Create driver
    try:
        driver = webdriver.Chrome(options=chrome_options)
        
        # Additional stealth: Remove webdriver property
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        # Stealth: Modify plugins
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                })
            """
        })
        
        # Stealth: Modify languages
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                })
            """
        })
        
        return driver
    except Exception as e:
        print(f"Error creating driver: {e}")
        raise


def rotate_tor_circuit():
    """
    Signal Tor to create a new circuit via Stem controller.
    
    This ensures each capture instance uses a different Tor circuit,
    which improves classifier robustness (as per paper methodology).
    
    Returns True if successful, False otherwise.
    """
    # Circuit rotation is CRITICAL for WFP:
    # - Different circuits = different entry nodes = varied traffic patterns
    # - This makes classifier robust to network-level variations
    # - Paper recommends NEWNYM signal before each capture
    
    if not STEM_AVAILABLE:
        print("WARNING: Stem not available, skipping circuit rotation")
        return True
    
    try:
        with Controller.from_port(port=config.TOR_CONTROL_PORT) as controller:
            controller.authenticate()
            controller.signal(Signal.NEWNYM)
            print("(new circuit)", end=" ")
            time.sleep(config.CIRCUIT_WAIT_SECONDS)
            return True
    except Exception as e:
        print(f"Circuit rotation error: {e}")
        return False


def capture_site(url, label, instance_idx):
    """
    Capture network traffic for a single website visit.
    
    Steps:
    1. Random delay (avoid rate limiting)
    2. Rotate Tor circuit (new circuit per instance)
    3. Start packet capture in background
    4. Load website in Tor Browser
    5. Wait for page to load
    6. Verify page loaded successfully
    7. Stop capture and save PCAP
    
    Args:
        url: Full URL to visit
        label: Website label for filename
        instance_idx: Instance number for this capture
    
    Returns:
        Path to saved pcap file, or None on failure
    """
    # Random delay before capture (avoid rate limiting)
    import random
    delay = random.uniform(2, 5)
    time.sleep(delay)
    
    # Rotate circuit first
    rotate_tor_circuit()
    
    # Setup output file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pcap_dir = os.path.join(base_dir, "data", "raw")
    os.makedirs(pcap_dir, exist_ok=True)
    output_file = os.path.join(
        pcap_dir, 
        f"{label}_{instance_idx:03d}.pcap"
    )
    
    # Start packet capture
    capture = None
    if SCAPY_AVAILABLE:
        capture = PacketCapture(
            interface=config.CAPTURE_INTERFACE,
            output_file=output_file,
            filter_str="tcp",  # Capture ALL TCP traffic on loopback
            timeout=config.CAPTURE_TIMEOUT
        )
        capture.start()
    
    page_loaded = False
    driver = None
    try:
        driver = create_firefox_driver()
        driver.get(url)
        
        # Random wait for initial page load (2-5 seconds)
        wait_time = random.uniform(2, 5)
        time.sleep(wait_time)
        
        # Verify page loaded properly - check for blocked/verification pages
        page_loaded = False
        page_title = ""
        try:
            page_title = driver.title
        except:
            pass
        
        # Check for blocked/verification indicators in page title
        # Extended list of blocking indicators
        blocked_keywords = [
            'blocked', 'access denied', 'captcha', 'verify', 'robot',
            'unusual traffic', 'security check', 'permission denied',
            'sorry', 'please wait', 'checking your browser', 'challenge',
            'cloudflare', 'ddos', 'rate limit', 'too many requests',
            'automated', 'suspicious', 'denied', 'forbidden',
            'not allowed', 'error', 'exception', 'traffic', 'rejected',
            'please enable', 'javascript', 'cookies', 'ad blocker'
        ]
        
        title_lower = page_title.lower() if page_title else ""
        is_blocked = any(kw in title_lower for kw in blocked_keywords)
        
        # Also check URL - if redirected to verification, URL will change
        current_url = ""
        try:
            current_url = driver.current_url.lower()
        except:
            pass
        
        # Page is valid if:
        # 1. Title is not blocked keywords
        # 2. URL contains expected domain
        if not is_blocked and page_title and len(page_title) > 0:
            # Additional check: verify URL matches expected domain
            url_domain = url.split('://')[1].split('/')[0] if '://' in url else url.split('/')[0]
            if url_domain.replace('www.', '') in current_url.replace('www.', ''):
                page_loaded = True
                print(f"(page: {page_title[:30]}...)", end=" ")
            else:
                print(f"(redirected to: {current_url[:40]}...)", end=" ")
        else:
            print(f"(BLOCKED: {page_title[:30]}...)", end=" ")
        
        if not page_loaded:
            # Check if body exists with SUBSTANTIAL content (increased threshold)
            try:
                body = driver.find_element("tag name", "body")
                if body:
                    text_length = len(body.text)
                    # Higher threshold - real pages have 2000+ chars
                    # Blocked pages typically have < 1000 chars
                    if text_length > 2000:
                        page_loaded = True
                        print(f"(body: {text_length} chars)", end=" ")
                    elif text_length > 500:
                        # Medium content - might be blocked but some content loaded
                        # Check for common blocked page patterns
                        body_text = body.text.lower()
                        if any(w in body_text for w in ['blocked', 'denied', 'verify', 'captcha', 'sorry']):
                            print(f"(BLOCKED content: {text_length} chars)", end=" ")
                        else:
                            page_loaded = True
                            print(f"(body: {text_length} chars)", end=" ")
                    else:
                        print(f"(too short: {text_length} chars)", end=" ")
            except Exception as e:
                print(f"(no body: {e})", end=" ")
                pass
        
        if page_loaded:
            # Random scroll behavior (simulates real browsing)
            scroll_count = random.randint(2, 5)
            for _ in range(scroll_count):
                scroll_amt = random.randint(200, 600)
                driver.execute_script(f"window.scrollBy(0, {scroll_amt});")
                time.sleep(random.uniform(0.5, 1.5))
                driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(1)
            
            # Wait for full page load
            time.sleep(config.PAGE_LOAD_WAIT - 4)  # Subtract the time we already waited
        else:
            print("(page NOT loaded!)", end=" ")
            
    except Exception as e:
        print(f"Error loading {url}: {e}")
    
    finally:
        # Stop capture
        packet_count = 0
        total_bytes = 0
        if capture:
            packet_count = capture.stop()
        
        # Validate packet data BEFORE accepting
        if packet_count > 0 and os.path.exists(output_file):
            try:
                from scapy.all import rdpcap
                packets = rdpcap(output_file)
                packet_count = len(packets)
                
                # Calculate total bytes transferred
                total_bytes = sum(len(pkt.load) for pkt in packets if hasattr(pkt, 'load'))
                
                # Use thresholds from config
                MIN_BYTES = config.MIN_PACKETS * 250  # ~250 bytes per packet minimum
                
                if packet_count < config.MIN_PACKETS:
                    print(f"FAILED: only {packet_count} packets (min: {config.MIN_PACKETS})")
                    packet_count = 0
                elif total_bytes < MIN_BYTES:
                    print(f"FAILED: only {total_bytes:,} bytes transferred (min: {MIN_BYTES})")
                    packet_count = 0
                    total_bytes = 0
                    
            except Exception as e:
                print(f"FAILED: validation error: {e}")
                packet_count = 0
        
        # Close browser
        if driver:
            try:
                driver.quit()
            except:
                pass
        
        # Check if page loaded AND we got enough packets
        if page_loaded and packet_count >= config.MIN_PACKETS and total_bytes > 0:
            print(f"OK: {packet_count} packets, {total_bytes:,} bytes -> {output_file}")
            return output_file
        elif not page_loaded:
            print(f"FAILED: page did not load")
            # Clean up file
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass
            return None
        else:
            print(f"FAILED: insufficient data ({packet_count} packets, {total_bytes:,} bytes)")
            # Clean up file
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass
            return None


def run_collection():
    """
    Main collection loop: visits all configured websites multiple times.
    
    For each site:
        - Rotate Tor circuit
        - Start packet capture
        - Load website in Tor Browser
        - Stop capture and save pcap
    
    Filename format: {label}_{instance_idx:03d}.pcap
    """
    sites = config.MONITORED_SITES
    instances = config.INSTANCES_PER_CLASS
    
    print(f"=" * 60)
    print(f"  CUMUL WFP - Data Collection")
    print(f"=" * 60)
    print(f"Sites: {len(sites)}")
    print(f"Instances per site: {instances}")
    print(f"Total captures: {len(sites) * instances}")
    print(f"=" * 60)
    
    # Verify prerequisites
    if not SCAPY_AVAILABLE:
        print("ERROR: Scapy not available. Cannot capture packets.")
        return
    
    # Check interface (None = all interfaces is valid)
    if config.CAPTURE_INTERFACE and not os.path.exists(config.CAPTURE_INTERFACE):
        print(f"WARNING: Interface {config.CAPTURE_INTERFACE} not found, using all interfaces")
    
    # Start Tor Browser automatically
    if not wait_for_tor():
        print("\nStarting Tor Browser...")
        if not start_tor_browser():
            print("ERROR: Cannot start Tor Browser. Please start it manually.")
            return
    
    print("\nStarting data collection...")
    
    success_count = 0
    fail_count = 0
    
    for label, url in sites.items():
        print(f"\n--- {label} ({url}) ---")
        for i in range(instances):
            print(f"  Instance {i+1}/{instances}...", end=" ")
            result = capture_site(url, label, i)
            if result:
                success_count += 1
            else:
                fail_count += 1
            
            # Small random delay between captures
            time.sleep(random.uniform(1, 3))
    
    print(f"\n{'=' * 60}")
    print(f"Data collection complete!")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Total: {success_count + fail_count}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_collection()
