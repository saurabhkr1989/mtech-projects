"""
File: config.py
Project: YouTube Video Fingerprinting over Tor (version 2 of the CUMUL WFP project)

Purpose:
    The ONLY file that needs editing between runs. Every timing value,
    path and threshold used by the other modules lives here with its rationale.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import os

# All data paths are anchored to this folder, so the app behaves the same
# whichever directory it is launched from (version 1 wrote into the parent
# folder because paths were built relative to the module location).
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Folder that CONTAINS this app folder. Tor Browser, the driver and (in the
# portable package) Python sit next to the app folder, so every path below is
# relative and the folder can be copied to any Windows laptop / drive:
#   <PACKAGE_DIR>\TorBrowser\Tor Browser\...   Tor Browser bundle
#   <PACKAGE_DIR>\drivers\geckodriver.exe      (portable package only)
#   <PACKAGE_DIR>\python\python.exe            (portable package only)
#   <PACKAGE_DIR>\<this app folder>\
PACKAGE_DIR = os.path.dirname(PROJECT_DIR)

# ===== VIDEO TO CAPTURE =====
# Paste the YouTube link here. Accepted forms:
#   https://www.youtube.com/watch?v=VIDEO_ID
#   https://youtu.be/VIDEO_ID
#   https://www.youtube.com/shorts/VIDEO_ID
YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v=17DNn5QDbAw&t"

# ===== MODE =====
# "single"  : every instance plays YOUTUBE_VIDEO_URL (above).
# "playlist": every instance plays ONE video chosen at random from
#             YOUTUBE_PLAYLIST_URL. Random periods and the random number of
#             parallel browsers apply exactly as in "single" mode.
MODE = "single"

# Playlist link, e.g. https://www.youtube.com/playlist?list=PLxxxxxxxx
# (a watch link containing &list=... works too).
YOUTUBE_PLAYLIST_URL = "https://www.youtube.com/playlist?list=PASTE_PLAYLIST_ID_HERE"

# The playlist's videos are read once from the playlist page (over Tor) and
# kept in data/raw/<VIDEO_LABEL>/playlist_videos.csv; later runs reuse it so
# video numbers (v01, v02, ...) stay the same. True = read the page again.
PLAYLIST_REFRESH = False

# Optional: list the playlist's videos by hand instead of reading the page.
# PLAYLIST_VIDEO_URLS = ["https://www.youtube.com/watch?v=...", ...]
PLAYLIST_VIDEO_URLS = []

# Videos per circuit (playlist mode): once a circuit and browser are up,
# this many playlist videos are played one after the other in that browser
# (one capture each) before the next session starts on a new circuit - for
# short videos this saves most of the circuit/browser start-up time.
#   (10, 15) : a random number from 10 to 15 per session
#   12       : always 12
#   1        : one video per circuit (earlier behaviour)
# A failed video ends the session; it and the session's remaining videos
# are done in a later session on a new circuit. Log columns: session,
# position_in_session (1 = cold start, later = warm browser/connections).
VIDEOS_PER_CIRCUIT = (10, 15)
# How a viewer gets from one video to the next in a session:
#   "click"    : a random other video clicked in the playlist panel
#   "in_order" : the player's Next button (playlist order, like autoplay)
NEXT_VIDEO = "click"
# Pause on the finished video's page before the next one is chosen
# (seconds, random; part of the next video's capture, like dwell_s).
BETWEEN_VIDEOS_SECONDS = (2, 8)

# ===== NAVIGATION =====
# "browse": reach the video like a viewer - open an entry page, stay a
#           random time and scroll, then CLICK the video's thumbnail:
#             single mode   : the video's channel, Videos tab
#             playlist mode : the playlist page
#           If the thumbnail is not found: YouTube search for the title, then
#           the link opened directly (log column "navigation" says which).
#           The click time is logged (click_epoch, click_offset_s) so each
#           trace can be used whole or cut at the click.
# "direct": open the video link directly (earlier behaviour).
NAVIGATION = "browse"

# Channel of the single-mode video. None = looked up automatically (once,
# via YouTube's oEmbed service over Tor) and kept in data/video_info.json.
YOUTUBE_CHANNEL_URL = None

BROWSE_DWELL_SECONDS = (3, 15)    # random time on the entry page before the click
BROWSE_SCROLLS = (0, 3)           # random number of scrolls during that time
BROWSE_MAX_SEARCH_SCROLLS = 15    # scrolls down the entry page to find an older video

# Short name used in capture file names: <VIDEO_LABEL>_<instance>.pcapng
# Use letters, digits and hyphens only (no underscore - the underscore
# separates the label from the instance number in file names).
VIDEO_LABEL = "video1"

# Number of SUCCESSFUL captures (complete playbacks) to collect - for the
# video ("single"), or in total over the playlist's videos ("playlist"). Failed attempts are retried on a new circuit until this many
# successful capture files exist. Each instance is a fresh browser on a
# fresh Tor circuit, giving the classifier independent samples.
INSTANCES = 1000

# How many instances run AT THE SAME TIME. Each parallel slot has its own
# tor.exe, its own Tor Browser window and its own capture, so the traces do
# not mix (every slot's traffic leaves on its own TCP connection(s) to its
# own guard, and the capture filter is pinned to exactly those connections).
# Each slot needs ~0.5-1 GB RAM and its share of bandwidth; 5 is a sensible
# maximum for a laptop on home broadband.
PARALLEL_INSTANCES = 5

# ===== RANDOM PERIODS =====
# True: the run is divided into periods of random length; in each period a
# random number of browsers (within PARALLEL_RANGE, never more than
# PARALLEL_INSTANCES) play videos at the same time - an irregular, more
# natural browsing rhythm instead of a constant 5. Playing videos always
# finish; when a period allows fewer browsers, the extra slots wait.
# False: always PARALLEL_INSTANCES browsers.
RANDOM_PERIODS_ENABLED = True
PERIOD_MINUTES_RANGE = (10, 40)   # length of each period, minutes
PARALLEL_RANGE = (1, 5)           # browsers in parallel within a period

# Seconds between starting consecutive slots, so 5 tors / 5 browsers do not
# all start in the same instant (CPU spike, YouTube rate limiting).
SLOT_START_STAGGER_SECONDS = 20

# ===== BROWSER =====
# "tor_browser" : the real Tor Browser (firefox.exe from the bundle), driven
#                 by Selenium + geckodriver, using the Tor process this app starts.
# "chrome_tor"  : Google Chrome routed through the same Tor SOCKS port
#                 (the method used in version 1). Fallback if Tor Browser
#                 automation fails on this machine.
BROWSER = "tor_browser"

TBB_DIR = os.path.join(PACKAGE_DIR, "TorBrowser", "Tor Browser")
TBB_FIREFOX_EXE = os.path.join(TBB_DIR, "Browser", "firefox.exe")
TBB_PROFILE_DIR = os.path.join(TBB_DIR, "Browser", "TorBrowser", "Data", "Browser", "profile.default")
TOR_EXE_PATH = os.path.join(TBB_DIR, "Browser", "TorBrowser", "Tor", "tor.exe")
TOR_GEOIP_FILE = os.path.join(TBB_DIR, "Browser", "TorBrowser", "Data", "Tor", "geoip")
TOR_GEOIP6_FILE = os.path.join(TBB_DIR, "Browser", "TorBrowser", "Data", "Tor", "geoip6")

# Bundled geckodriver if present (portable package), else None = Selenium
# Manager downloads the matching driver automatically (needs internet).
_BUNDLED_GECKODRIVER = os.path.join(PACKAGE_DIR, "drivers", "geckodriver.exe")
GECKODRIVER_PATH = _BUNDLED_GECKODRIVER if os.path.exists(_BUNDLED_GECKODRIVER) else None
CHROMEDRIVER_PATH = None

# How the browser windows appear, so they do not interrupt work on the laptop:
#   "behind"   : a normal, real window that opens BEHIND your current work;
#                the keyboard focus is handed back to the window you were
#                using. The windows stay on the taskbar - click one to watch
#                the video playing. (default)
#   "offscreen": a real window placed outside the visible screen.
#   "headless" : no window at all.
#   "visible"  : normal window that comes to the front (Windows' default).
BROWSER_WINDOW = "behind"

# Window size used in every mode. YouTube's automatic quality depends on the
# player size, so a fixed size keeps instances comparable.
BROWSER_WINDOW_SIZE = (1280, 720)

# Start every video muted. Muting does not change network traffic (the
# audio stream is still downloaded); it also lets the browser autoplay
# without a user click. Applied three ways: browser volume 0, the YouTube
# player's own mute button, and the <video> element's muted flag.
MUTE_AUDIO = True

# Seconds to let the freshly launched browser settle (extensions, Tor
# Browser start-up checks) BEFORE the capture starts, so start-up noise is
# not mixed into the video trace.
BROWSER_SETTLE_SECONDS = 5

# ===== TOR =====
# Slot k (0, 1, 2 ...) runs its own tor.exe on
#     SOCKS   port TOR_BASE_SOCKS_PORT   + 2k   (9250, 9252, 9254 ...)
#     control port TOR_BASE_SOCKS_PORT+1 + 2k   (9251, 9253, 9255 ...)
# with data folder data/tor_data/slot<k>. These ports are deliberately away
# from 9050/9051 (your Tor Browser torrc) and 9150/9151 (Tor Browser
# default), so a Tor Browser opened by hand does not clash with the app.
TOR_BASE_SOCKS_PORT = 9250
TOR_DATA_DIR = os.path.join(PROJECT_DIR, "data", "tor_data")

# Maximum seconds to wait for tor to reach "Bootstrapped 100%".
TOR_BOOTSTRAP_TIMEOUT = 180

# Seconds to wait after NEWNYM so tor builds the new circuit before the
# browser opens its first connection. Tor itself rate-limits NEWNYM to one
# per 10 s; the code also honours that limit.
CIRCUIT_WAIT_SECONDS = 5

# ===== PLAYBACK =====
# ----- Video resolution -----
# None            : YouTube's Auto - adapts to Tor's bandwidth, so the
#                   resolution varies between captures.
# "720p"          : every capture at 720p.
# ["360p", "720p", "1080p"] : several resolutions in one run; each capture
#                   gets one of them (VIDEO_QUALITY_SELECTION below).
# Names: 144p 240p 360p 480p 720p 1080p 1440p 2160p (YouTube's own codes
# such as "hd720" work too). The log records the requested resolution
# (quality_requested), the one actually played (quality) and the share of
# playback at the requested one (quality_share).
VIDEO_QUALITY = None

# With a list above: "random" = a random one per capture;
# "rotate" = in turn (360p, 720p, 1080p, 360p, ...), equal numbers of each.
VIDEO_QUALITY_SELECTION = "random"

# A video that does not offer the requested resolution is played at the
# nearest one by YouTube. False = keep such captures (the log shows what
# was played); True = discard them (less than 90 % at the requested one).
QUALITY_MUST_MATCH = False

# ----- Playback speed -----
# 1.0             : normal speed (default).
# 1.5             : every capture at 1.5x.
# [1.0, 1.25, 1.5, 2.0] : several speeds in one run; each capture gets one
#                   (PLAYBACK_SPEED_SELECTION: "random" or "rotate").
# Speeds of YouTube's speed menu: 0.25 0.5 0.75 1 1.25 1.5 1.75 2.
# Faster playback makes the player fetch video faster (and slower, slower),
# which changes how the data arrives. The log records speed_requested, the
# speed actually in effect (speed) and when it was changed (speed_changed_at_s).
PLAYBACK_SPEED = 1.0
PLAYBACK_SPEED_SELECTION = "random"
# Like a viewer who opens the speed menu shortly after the video starts:
# normal speed until a random point within this range (seconds into the
# video), then the chosen speed. (0, 0) = the chosen speed from the start.
SPEED_CHANGE_AFTER_SECONDS = (3, 10)

# ----- Adverts -----
# A skippable advert is skipped the way a viewer does: a real mouse click on
# "Skip" as soon as it is offered, after a human reaction time picked at
# random from this range (seconds). Unskippable adverts play through. The
# log records ads_count, ads_skipped and ad_seconds per capture.
AD_SKIP_REACTION_SECONDS = (0.4, 1.5)

# Seconds to wait for the page load event (YouTube over Tor can be slow).
PAGE_LOAD_TIMEOUT = 90

# Seconds to wait for the YouTube player and <video> element to appear.
PLAYER_READY_TIMEOUT = 90

# If the playback position does not advance for this many seconds
# (endless buffering), the attempt is abandoned and retried.
STALL_TIMEOUT = 120

# Playback counts as complete when position >= duration - END_TOLERANCE.
# YouTube sometimes stops a fraction of a second before the reported end.
END_TOLERANCE_SECONDS = 1.0

# Upper bound on wall-clock time per playback = duration x this factor
# (+ PLAYER_READY_TIMEOUT). Covers ads and rebuffering over Tor.
MAX_PLAYBACK_FACTOR = 3.0

# Seconds between player-state checks.
POLL_INTERVAL_SECONDS = 1.0

# Seconds between "playing 01:23 / 06:42" progress lines (per slot).
PROGRESS_PRINT_INTERVAL_SECONDS = 15

# What to do when YouTube stops the video part-way with an error such as
# "Something went wrong. Refresh or try again later" (common over Tor,
# often around the 1-minute mark):
#   "resume"  : reload the page at the position reached and keep playing,
#               up to MAX_RESUMES_PER_PLAYBACK times. The trace then
#               contains the reload(s); the log column "resumes" says how
#               many, so such traces can be kept apart later.
#   "discard" : abandon the attempt and retry from 0:00 on a new circuit.
ON_PLAYER_ERROR = "resume"
MAX_RESUMES_PER_PLAYBACK = 10

# After this many seconds of playback, a capture that has recorded no
# packets aborts the attempt (wrong interface / filter) instead of wasting
# the whole video.
CAPTURE_HEALTH_CHECK_SECONDS = 30

# Seconds to keep capturing after the video ends, so the final
# packets / connection teardown are included in the trace.
POST_VIDEO_WAIT_SECONDS = 3

# ===== RETRIES =====
# Failed attempts are retried on a new circuit as often as needed, until
# INSTANCES successful captures exist. Two kinds of failure (failure_policy.py):
#  - SITE REFUSAL ("not a bot", Google "unusual traffic", player errors,
#    too slow): expected over Tor, never stops the run. After this many in a
#    row (all slots together) every slot pauses for a cool-down, starting at
#    COOLDOWN_MINUTES_START and doubling up to COOLDOWN_MINUTES_MAX.
REFUSALS_BEFORE_COOLDOWN = 15
COOLDOWN_MINUTES_START = 5
COOLDOWN_MINUTES_MAX = 30
# The run stops only after this many cool-downs without a single success.
MAX_COOLDOWNS_IN_A_ROW = 8
#  - TECHNICAL (capture records nothing, browser/tor not starting): this
#    many in a row stop the run - retrying cannot help.
MAX_CONSECUTIVE_FAILURES = 25

# Screenshot + page text saved to data/debug/ for the first this-many
# failures of each kind, so failures can be seen rather than guessed.
DEBUG_SNAPSHOTS_PER_REASON = 3

# Random pause (seconds) between instances in the same slot.
INTER_INSTANCE_DELAY_RANGE = (5, 15)

# ===== PACKET CAPTURE =====
# "auto"     : before every run, test dumpcap (only if Wireshark + Npcap are
#              installed) and then the built-in raw socket, with one test
#              connection each, and use the first that actually sees it
# "rawsocket": built into Windows, nothing to install (needs Administrator)
# "dumpcap"  : Wireshark's dumpcap + Npcap driver
CAPTURE_ENGINE = "auto"
DUMPCAP_PATH = r"C:\Program Files\Wireshark\dumpcap.exe"

# None = the interface that carries the default route (auto-detected).
# Otherwise its IP address, description or \Device\NPF_{GUID} (see "Check setup").
CAPTURE_INTERFACE = None

# Bytes kept per packet. The payload is Tor-encrypted and
# useless; sizes/directions/timestamps come from headers, and the original
# packet length is still recorded. 128 B keeps files ~10x smaller.
CAPTURE_SNAPLEN = 128

# A completed playback whose capture has fewer packets than this is
# treated as a failed capture (wrong interface, filter missed the guard).
MIN_PACKETS = 1000

# ===== OUTPUT =====
DATA_RAW_DIR = os.path.join(PROJECT_DIR, "data", "raw")
COLLECTION_LOG_PATH = os.path.join(PROJECT_DIR, "data", "collection_log.csv")
