# YouTube Video Fingerprinting over Tor — capture tool (version 2)

Plays one configured YouTube video in Tor Browser, muted, start to finish, many times
(5 at once by default), and saves one packet capture per complete playback. These
captures are the training data for the fingerprinting classifier.

## Parallel slots
`PARALLEL_INSTANCES` slots run at the same time. Each slot has:
- its own `tor.exe` (ports 9250/9251, 9252/9253, ... ; data in `data/tor_data/slot<k>`)
- its own Tor Browser window
- its own capture, filtered to that tor's own TCP connections (remote IP + local port),
  so the 5 videos never mix in one file

Slots take instance numbers from a shared queue until `INSTANCES` are complete.

## What one instance does
1. New Tor circuit (NEWNYM) on the slot's tor
2. Fresh Tor Browser (temporary copy of the bundle profile → empty cache), muted
3. Capture starts on the slot's tor connections only
4. Opens `YOUTUBE_VIDEO_URL`, handles cookie consent, skips ads, starts it through
   YouTube's own player (muted) and keeps it playing
5. If YouTube stops part-way with "Something went wrong", reloads at the position
   reached and continues (`ON_PLAYER_ERROR = "resume"`, counted in the log)
6. Waits until the player reports the video has ended
7. Capture stops, browser closes (left-over windows are killed)
8. File kept only if the video played to the end and the capture has ≥ `MIN_PACKETS`
   packets. Otherwise discarded and retried on a new circuit - as often as needed,
   until `INSTANCES` (default 1000) successful captures exist. The run stops only if
   `MAX_CONSECUTIVE_FAILURES` attempts in a row fail (systematic problem).
   A capture that records nothing in the first 30 s of playback aborts the attempt.

## Different circuits for the 5 parallel browsers
- each slot is a separate tor process -> separate circuits by construction
- no two running slots share a guard (a slot whose tor picks a guard already in use
  restarts its tor with a fresh guard)
- NEWNYM + fresh browser before every attempt -> new circuit per instance
- the circuit actually carrying the YouTube traffic (guard > middle > exit) is
  logged per attempt in `collection_log.csv` (column `circuit_path`)

## Packet capture
Before every run the app captures one test connection and uses the first engine that sees it:
- `dumpcap` - only if Wireshark + Npcap are installed
- `rawsocket` - built into Windows (raw socket + SIO_RCVALL), nothing to install;
  one receiver thread routes each packet to the file of the slot it belongs to.
  Output `.pcap` (link type RAW-IP), opens in Wireshark.

## Setup
- Portable package (`YouTubeWFP_Portable`): nothing to install - double-click `Run_YouTubeWFP.bat`.
- This development copy: `..\cumul_venv` (selenium, stem), Tor Browser in `..\TorBrowser`.

## Run
Open the terminal **as Administrator** (packet capture needs it), then:
```
cd "D:\MTech Assignments\Sem II\Nw System Security\Project\youtube_wfp"
..\cumul_venv\Scripts\activate
python main.py check        # verify everything first
python main.py collect 1    # one test instance
python main.py collect      # all INSTANCES, PARALLEL_INSTANCES at a time
python main.py status
```
Or plain `python main.py` for the menu. Ctrl+C stops all slots cleanly; run again to resume.

## Browsing mode (default)
`NAVIGATION = "browse"`: the video is reached like a viewer does - entry page (the video's channel,
Videos tab; the playlist page in playlist mode) -> random wait and scrolling -> click the thumbnail.
YouTube then changes the page in place (no site reload), as in real viewing. Fallbacks: YouTube
search for the title, then the link opened directly. Log columns: `navigation`, `entry_url`, `dwell_s`,
`click_epoch` (epoch seconds, same clock as the pcap timestamps), `click_offset_s` (seconds after the
capture start) - use the whole trace, or cut it at the click. `NAVIGATION = "direct"` = earlier behaviour.

## Playlist mode
`MODE = "playlist"` + `YOUTUBE_PLAYLIST_URL`: every instance plays one video of the playlist
from the playlist, to its end. Random periods and the random number of parallel browsers apply
as usual. The playlist page is read once over Tor; the video list is kept in
`data/raw/<VIDEO_LABEL>/playlist_videos.csv` (v01, v02, ... -> video id, title), reused on later
runs (`PLAYLIST_REFRESH = True` reads it again; `PLAYLIST_VIDEO_URLS` lists videos by hand).
Captures: `data/raw/<VIDEO_LABEL>/vNN/<VIDEO_LABEL>_NNN.pcapng` - one folder (class) per video.
`INSTANCES` is the total over the playlist.

Videos per circuit: `VIDEOS_PER_CIRCUIT = (10, 15)` plays a random 10-15 playlist videos in one
browser on one circuit (one capture each) before a new session on a new circuit; `12` = fixed,
`1` = one video per circuit. First video of a session: with `NAVIGATION = "browse"` the playlist page is opened and one of
the videos in view is clicked (no searching); next ones
from the previous video's watch page - `NEXT_VIDEO = "click"` (a random other video in the
playlist panel) or `"in_order"` (the player's Next button). `BETWEEN_VIDEOS_SECONDS = (2, 8)`:
pause before the next one (part of its capture). Each video is held a fraction of a second
before its end so the playlist cannot start the next one inside the capture. A failed video ends
the session; it and the unplayed ones go to a new session. Log: `session`, `position_in_session`
(1 = cold browser, later = warm) - split training/test by session.

## Edit only `config.py`
- `YOUTUBE_VIDEO_URL`, `VIDEO_LABEL`, `INSTANCES`, `PARALLEL_INSTANCES`
- `MUTE_AUDIO` - start every video muted (default True)
- `BROWSER_WINDOW` - `"behind"` (default: real window that opens behind your current work,
  focus handed back to you; click it on the taskbar to watch), `"offscreen"`, `"headless"`
  (no window) or `"visible"` (comes to the front)
- `ON_PLAYER_ERROR` - `"resume"` (reload at position) or `"discard"` (retry from 0:00)
- `VIDEO_QUALITY` - resolution: `None` (Auto), one (`"720p"`) or a list (`["360p", "720p", "1080p"]`,
  one per capture, `VIDEO_QUALITY_SELECTION = "random"` or `"rotate"`); log columns `quality_requested`,
  `quality` (actually played), `quality_share`; `QUALITY_MUST_MATCH = True` discards captures not played
  at the requested resolution
- `PLAYBACK_SPEED` - `1.0` (normal), one speed (`1.5`) or a list (`[1.0, 1.25, 1.5, 2.0]`, one per
  capture, `PLAYBACK_SPEED_SELECTION = "random"` or `"rotate"`); speeds 0.25-2 as in YouTube's menu;
  changed at a random point `SPEED_CHANGE_AFTER_SECONDS = (3, 10)` into the video (`(0, 0)` = from the
  start), re-applied if the player resets it (e.g. after an advert); log columns `speed_requested`,
  `speed` (in effect), `speed_changed_at_s`
- `BROWSER` - `"tor_browser"` (default) or `"chrome_tor"` (fallback, the version 1 method)

## Output
- `data/raw/<label>_<NNN>.pcap` / `.pcapng` - one file per complete playback (headers only)
- `data/collection_log.csv` - one row per attempt: slot, status, reason, video duration,
  how far it played, resumes, ads seen, rebuffering, packets, bytes, capture filter,
  tor connections, local IP. Local IP + tor connection give packet direction for
  feature extraction (from the tor relay = incoming).

## Known limits
- YouTube often shows "Sign in to confirm you're not a bot" or "Something went wrong"
  to Tor users; the first is retried on a new circuit, the second resumed.
- A resumed playback contains a page reload in its trace; filter on `resumes = 0` if
  only uninterrupted traces are wanted.
- Ads that cannot be skipped are part of that trace (`ads_seen` in the log).
- Live streams have no end and are rejected.
