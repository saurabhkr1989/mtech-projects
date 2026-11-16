"""
File: config.py
Project: Twitter/X Post Fingerprinting (no Tor) - capture tool

Purpose:
    The ONLY file that needs editing between runs. Every timing value,
    path and threshold used by the other modules lives here with its rationale.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import os

# Paths are relative to the package, so the folder can be copied anywhere:
#   <PACKAGE_DIR>\Firefox\firefox.exe        bundled Firefox ESR
#   <PACKAGE_DIR>\drivers\geckodriver.exe    bundled driver
#   <PACKAGE_DIR>\python\python.exe          bundled Python
#   <PACKAGE_DIR>\twitter_wfp\               this app
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.dirname(PROJECT_DIR)

# ===== POSTS TO CAPTURE =====
# One entry per post: "label": "link". The label becomes the class name and
# the capture sub-folder (data\raw\<label>\). Labels: letters, digits and
# hyphens only (no underscore - it separates label and instance number).
# Links: https://x.com/<user>/status/<id>  (twitter.com links work too)
TWITTER_POSTS = {
    "post1": "https://x.com/saurabhkr1989/status/2120458599269052646",
    "post2": "https://x.com/saurabhkr1989/status/2120475284348805306",
    "post3": "https://x.com/saurabhkr1989/status/2121325800200994925",
    "post4": "https://x.com/KedgyKaruna/status/2121329837189267922",
}

# Each browser session loads the post once and then refreshes it this many
# times; every load is captured into its own file and counts as one
# instance (10 refreshes = 11 captures per circuit). Refreshes behave like
# pressing F5: the browser reuses its cache, so later loads transfer less
# than the first - the log column load_in_session (0 = first load) tells
# them apart.
REFRESHES_PER_SESSION = 2

# ===== NAVIGATION =====
# "browse": the FIRST load of every session reaches the post like a person
#           does - open the poster's profile, stay a random time and scroll,
#           then CLICK the post (its timestamp link). The refreshes that
#           follow are F5 on the post page. If the post is not on the
#           profile (X shows logged-out visitors only part of it; replies
#           are never on the main profile tab) the link is opened directly
#           and the log says "direct-fallback".
#           The click time is logged (click_epoch, click_offset_s) so each
#           trace can be used whole or cut at the click.
# "direct": open the post link directly (earlier behaviour).
NAVIGATION = "browse"
BROWSE_DWELL_SECONDS = (3, 15)    # random time on the profile before the click
BROWSE_SCROLLS = (0, 3)           # random number of scrolls during that time
BROWSE_MAX_SEARCH_SCROLLS = 10    # scrolls down the profile to find the post

# SUCCESSFUL captures to collect for EACH post. Failed attempts are retried
# until this many capture files exist per post. Posts are interleaved
# (post1, post2, post1, ...) so time-of-day effects are spread evenly.
INSTANCES_PER_POST = 1000

# Browsers running AT THE SAME TIME. Each capture is split by PROCESS: it
# keeps only packets of TCP connections opened by its own slot - the slot's
# tor.exe (Tor mode) or its own Firefox and child processes (direct mode) -
# read from Windows' connection table several times a second.
PARALLEL_INSTANCES = 5

# Seconds between starting consecutive slots (avoids 5 launches at once).
SLOT_START_STAGGER_SECONDS = 10

# ===== BROWSER =====
# "tor_browser"     : Tor Browser through Tor (default). Each parallel slot
#                     runs its own tor.exe; every instance gets a NEW circuit
#                     and a fresh browser, so visits come from many different
#                     Tor exits instead of this laptop's one IP address.
# "firefox_private" : bundled Firefox in a private window, direct (no Tor).
BROWSER = "tor_browser"

TBB_DIR = os.path.join(PACKAGE_DIR, "TorBrowser", "Tor Browser")
TBB_FIREFOX_EXE = os.path.join(TBB_DIR, "Browser", "firefox.exe")
TBB_PROFILE_DIR = os.path.join(TBB_DIR, "Browser", "TorBrowser", "Data", "Browser", "profile.default")
TOR_EXE_PATH = os.path.join(TBB_DIR, "Browser", "TorBrowser", "Tor", "tor.exe")
TOR_GEOIP_FILE = os.path.join(TBB_DIR, "Browser", "TorBrowser", "Data", "Tor", "geoip")
TOR_GEOIP6_FILE = os.path.join(TBB_DIR, "Browser", "TorBrowser", "Data", "Tor", "geoip6")
FIREFOX_EXE = os.path.join(PACKAGE_DIR, "Firefox", "firefox.exe")
_BUNDLED_GECKODRIVER = os.path.join(PACKAGE_DIR, "drivers", "geckodriver.exe")
GECKODRIVER_PATH = _BUNDLED_GECKODRIVER if os.path.exists(_BUNDLED_GECKODRIVER) else None

# "behind"   : normal window that opens BEHIND your current work (focus is
#              handed back to the window you were using); visible on the
#              taskbar - click it to watch. (default)
# "visible"  : normal window that comes to the front.
# "offscreen": real window placed outside the visible screen.
# "headless" : no window.
BROWSER_WINDOW = "behind"
BROWSER_WINDOW_SIZE = (1280, 900)

# Start videos muted (network traffic is identical; avoids autoplay blocks).
MUTE_AUDIO = True

# Seconds to let a freshly launched browser settle before capture starts.
BROWSER_SETTLE_SECONDS = 5

# ===== TOR (BROWSER = "tor_browser") =====
# Slot k runs its own tor.exe on SOCKS port TOR_BASE_SOCKS_PORT + 2k and
# control port +1 (9350/9351, 9352/9353, ...), data in data/tor_data/slot<k>.
# 9350+ keeps clear of the YouTube app (9250+) so both can run together, and
# of 9050/9150 (Tor Browser opened by hand).
TOR_BASE_SOCKS_PORT = 9350
TOR_DATA_DIR = os.path.join(PROJECT_DIR, "data", "tor_data")
TOR_BOOTSTRAP_TIMEOUT = 180
# Seconds to wait after requesting a new circuit (NEWNYM) before the browser
# opens its first connection. Tor itself allows one NEWNYM per ~10 s.
CIRCUIT_WAIT_SECONDS = 5

# ===== PAGE / VIDEO =====
# Seconds to wait for the page load event (Tor is slower than direct).
PAGE_LOAD_TIMEOUT = 90

# Seconds to wait for the post itself (the tweet article) to appear.
POST_READY_TIMEOUT = 60

# Post WITHOUT video: "fully loaded" = page complete, post shown, all its
# images loaded, and no new network request for this many seconds.
NETWORK_IDLE_SECONDS = 5

# Upper bound for a post without video. If the page keeps making requests
# (X polls in the background) but the post and its images are complete by
# then, the capture is still accepted (log says so).
MAX_PAGE_LOAD_SECONDS = 90

# Post WITH video: play it to the end (True), or treat it like a post
# without video (False).
PLAY_VIDEO_TO_END = True

# Seconds to wait (after the post appears) for a video player to show up
# before treating the post as having no video.
VIDEO_APPEAR_GRACE_SECONDS = 5

# Video stalls (no progress) longer than this abandon the attempt.
STALL_TIMEOUT = 60

# Fallback completion: within this many seconds of the end for 3 s without
# the player's own "ended" flag.
END_TOLERANCE_SECONDS = 0.5

# Wall-clock limit for a video = duration x factor + POST_READY_TIMEOUT.
MAX_PLAYBACK_FACTOR = 3.0

POLL_INTERVAL_SECONDS = 1.0
PROGRESS_PRINT_INTERVAL_SECONDS = 15

# Seconds to keep capturing after the post/video finished (tail packets).
POST_LOAD_WAIT_SECONDS = 3

# ===== RETRIES =====
# A load that fails (login wall, "Something went wrong", post not shown)
# ends that browser session at once; a new session - new circuit, new
# browser - starts immediately with the remaining instances. No waiting.
# Optional cool-down instead (False = off): after REFUSALS_BEFORE_COOLDOWN
# refusals in a row all slots pause, 5 min doubling up to 30 min.
COOLDOWN_ENABLED = False
REFUSALS_BEFORE_COOLDOWN = 15
COOLDOWN_MINUTES_START = 5
COOLDOWN_MINUTES_MAX = 30
MAX_COOLDOWNS_IN_A_ROW = 8
# Safety stop: this many refusals in a row without a single success means
# X refuses everything - the run stops instead of looping for hours.
MAX_REFUSALS_WITHOUT_SUCCESS = 300
#  - TECHNICAL (capture records nothing, browser not starting): this many
#    in a row stop the run - retrying cannot help.
MAX_CONSECUTIVE_FAILURES = 25

# Screenshot + page text saved to data/debug/ for the first this-many
# failures of each kind, so failures can be seen rather than guessed.
DEBUG_SNAPSHOTS_PER_REASON = 3

# Random pause (seconds) between instances in the same slot.
INTER_INSTANCE_DELAY_RANGE = (2, 6)

# ===== PACKET CAPTURE =====
# "auto"     : test dumpcap (only if Wireshark + Npcap are installed) and the
#              built-in raw socket with one test connection, use the first
#              that works
# "rawsocket": built into Windows, nothing to install (needs Administrator)
# "dumpcap"  : Wireshark's dumpcap + Npcap driver
CAPTURE_ENGINE = "auto"
DUMPCAP_PATH = r"C:\Program Files\Wireshark\dumpcap.exe"

# None = the interface carrying the default route; else its IP address,
# description or \Device\NPF_{GUID} (see "Check setup").
CAPTURE_INTERFACE = None

# Bytes of each packet kept (headers; payload is TLS-encrypted). The
# original packet length is always recorded.
CAPTURE_SNAPLEN = 128

# A finished attempt whose capture has fewer packets is rejected.
MIN_PACKETS = 100

# After this many seconds on the page, a capture with no packet at all
# aborts the attempt (capture not working) instead of waiting for the end.
CAPTURE_HEALTH_CHECK_SECONDS = 20

# ===== OUTPUT =====
DATA_RAW_DIR = os.path.join(PROJECT_DIR, "data", "raw")
COLLECTION_LOG_PATH = os.path.join(PROJECT_DIR, "data", "collection_log.csv")
