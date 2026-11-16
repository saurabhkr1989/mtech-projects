"""
File: youtube.py
Purpose:
    Opens the configured YouTube video in an already-launched browser and
    keeps it playing, muted, until the main video has genuinely reached its end.

How "played completely" is decided (checked every POLL_INTERVAL_SECONDS
through JavaScript on the page's <video> element):
    - not during an advert (the player gets the CSS class "ad-showing");
    - video.ended is true, OR the position wrapped back to the start after
      reaching >= 97 % (Shorts loop forever and never report "ended"),
      OR (fallback) the position stayed within END_TOLERANCE_SECONDS of the
      end for END_GRACE_SECONDS without "ended" being raised.

What keeps it playing:
    - start through the YouTube player's own API (mute() + playVideo()) AND
      the <video> element (muted + play()); if it is ever found paused it is
      started again;
    - adverts are skipped when a Skip button appears;
    - "Continue watching?" dialogs are confirmed;
    - a mid-video YouTube error ("Something went wrong...") is resumed by
      reloading the page at the position reached (config.ON_PLAYER_ERROR).
Bot checks before the video starts, endless buffering or a page that never
loads end the attempt; the caller discards that capture and retries.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import random
import re
import time
from collections import Counter
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from selenium.common.exceptions import (ElementClickInterceptedException, ElementNotInteractableException,
                                        StaleElementReferenceException, TimeoutException, WebDriverException)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

import config

# Messages YouTube / Google show instead of the video, typically to Tor
# exits. Matched case-insensitively against the player area text.
BLOCKED_PLAYBACK_PHRASES = [
    "not a bot",
    "sign in to confirm",
    "unusual traffic",
    "video unavailable",
    "this video is unavailable",
    "this video is private",
    "this video has been removed",
    "playback on other websites has been disabled",
    "something went wrong",
    "an error occurred",
]

# Errors after which the video itself is fine and a reload continues it
# (as opposed to "video unavailable" / "private", where reloading is useless).
RESUMABLE_ERROR_PHRASES = ["something went wrong", "an error occurred", "refresh or try again"]

# Fraction of the duration after which a jump back to the start is read as
# "the video finished and looped" (YouTube Shorts behaviour).
LOOP_COMPLETION_FRACTION = 0.97

# Seconds to wait, once the position is within END_TOLERANCE of the end,
# for the player's "ended" flag before accepting the playback as complete.
END_GRACE_SECONDS = 3

# ---------------------------------------------------------------- JavaScript
PLAYER_STATE_SCRIPT = r"""
const player = document.getElementById('movie_player');
// The watch-page player first: channel and playlist pages create small
// hover-preview players with the same class, which must not be mistaken
// for the video being played.
const video = document.querySelector('#movie_player video') || document.querySelector('#shorts-player video')
              || document.querySelector('video.html5-main-video') || document.querySelector('video');
const errorBox = document.querySelector('.ytp-error');
const playerArea = document.querySelector('#player, ytd-player, #movie_player, #shorts-player');
// ytInitialPlayerResponse describes the page as FIRST loaded. After a click
// on a thumbnail YouTube changes the page in place (single-page app), so
// those details may belong to another page: use them only if they match the
// video in the address bar, else ask the player itself.
const urlVideoId = new URLSearchParams(location.search).get('v');
let details = null;
try { details = window.ytInitialPlayerResponse && window.ytInitialPlayerResponse.videoDetails; } catch (e) {}
if (details && urlVideoId && details.videoId !== urlVideoId) details = null;
let playerData = null;
try { playerData = (player && player.getVideoData) ? player.getVideoData() : null; } catch (e) {}
const playerVideoId = (playerData && playerData.video_id) || '';
if (playerData && urlVideoId && playerData.video_id && playerData.video_id !== urlVideoId) playerData = null;
let playerSeconds = null;
try { playerSeconds = (player && player.getDuration && !player.classList.contains('ad-showing')) ? player.getDuration() : null; } catch (e) {}
return {
  url: location.href,
  player_video_id: playerVideoId,
  has_video: !!video,
  ad_showing: !!(player && (player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting'))),
  current_time: video ? video.currentTime : null,
  element_duration: (video && isFinite(video.duration)) ? video.duration : null,
  ended: video ? video.ended : false,
  paused: video ? video.paused : true,
  muted: video ? video.muted : null,
  playback_rate: video ? video.playbackRate : null,
  error_text: (errorBox && errorBox.offsetParent !== null) ? errorBox.innerText.trim().slice(0, 300) : '',
  player_text: playerArea ? playerArea.innerText.slice(0, 2000) : '',
  page_length_seconds: details ? Number(details.lengthSeconds) : (playerSeconds || null),
  page_is_live: details ? (!!details.isLiveContent && !!details.isLive) : !!(playerData && playerData.isLive),
  page_title: details ? details.title : ((playerData && playerData.title) || document.title),
  quality: (player && player.getPlaybackQuality) ? player.getPlaybackQuality() : null
};
"""

# Cookie-consent screens. Two forms, both seen with Tor exits in the EU:
#   - a separate page on consent.youtube.com / consent.google.com;
#   - the in-page dialog "Before you continue to YouTube" (Reject all /
#     Accept all) laid OVER an already loaded page. It can appear at page
#     load or later, and while it is shown the video in the background is
#     paused (seen 15 Nov 2026).
# It does not appear on every visit, so the script first checks whether a
# consent page or a VISIBLE consent dialog is there and does nothing
# otherwise; it is run on every state check (dismiss_consent()). "Reject
# all" is preferred because it sets fewer cookies; "Accept all" otherwise.
CONSENT_CLICK_SCRIPT = r"""
const isVisible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
const scopes = [];
if (/^consent\./.test(location.hostname)) scopes.push(document);
for (const dialog of document.querySelectorAll(
       'ytd-consent-bump-v2-lightbox, ytd-consent-bump-v2-renderer, tp-yt-paper-dialog, [role="dialog"]')) {
  if (isVisible(dialog)) scopes.push(dialog);
}
if (!scopes.length) return null;
const patterns = [/^reject all$/i, /^accept all$/i, /^alle ablehnen$/i, /^alle akzeptieren$/i,
                  /^tout refuser$/i, /^tout accepter$/i, /^rechazar todo$/i, /^aceptar todo$/i];
for (const scope of scopes) {
  const buttons = Array.from(scope.querySelectorAll('button, input[type=submit], tp-yt-paper-button, a[role="button"]'))
                       .filter(isVisible);
  for (const pattern of patterns) {
    const button = buttons.find(el => pattern.test((el.innerText || el.value || '').trim()));
    if (button) { button.click(); return (button.innerText || button.value || '').trim(); }
  }
  // Same buttons identified by their accessibility label
  // ("Reject the use of cookies and other data for the purposes described").
  const byLabel = buttons.find(el => /^reject the use of cookies/i.test(el.getAttribute('aria-label') || ''))
               || buttons.find(el => /^accept the use of cookies/i.test(el.getAttribute('aria-label') || ''));
  if (byLabel) { byLabel.click(); return byLabel.getAttribute('aria-label').split(' ').slice(0, 2).join(' '); }
}
return null;
"""


def dismiss_consent(driver, report=print):
    """Answer a cookie-consent page or dialog if (and only if) one is shown.
    Returns True when something was clicked."""
    clicked_label = driver.execute_script(CONSENT_CLICK_SCRIPT)
    if clicked_label:
        report(f"cookie consent shown - clicked '{clicked_label}'")
        return True
    return False


# Start (or restart) playback, muted. YouTube's own player API is used first:
# calling only video.play() can be overridden by the player, which then
# leaves the video sitting at 0:00 (seen on the first test run).
START_PLAYBACK_SCRIPT = r"""
const mute = arguments[0];
const player = document.getElementById('movie_player');
const video = document.querySelector('#movie_player video') || document.querySelector('#shorts-player video')
              || document.querySelector('video.html5-main-video') || document.querySelector('video');
if (player) {
  try { if (mute && player.mute) player.mute(); } catch (e) {}
  try { if (player.playVideo) player.playVideo(); } catch (e) {}
}
if (video) {
  if (mute) video.muted = true;
  // The playback speed is not touched here: it is set (and kept) by the
  // speed handling in play_video_to_end, as a viewer's choice would be.
  const playPromise = video.play();
  if (playPromise && playPromise.catch) playPromise.catch(() => {});
}
// Switch off "Autoplay next video" so the trace contains only this video.
const autonav = document.querySelector('.ytp-autonav-toggle-button[aria-checked="true"]');
if (autonav) autonav.click();
return !!video;
"""

# Resolution names accepted in config.VIDEO_QUALITY -> YouTube player codes.
RESOLUTION_CODES = {"144p": "tiny", "240p": "small", "360p": "medium", "480p": "large", "720p": "hd720",
                    "1080p": "hd1080", "1440p": "hd1440", "2160p": "hd2160"}
CODE_HEIGHTS = {code: int(name[:-1]) for name, code in RESOLUTION_CODES.items()}
# Seconds of (non-advert) playback after which the requested resolution
# should be in effect; the share of playback at it is measured from then.
QUALITY_SETTLE_SECONDS = 10


def normalize_quality(value):
    """'720p', '720', 720 or 'hd720' -> 'hd720'; None / 'auto' -> None."""
    if value is None or str(value).strip().lower() in ("", "auto", "none"):
        return None
    text = str(value).strip().lower()
    if text in CODE_HEIGHTS:
        return text
    if not text.endswith("p"):
        text += "p"
    if text in RESOLUTION_CODES:
        return RESOLUTION_CODES[text]
    raise ValueError(f'unknown video resolution "{value}" - use one of: auto, '
                     + ", ".join(RESOLUTION_CODES))


def configured_qualities():
    """config.VIDEO_QUALITY as a list of player codes ([None] = Auto)."""
    setting = config.VIDEO_QUALITY
    values = setting if isinstance(setting, (list, tuple)) else [setting]
    qualities = [normalize_quality(value) for value in values]
    return qualities or [None]


def resolution_label(code):
    return f"{CODE_HEIGHTS[code]}p" if code in CODE_HEIGHTS else "auto"


# Playback speeds YouTube's own speed menu offers.
ALLOWED_SPEEDS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)


def normalize_speed(value):
    """1.5, '1.5', '1.5x' -> 1.5; None / 'normal' -> 1.0."""
    if value is None or str(value).strip().lower() in ("", "normal", "none"):
        return 1.0
    text = str(value).strip().lower().rstrip("x")
    try:
        speed = float(text)
    except ValueError:
        speed = -1.0
    if speed not in ALLOWED_SPEEDS:
        raise ValueError(f'unsupported playback speed "{value}" - use one of: '
                         + ", ".join(f"{allowed:g}" for allowed in ALLOWED_SPEEDS))
    return speed


def configured_speeds():
    setting = config.PLAYBACK_SPEED
    values = setting if isinstance(setting, (list, tuple)) else [setting]
    return [normalize_speed(value) for value in values] or [1.0]


# Sets the speed the way the player's own speed menu does (player API) and
# on the <video> element; returns the speed now in effect.
SET_SPEED_SCRIPT = r"""
const rate = arguments[0];
const player = document.getElementById('movie_player');
const video = document.querySelector('#movie_player video') || document.querySelector('video');
try { if (player && player.setPlaybackRate) player.setPlaybackRate(rate); } catch (e) {}
if (video && Math.abs(video.playbackRate - rate) > 0.001) video.playbackRate = rate;
return video ? video.playbackRate : null;
"""


# Playlist sessions (several videos in one browser): a playlist moves on to
# the next video by itself the moment one ends, which would put the start
# of the next video into this video's capture. This holds the armed video a
# fraction of a second before its end (everything is downloaded by then),
# so the capture can be closed cleanly before the next video is chosen.
# Adverts and other videos are never held.
HOLD_AT_END_SCRIPT = r"""
const video = document.querySelector('#movie_player video');
window.__wfpHoldId = arguments[0];
if (!video) return false;
if (!video.__wfpHold) {
  video.__wfpHold = true;
  video.addEventListener('timeupdate', () => {
    const player = document.getElementById('movie_player');
    if (!window.__wfpHoldId) return;
    if (player && (player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting'))) return;
    if (new URLSearchParams(location.search).get('v') !== window.__wfpHoldId) return;
    const end = video.duration;
    if (!isFinite(end) || end <= 0) return;
    if (video.currentTime >= end - Math.min(0.9, 0.35 * video.playbackRate + 0.2)) video.pause();
  });
}
return true;
"""

# Stops the player without leaving the page (next video of a session).
PAUSE_PLAYER_SCRIPT = r"""
window.__wfpHoldId = null;
const player = document.getElementById('movie_player');
try { if (player && player.pauseVideo) player.pauseVideo(); } catch (e) {}
const video = document.querySelector('#movie_player video');
if (video && !video.paused) video.pause();
return true;
"""


# Stored preference the YouTube player reads when a video starts (the same
# entry the player itself writes when a viewer picks a resolution). Set on
# the entry page in browsing mode, so even the first seconds of the video
# are fetched at the requested resolution.
QUALITY_PREFERENCE_SCRIPT = r"""
const height = arguments[0], now = Date.now();
try {
  localStorage.setItem('yt-player-quality', JSON.stringify({
    data: JSON.stringify({quality: height, previousQuality: height}),
    expiration: now + 30 * 24 * 3600 * 1000, creation: now}));
  return true;
} catch (e) { return false; }
"""

SET_QUALITY_SCRIPT = r"""
const player = document.getElementById('movie_player');
if (player && player.setPlaybackQualityRange) { player.setPlaybackQualityRange(arguments[0], arguments[0]); return true; }
return false;
"""

# Advert handling (seen 15 Nov 2026: long adverts played to the end and
# "corrupted" the capture - no viewer watches a skippable advert to the end).
# YouTube ignores script-generated clicks on its Skip button; only a real
# (trusted) mouse click counts - the reason browser auto-skip extensions
# stopped working. The Skip button is therefore clicked through WebDriver,
# which produces a genuine mouse click, after a short human reaction time.
SKIP_BUTTON_SELECTORS = (".ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, "
                         ".ytp-ad-skip-button-container button, button[id^='skip-button']")
# Seconds between checks while an advert is showing (fast, so Skip is seen
# as soon as it becomes clickable).
AD_POLL_SECONDS = 0.25
# An advert break longer than this is given up on (stuck player).
MAX_AD_BREAK_SECONDS = 600

AD_STATE_SCRIPT = r"""
const player = document.getElementById('movie_player');
const showing = !!(player && (player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting')));
const video = document.querySelector('#movie_player video') || document.querySelector('video');
return {showing: showing, src: video ? (video.currentSrc || video.src || '') : '',
        time: video ? video.currentTime : 0};
"""

# "Video paused. Continue watching?" dialog shown during long sessions.
CONTINUE_WATCHING_SCRIPT = r"""
const confirm = document.querySelector('yt-confirm-dialog-renderer #confirm-button button, yt-confirm-dialog-renderer #confirm-button');
if (confirm && confirm.offsetParent !== null) { confirm.click(); return true; }
return false;
"""


@dataclass
class PlaybackResult:
    completed: bool = False
    reason: str = ""
    video_title: str = ""
    video_duration_seconds: float = 0.0
    played_until_seconds: float = 0.0
    wall_seconds: float = 0.0
    ads_seen: bool = False
    ad_breaks: int = 0                # advert breaks (one break may hold several adverts)
    ads_count: int = 0                # adverts played
    ads_skipped: int = 0              # adverts skipped with the Skip button
    ad_seconds: float = 0.0           # time spent in advert breaks
    rebuffer_events: int = 0
    resumes: int = 0
    quality: str = ""                 # resolution actually played (most of the time)
    quality_requested: str = "auto"
    quality_share: float = 0.0        # share of playback at the requested resolution
    speed_requested: float = 1.0
    speed: float = 1.0                # speed actually in effect most of the time after the change
    speed_changed_at_seconds: float = 0.0   # position in the video when the speed was changed


def extract_video_id(video_url):
    """Return the YouTube id from watch / youtu.be / shorts / embed URLs."""
    parsed_url = urlparse(video_url)
    if parsed_url.hostname and parsed_url.hostname.endswith("youtu.be"):
        return parsed_url.path.strip("/").split("/")[0] or None
    if "v" in parse_qs(parsed_url.query):
        return parse_qs(parsed_url.query)["v"][0]
    shorts_or_embed = re.match(r"^/(?:shorts|embed|live)/([^/?#]+)", parsed_url.path)
    return shorts_or_embed.group(1) if shorts_or_embed else None


def url_starting_at(video_url, start_seconds):
    """Same video URL with YouTube's t= start offset (used to resume)."""
    parsed_url = urlparse(video_url)
    query = parse_qs(parsed_url.query)
    query["t"] = [f"{int(start_seconds)}s"]
    return urlunparse(parsed_url._replace(query=urlencode(query, doseq=True)))


def format_clock(seconds):
    seconds = int(seconds or 0)
    if seconds >= 3600:
        return f"{seconds // 3600:d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _blocked_reason(player_state):
    if player_state["error_text"]:
        return f"player error: {' '.join(player_state['error_text'].split())}"
    if "google.com/sorry" in player_state["url"]:
        return "blocked: Google 'unusual traffic' page"
    player_text_lower = (player_state["player_text"] or "").lower()
    for phrase in BLOCKED_PLAYBACK_PHRASES:
        if phrase in player_text_lower:
            return f"blocked: '{phrase}'"
    if player_state["url"].startswith(("about:torconnect", "about:neterror")):
        return f"browser not connected through tor ({player_state['url'][:40]})"
    return None


def _is_resumable(reason):
    return any(phrase in reason.lower() for phrase in RESUMABLE_ERROR_PHRASES)


def _open_page_and_wait_for_player(driver, page_url, report, abort_check, expected_video_id=None):
    """Load page_url (None = the video page is already open, reached by a
    click in browsing mode), handle consent screens, wait for the <video>
    element. Returns (player_state, None) or (None, failure reason)."""
    try:
        if page_url is not None:
            driver.get(page_url)
    except TimeoutException:
        # YouTube keeps long-lived requests open; a missed "load" event does
        # not mean the player is unusable, so carry on and check the player.
        report(f"page load event not reached in {config.PAGE_LOAD_TIMEOUT}s - checking player anyway")
    deadline = time.monotonic() + config.PLAYER_READY_TIMEOUT
    while time.monotonic() < deadline:
        abort_reason = abort_check(0)
        if abort_reason:
            return None, abort_reason
        # A consent dialog can cover an already loaded video page, so it is
        # checked every time, not only while no video is found.
        if dismiss_consent(driver, report):
            time.sleep(3)
            continue
        player_state = driver.execute_script(PLAYER_STATE_SCRIPT)
        blocked_reason = _blocked_reason(player_state)
        if blocked_reason:
            return None, blocked_reason
        if player_state["has_video"]:
            # After an in-page click (browsing, next video of a session) the
            # player briefly still holds the previous video: wait until it
            # reports the clicked one and has started it from the beginning.
            switching = page_url is None and expected_video_id and (
                (player_state["player_video_id"] and player_state["player_video_id"] != expected_video_id)
                or (not player_state["ad_showing"] and (player_state["current_time"] or 0) > 10
                    and time.monotonic() < deadline - config.PLAYER_READY_TIMEOUT / 2))
            if not switching:
                driver.execute_script(START_PLAYBACK_SCRIPT, config.MUTE_AUDIO)
                return player_state, None
        time.sleep(1)
    return None, f"player did not appear within {config.PLAYER_READY_TIMEOUT}s"


def _find_clickable_skip_button(driver):
    for button in driver.find_elements(By.CSS_SELECTOR, SKIP_BUTTON_SELECTORS):
        try:
            if button.is_displayed() and button.is_enabled():
                return button
        except StaleElementReferenceException:
            continue
    return None


def _click_like_a_viewer(driver, button):
    """A genuine mouse click on the button (WebDriver click), with fallbacks
    for a button partly covered by the advert overlay."""
    try:
        button.click()
        return "real mouse click"
    except (ElementClickInterceptedException, ElementNotInteractableException):
        pass
    try:
        ActionChains(driver).move_to_element(button).pause(random.uniform(0.05, 0.2)).click().perform()
        return "mouse moved and clicked"
    except WebDriverException:
        driver.execute_script("arguments[0].click();", button)
        return "script click (may be ignored)"


def _handle_ad_break(driver, playback_result, report, abort_check, playing_seconds):
    """Stay with the advert break until the main video is back: click Skip
    (after a human reaction time) as soon as it becomes clickable; watch
    unskippable adverts through, as a viewer must."""
    break_started = time.monotonic()
    playback_result.ad_breaks += 1
    playback_result.ads_seen = True
    current_ad_source, skip_seen_at = None, None
    while True:
        if abort_check(playing_seconds):
            return
        try:
            ad_state = driver.execute_script(AD_STATE_SCRIPT)
        except WebDriverException:
            return
        if not ad_state["showing"]:
            break
        if ad_state["src"] != current_ad_source:
            # A new advert of the break ("Ad 1 of 2", "Ad 2 of 2" ...).
            current_ad_source, skip_seen_at = ad_state["src"], None
            playback_result.ads_count += 1
            report(f"advert {playback_result.ads_count} playing - Skip will be clicked as soon as it is offered")
        skip_button = _find_clickable_skip_button(driver)
        if skip_button is not None:
            if skip_seen_at is None:
                # Human reaction time between Skip appearing and the click.
                skip_seen_at = time.monotonic()
                reaction_delay = random.uniform(*config.AD_SKIP_REACTION_SECONDS)
            if time.monotonic() - skip_seen_at >= reaction_delay:
                try:
                    how = _click_like_a_viewer(driver, skip_button)
                    playback_result.ads_skipped += 1
                    report(f"advert skipped after {time.monotonic() - break_started:.1f}s ({how})")
                    skip_seen_at = None
                    time.sleep(0.5)
                except (StaleElementReferenceException, WebDriverException) as skip_error:
                    report(f"skip click failed ({type(skip_error).__name__}) - trying again")
        if time.monotonic() - break_started > MAX_AD_BREAK_SECONDS:
            report(f"advert break longer than {MAX_AD_BREAK_SECONDS}s - continuing")
            break
        time.sleep(AD_POLL_SECONDS)
    playback_result.ad_seconds = round(playback_result.ad_seconds + time.monotonic() - break_started, 1)


def play_video_to_end(driver, video_url, report=print, abort_check=lambda playback_seconds: None,
                      already_open=False, quality=None, speed=1.0, hold_at_end=False):
    """Load the video (or, with already_open=True, use the video page the
    browsing step has just clicked through to) and block until it has played
    completely (or failed).

    report(message)            : progress output (prefixed per slot by caller)
    abort_check(play_seconds)  : returns a reason string to stop early (user
                                 pressed Ctrl+C, capture records nothing ...)
    hold_at_end                : playlist session - hold the video just before
                                 its end so the playlist does not move on
                                 (HOLD_AT_END_SCRIPT)
    """
    playback_result = PlaybackResult()
    started_at = time.monotonic()
    expected_video_id = extract_video_id(video_url)
    driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)

    player_state, failure_reason = _open_page_and_wait_for_player(
        driver, None if already_open else video_url, report, abort_check, expected_video_id)
    if hold_at_end and player_state is not None:
        driver.execute_script(HOLD_AT_END_SCRIPT, expected_video_id)
    if player_state is None:
        playback_result.reason = failure_reason
        playback_result.wall_seconds = round(time.monotonic() - started_at, 1)
        return playback_result
    if player_state["page_is_live"]:
        playback_result.reason = "live stream - has no end to play to"
        return playback_result

    playback_result.video_title = player_state["page_title"] or ""
    page_length_seconds = player_state["page_length_seconds"] or 0
    report(f"video found: '{playback_result.video_title[:50]}' ({format_clock(page_length_seconds)})")
    playback_result.quality_requested = resolution_label(quality)
    if quality:
        # Lock the resolution at once, before the first video segments.
        driver.execute_script(SET_QUALITY_SCRIPT, quality)
    quality_polls = Counter()          # non-advert state checks per resolution seen
    last_quality_push = 0.0
    # Speed: like a viewer who opens the speed menu a little after the video
    # starts - normal speed until a random point, then the chosen speed.
    speed = speed or 1.0
    playback_result.speed_requested = speed
    speed_change_at = random.uniform(*config.SPEED_CHANGE_AFTER_SECONDS) if speed != 1.0 else 0.0
    speed_changed = speed == 1.0
    speed_polls = Counter()            # non-advert state checks per speed seen (after the change)
    last_speed_push = 0.0
    main_video_duration = 0.0
    furthest_position = 0.0
    last_position = -1.0
    last_progress_at = time.monotonic()
    last_progress_report_at = 0.0
    buffering = False
    near_end_since = None
    playing_seconds = 0.0

    while True:
        time.sleep(config.POLL_INTERVAL_SECONDS)
        now = time.monotonic()
        try:
            player_state = driver.execute_script(PLAYER_STATE_SCRIPT)
        except WebDriverException as script_error:
            playback_result.reason = f"browser stopped responding: {script_error.msg}"
            break

        abort_reason = abort_check(playing_seconds)
        if abort_reason:
            playback_result.reason = abort_reason
            break

        # The consent dialog may appear in the middle of playback and pause
        # the video: answer it, restart playback, and do not count the pause
        # as a stall.
        if dismiss_consent(driver, report):
            time.sleep(2)
            driver.execute_script(START_PLAYBACK_SCRIPT, config.MUTE_AUDIO)
            last_progress_at = time.monotonic()
            continue

        blocked_reason = _blocked_reason(player_state)
        if blocked_reason:
            can_resume = (config.ON_PLAYER_ERROR == "resume" and furthest_position > 0
                          and _is_resumable(blocked_reason)
                          and playback_result.resumes < config.MAX_RESUMES_PER_PLAYBACK)
            if not can_resume:
                playback_result.reason = blocked_reason
                break
            playback_result.resumes += 1
            resume_at = max(0, int(furthest_position) - 1)
            report(f"YouTube error at {format_clock(furthest_position)} ({blocked_reason}) - "
                   f"reloading at {format_clock(resume_at)} "
                   f"[resume {playback_result.resumes}/{config.MAX_RESUMES_PER_PLAYBACK}]")
            player_state, failure_reason = _open_page_and_wait_for_player(
                driver, url_starting_at(video_url, resume_at), report, abort_check)
            if player_state is None:
                playback_result.reason = f"resume failed: {failure_reason}"
                break
            last_position = -1.0
            last_progress_at = time.monotonic()
            continue

        current_video_id = extract_video_id(player_state["url"])
        if expected_video_id and current_video_id and current_video_id != expected_video_id:
            # Inside a playlist the player moves on to the next video by
            # itself when one ends; if that happened right at the end, the
            # video WAS played completely.
            # Margin: 3 % of the video, or two state checks + 1 s for short
            # videos (the last check can come up to one interval before the
            # end). YouTube only moves on once a video has ended.
            known_duration = main_video_duration or page_length_seconds
            end_margin = max(known_duration * (1 - LOOP_COMPLETION_FRACTION), 2 * config.POLL_INTERVAL_SECONDS + 1)
            if known_duration and furthest_position >= known_duration - end_margin:
                playback_result.completed = True
                playback_result.reason = "played to end (playlist moved to next video)"
                furthest_position = known_duration
                break
            playback_result.reason = f"page navigated to another video ({current_video_id})"
            break

        if player_state["ad_showing"]:
            # Adverts use the same <video> element; their time and duration
            # must not be mistaken for the main video's. The whole advert
            # break is handled here (skip as soon as a viewer could).
            _handle_ad_break(driver, playback_result, report, abort_check, playing_seconds)
            last_progress_at = time.monotonic()
            continue

        # Resolution: re-applied (at most every 2 s) until the player reports
        # it - e.g. after a resume or when the player overrides it at start.
        if player_state["quality"]:
            if playing_seconds >= QUALITY_SETTLE_SECONDS:
                quality_polls[player_state["quality"]] += 1
        if quality and player_state["quality"] != quality and now - last_quality_push >= 2:
            driver.execute_script(SET_QUALITY_SCRIPT, quality)
            last_quality_push = now

        # Speed: changed once the random moment is reached, then kept - the
        # player resets it e.g. after an advert, so it is re-applied (at most
        # every 2 s) whenever it differs.
        current_rate = player_state["playback_rate"] or 1.0
        if not speed_changed and (player_state["current_time"] or 0) >= speed_change_at:
            driver.execute_script(SET_SPEED_SCRIPT, speed)
            speed_changed = True
            last_speed_push = now
            playback_result.speed_changed_at_seconds = round(player_state["current_time"] or 0, 1)
            report(f"playback speed changed to {speed:g}x at {format_clock(player_state['current_time'])}")
        elif speed_changed and abs(current_rate - speed) > 0.001 and now - last_speed_push >= 2:
            driver.execute_script(SET_SPEED_SCRIPT, speed)
            last_speed_push = now
        if speed_changed:
            speed_polls[round(current_rate, 2)] += 1
        driver.execute_script(CONTINUE_WATCHING_SCRIPT)

        if player_state["element_duration"]:
            main_video_duration = player_state["element_duration"]
        duration = main_video_duration or page_length_seconds
        position = player_state["current_time"] or 0.0

        if position > last_position + 0.05:
            if last_position >= 0:
                playing_seconds += position - last_position if position - last_position < 5 else 0
            last_progress_at = now
            buffering = False
        elif not buffering and not player_state["paused"]:
            buffering = True
            playback_result.rebuffer_events += 1
        looped_back = (duration > 0 and furthest_position >= duration * LOOP_COMPLETION_FRACTION
                       and position < furthest_position - 2)
        last_position = position
        furthest_position = max(furthest_position, position)

        # Completion: the player's own "ended" flag is the primary signal;
        # "within END_TOLERANCE of the end" counts only after END_GRACE_SECONDS.
        near_end = duration > 0 and position >= duration - config.END_TOLERANCE_SECONDS
        if near_end and near_end_since is None:
            near_end_since = now
        if player_state["ended"] or looped_back or \
                (near_end and now - near_end_since >= END_GRACE_SECONDS):
            playback_result.completed = True
            playback_result.reason = "played to end"
            furthest_position = max(furthest_position, duration if player_state["ended"] else position)
            break
        if near_end:
            continue  # do not "resume" a video that has just finished

        if player_state["paused"] or (config.MUTE_AUDIO and player_state["muted"] is False):
            driver.execute_script(START_PLAYBACK_SCRIPT, config.MUTE_AUDIO)

        if now - last_progress_at > config.STALL_TIMEOUT:
            playback_result.reason = f"stalled: no progress for {config.STALL_TIMEOUT}s at {format_clock(position)}"
            break
        # A slower speed takes longer in real time; the limit scales with it.
        allowed_wall_seconds = ((duration or 600) / min(speed, 1.0) * config.MAX_PLAYBACK_FACTOR
                                + config.PLAYER_READY_TIMEOUT)
        if now - started_at > allowed_wall_seconds:
            playback_result.reason = f"too slow: exceeded {allowed_wall_seconds:.0f}s wall-clock limit"
            break

        if now - last_progress_report_at >= config.PROGRESS_PRINT_INTERVAL_SECONDS:
            last_progress_report_at = now
            percent_done = 100 * position / duration if duration else 0
            report(f"playing {format_clock(position)} / {format_clock(duration)} ({percent_done:4.0f}%)"
                   f"  quality={player_state['quality']}  muted={player_state['muted']}")

    playback_result.video_duration_seconds = round(main_video_duration or page_length_seconds, 2)
    playback_result.played_until_seconds = round(furthest_position, 2)
    if speed_polls:
        playback_result.speed = speed_polls.most_common(1)[0][0]
    if quality_polls:
        # Resolution actually played: the one seen for most of the playback.
        actual_code, _count = quality_polls.most_common(1)[0]
        playback_result.quality = resolution_label(actual_code) if actual_code in CODE_HEIGHTS else actual_code
        if quality:
            playback_result.quality_share = round(quality_polls[quality] / sum(quality_polls.values()), 2)
    elif isinstance(player_state, dict) and player_state.get("quality"):
        # Very short video (under QUALITY_SETTLE_SECONDS): the last reading.
        code = player_state["quality"]
        playback_result.quality = resolution_label(code) if code in CODE_HEIGHTS else code
        if quality:
            playback_result.quality_share = 1.0 if code == quality else 0.0
    if (playback_result.completed and quality and config.QUALITY_MUST_MATCH
            and playback_result.quality_share < 0.9):
        playback_result.completed = False
        playback_result.reason = (f"requested resolution {resolution_label(quality)} not played "
                                  f"(played {playback_result.quality}, {playback_result.quality_share:.0%} "
                                  "at the requested one) - not available for this video?")
    playback_result.wall_seconds = round(time.monotonic() - started_at, 1)
    return playback_result
