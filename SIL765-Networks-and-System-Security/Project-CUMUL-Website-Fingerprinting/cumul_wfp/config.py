# CUMUL WFP Configuration
# =====================
# This is the ONLY file that needs editing between runs.
# All features are controlled via flags in this file.

# ===== PATHS =====
TBB_PATH = r"D:\MTech Assignments\Sem II\Nw System Security\Project\TorBrowser\Tor Browser\Browser\firefox.exe"
TBB_PROFILE_DIR = r"D:\MTech Assignments\Sem II\Nw System Security\Project\TorBrowser\Tor Browser\Browser\TorBrowser\Data\Browser\profile.default"
TOR_COOKIE_PATH = r"D:\MTech Assignments\Sem II\Nw System Security\Project\TorBrowser\Tor Browser\Browser\TorBrowser\Data\Tor\control_auth_cookie"
DATA_RAW_DIR = r"data\raw"
DATA_PROC_DIR = r"data\processed"
MODEL_PATH = r"data\models\svm_model.pkl"
SCALER_PATH = r"data\models\scaler.pkl"
RESULTS_DIR = r"results"

# ===== NETWORK =====
CAPTURE_INTERFACE = None  # None = all interfaces (safer for Windows)
TOR_SOCKS_PORT = 9050
TOR_CONTROL_PORT = 9051

# ===== DATA COLLECTION =====
INSTANCES_PER_CLASS = 10  # 10 instances per monitored website
BG_INSTANCES_PER_CLASS = 1  # 1 instance per background/unmonitored site
CAPTURE_TIMEOUT = 30  # Seconds to sniff per page load
PAGE_LOAD_WAIT = 10  # Seconds to wait after selenium.get() before stopping sniff
CIRCUIT_WAIT_SECONDS = 5  # Wait after NEWNYM before next capture
MIN_PACKETS = 500  # Discard traces with fewer packets than this (realistic pages have 500+)

# ===== FEATURE EXTRACTION =====
EXTRACTION_LAYER = "tcp"  # "tcp" | "tls" | "cells". Use "tcp" for general HTTP traffic
N_FEATURES = 100  # Interpolation points. Paper optimal: 100

# ===== SVM HYPERPARAMETERS =====
SVM_C = 1.0  # Default when grid_search=False
SVM_GAMMA = "scale"  # Default when grid_search=False
GRID_SEARCH_C = [2**i for i in range(11, 18)]  # [2048 .. 131072]
GRID_SEARCH_GAMMA = [2**i for i in range(-3, 4)]  # [0.125 .. 8.0]
CV_FOLDS = 10

# ===== OPEN-WORLD EVALUATION =====
ALERT_THRESHOLD = 0.60  # Confidence below this -> "Unknown"
THRESHOLD_SWEEP_VALS = [i/10 for i in range(1, 10)]  # [0.1, 0.2, ..., 0.9]
BG_SET_SIZES = [1000, 5000, 9000]

# ===== FEATURE FLAGS =====
OPEN_WORLD = False  # True -> run open-world eval with background set
LONGITUDINAL = False  # True -> enable day-tagging and temporal eval
THRESHOLD_SWEEP = False  # True -> sweep threshold and plot P-R curve
DEMO_MODE = False  # True -> launch live Tkinter monitor

# ===== DEMO-MODE SETTINGS =====
MIN_PACKETS_FOR_CLASSIFY = 50  # Ignore live traces shorter than this
TRACE_IDLE_TIMEOUT = 3.0  # Seconds idle -> treat as trace end
MAX_TRACE_PACKETS = 2000  # Hard cap per trace

# ===== MONITORED SITES =====
# 20 websites for closed-world evaluation (as per paper)
MONITORED_SITES = {
    # News sites
    "bbc": "https://www.bbc.com",
    "cnn": "https://www.cnn.com",
    "reuters": "https://www.reuters.com",
    "nytimes": "https://www.nytimes.com",
    "washingtonpost": "https://www.washingtonpost.com",
    "theguardian": "https://www.theguardian.com",
    "aljazeera": "https://www.aljazeera.net",
    "foxnews": "https://www.foxnews.com",
    "huffpost": "https://www.huffpost.com",
    "usatoday": "https://www.usatoday.com",
    
    # Reference/Educational
    "wikipedia": "https://www.wikipedia.org",
    "nasa": "https://www.nasa.gov",
    "weather": "https://www.weather.com",
    "britannica": "https://www.britannica.com",
    "nih": "https://www.nih.gov",
    
    # Commercial/Entertainment
    "amazon": "https://www.amazon.com",
    "ebay": "https://www.ebay.com",
    "forbes": "https://www.forbes.com",
    "bloomberg": "https://www.bloomberg.com",
    "cnet": "https://www.cnet.com",
}

# ===== BACKGROUND SITES =====
# 50 unmonitored websites for open-world evaluation
# These are NOT used for training - used to test false positive rates
# NOTE: Removed duplicates and sites that may trigger verification
BACKGROUND_SITES = {
    # Tech/News
    "msn": "https://www.msn.com",
    "aol": "https://www.aol.com",
    "cnet": "https://www.cnet.com",
    "techradar": "https://www.techradar.com",
    "engadget": "https://www.engadget.com",
    "mashable": "https://www.mashable.com",
    "buzzfeed": "https://www.buzzfeed.com",
    "vice": "https://www.vice.com",
    "slate": "https://www.slate.com",
    "wired": "https://www.wired.com",
    "arstechnica": "https://arstechnica.com",
    "theverge": "https://www.theverge.com",
    "gizmodo": "https://www.gizmodo.com",
    "lifehacker": "https://lifehacker.com",
    "qz": "https://qz.com",
    "time": "https://time.com",
    "npr": "https://www.npr.org",
    "nbcnews": "https://www.nbcnews.com",
    "abcnews": "https://abcnews.go.com",
    "cbsnews": "https://www.cbsnews.com",
    "latimes": "https://www.latimes.com",
    
    # International
    "dailymail": "https://www.dailymail.co.uk",
    "express": "https://www.express.co.uk",
    "mirror": "https://www.mirror.co.uk",
    "telegraph": "https://www.telegraph.co.uk",
    "independent": "https://www.independent.co.uk",
    "metro": "https://metro.co.uk",
    "newsweek": "https://www.newsweek.com",
    "rawstory": "https://www.rawstory.com",
    "salon": "https://www.salon.com",
    "dailykos": "https://www.dailykos.com",
    "breitbart": "https://www.breitbart.com",
    "drudge": "https://www.drudgereport.com",
    "dailywire": "https://www.dailywire.com",
    "reason": "https://reason.com",
    "jacobin": "https://jacobin.com",
    "nypost": "https://nypost.com",
    "rt": "https://www.rt.com",
    "spiegel": "https://www.spiegel.de",
    "lemonde": "https://www.lemonde.fr",
    
    # Other
    "newsgoogle": "https://news.google.com",
    "reddit": "https://www.reddit.com",
    "tumblr": "https://www.tumblr.com",
    "flickr": "https://www.flickr.com",
    "imdb": "https://www.imdb.com",
    "tripadvisor": "https://www.tripadvisor.com",
    "yelp": "https://www.yelp.com",
    "zillow": "https://www.zillow.com",
}
