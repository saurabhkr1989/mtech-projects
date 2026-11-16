"""
File: twitter.py
Purpose:
    Opens one X/Twitter post in an already-launched browser and returns when
    the post has been fully consumed:
      - post WITH video (and PLAY_VIDEO_TO_END): the video plays muted until
        the player reports it has ended (or looped back after >= 97 %, as
        GIF-style videos loop forever);
      - post WITHOUT video: page complete, the post and all its images
        loaded, and NETWORK_IDLE_SECONDS without a new network request.
    Login walls, "Something went wrong", deleted/protected posts or a stalled
    video end the attempt with the reason; the caller retries.

X shows single posts to logged-out visitors. Cookie banners are answered
("Refuse non-essential" first) and sign-up pop-ups are closed, so nothing
blocks the post.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import re
import time
from dataclasses import dataclass

from selenium.common.exceptions import TimeoutException, WebDriverException

import config

# Text X shows instead of the post. Matched case-insensitively.
BLOCKED_PAGE_PHRASES = [
    "something went wrong",           # "...Try reloading." and "...but don't fret"
    "javascript is not available",
    "this page doesn’t exist", "this page doesn't exist",
    "this post is unavailable", "this post was deleted",
    "these posts are protected", "this post is from an account that no longer exists",
    "account suspended", "rate limit exceeded",
    "age-restricted",
]
LOOP_COMPLETION_FRACTION = 0.97
END_GRACE_SECONDS = 3

# Finds the post on the page (arguments[0] = post id). Seen on 12 Nov 2026:
# X showed the post fully, but without the 'article[data-testid="tweet"]'
# markup the first version looked for. Detection now tries, in order:
#   1. the classic tweet article (focal one has tabindex="-1");
#   2. the post's own timestamp, which links to /status/<post id>;
#   3. the page title "<name> on X: ..." with the main column present.
# The container returned is the article if there is one, else X's main
# (primary) column - images and video are looked for inside it.
FIND_POST_JS = r"""
function findPost(postId) {
  const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
  const focal = articles.find(a => a.getAttribute('tabindex') === '-1') || articles[0];
  if (focal) return focal;
  const column = document.querySelector('[data-testid="primaryColumn"]') || document.querySelector('main');
  const stamp = postId ? document.querySelector('a[href*="/status/' + postId + '"] time') : null;
  if (stamp) return stamp.closest('article') || stamp.closest('[data-testid="cellInnerDiv"]') || column || document.body;
  if (column && / on X: /.test(document.title)) return column;
  return null;
}
"""

POST_STATE_SCRIPT = FIND_POST_JS + r"""
const article = findPost(arguments[0]);
const video = article ? article.querySelector('video') : null;
const playerBox = article ? article.querySelector('[data-testid="videoPlayer"], [data-testid="videoComponent"]') : null;
const images = article ? Array.from(article.querySelectorAll('img')) : [];
try { if (!window.__wfpBufferSet) { performance.setResourceTimingBufferSize(20000); window.__wfpBufferSet = true; } } catch (e) {}
const resources = performance.getEntriesByType('resource');
let lastActivity = 0;
for (const r of resources) { lastActivity = Math.max(lastActivity, r.responseEnd || r.startTime); }
return {
  url: location.href,
  ready_state: document.readyState,
  has_post: !!article,
  has_video: !!video,
  has_player_box: !!playerBox,
  current_time: video ? video.currentTime : null,
  duration: (video && isFinite(video.duration)) ? video.duration : null,
  ended: video ? video.ended : false,
  paused: video ? video.paused : true,
  muted: video ? video.muted : null,
  loop: video ? video.loop : false,
  images_total: images.length,
  images_loaded: images.filter(i => i.complete && i.naturalWidth > 0).length,
  resource_count: resources.length,
  ms_since_last_request: performance.now() - lastActivity,
  page_text: document.body ? document.body.innerText.slice(0, 3000) : '',
  title: document.title
};
"""

# Cookie banner ("Refuse non-essential cookies" first), sign-up / log-in
# pop-ups ("Close" / "Not now"), sensitive-content warning ("Show").
DISMISS_OVERLAYS_SCRIPT = FIND_POST_JS + r"""
const clicked = [];
const buttons = Array.from(document.querySelectorAll('button, div[role="button"], a[role="button"], span'));
const clickFirst = (patterns) => {
  for (const pattern of patterns) {
    const el = buttons.find(b => pattern.test((b.innerText || b.getAttribute('aria-label') || '').trim()));
    if (el) { el.click(); clicked.push((el.innerText || el.getAttribute('aria-label') || '').trim()); return true; }
  }
  return false;
};
clickFirst([/^refuse non-essential cookies$/i, /^accept all cookies$/i]);
const close = document.querySelector('[data-testid="app-bar-close"], [data-testid="xMigrationBottomBar"] [role="button"], div[role="dialog"] [aria-label="Close"]');
if (close) { close.click(); clicked.push('close dialog'); }
clickFirst([/^not now$/i]);
const article = findPost(arguments[0]);
if (article) {
  const show = Array.from(article.querySelectorAll('button, div[role="button"]')).find(b => /^(show|view)$/i.test((b.innerText || '').trim()));
  if (show) { show.click(); clicked.push('show sensitive content'); }
}
return clicked;
"""

START_VIDEO_SCRIPT = FIND_POST_JS + r"""
const mute = arguments[1];
const article = findPost(arguments[0]);
if (!article) return 'no-post';
const video = article.querySelector('video');
if (!video) {
  const box = article.querySelector('[data-testid="videoPlayer"], [data-testid="videoComponent"], [data-testid="playButton"]');
  if (box) { box.click(); return 'clicked-player'; }
  return 'no-video';
}
if (mute) video.muted = true;
video.playbackRate = 1.0;
const playPromise = video.play();
if (playPromise && playPromise.catch) playPromise.catch(() => {});
return 'playing';
"""


@dataclass
class PostResult:
    completed: bool = False
    reason: str = ""
    page_title: str = ""
    has_video: bool = False
    video_duration_seconds: float = 0.0
    played_until_seconds: float = 0.0
    load_seconds: float = 0.0
    wall_seconds: float = 0.0
    rebuffer_events: int = 0


def extract_post_id(post_url):
    match = re.search(r"/status(?:es)?/(\d+)", post_url)
    return match.group(1) if match else None


def _format_clock(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _blocked_reason(post_state):
    if "/i/flow/login" in post_state["url"] or "/login" in post_state["url"]:
        return "redirected to login wall"
    page_text_lower = (post_state["page_text"] or "").lower()
    for phrase in BLOCKED_PAGE_PHRASES:
        if phrase in page_text_lower:
            return f"blocked: '{phrase}'"
    return None


def load_post(driver, post_url, report=print, abort_check=lambda seconds_on_page: None, reload=False,
              already_open=False):
    """Open the post (reload=False), refresh the page already showing it
    (reload=True, like pressing F5: the browser cache is used), or - with
    already_open=True - use the post the browsing step has just clicked
    through to; then block until it is fully loaded / its video has played
    to the end, or failed."""
    result = PostResult()
    started_at = time.monotonic()
    post_id = extract_post_id(post_url)
    driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
    try:
        if already_open:
            pass  # reached by a click in browsing mode: nothing to load
        elif reload:
            driver.refresh()
        else:
            driver.get(post_url)
    except TimeoutException:
        report(f"page load event not reached in {config.PAGE_LOAD_TIMEOUT}s - checking the post anyway")

    # ---- wait for the post itself
    post_state = None
    deadline = started_at + config.POST_READY_TIMEOUT
    while time.monotonic() < deadline:
        abort_reason = abort_check(time.monotonic() - started_at)
        if abort_reason:
            result.reason = abort_reason
            return _finish(result, started_at)
        driver.execute_script(DISMISS_OVERLAYS_SCRIPT, post_id)
        post_state = driver.execute_script(POST_STATE_SCRIPT, post_id)
        blocked_reason = _blocked_reason(post_state)
        if blocked_reason:
            result.reason = blocked_reason
            return _finish(result, started_at)
        if post_state["has_post"]:
            break
        time.sleep(1)
    else:
        result.reason = f"post did not appear within {config.POST_READY_TIMEOUT}s"
        return _finish(result, started_at)
    result.page_title = (post_state["title"] or "")[:120]

    # ---- does it have a video? (the player may appear a moment later)
    video_deadline = time.monotonic() + config.VIDEO_APPEAR_GRACE_SECONDS
    while not post_state["has_video"] and time.monotonic() < video_deadline:
        if post_state["has_player_box"]:
            driver.execute_script(START_VIDEO_SCRIPT, post_id, config.MUTE_AUDIO)
        time.sleep(1)
        post_state = driver.execute_script(POST_STATE_SCRIPT, post_id)
    result.has_video = post_state["has_video"]

    if result.has_video and config.PLAY_VIDEO_TO_END:
        report("post has a video - playing it to the end (muted)")
        _play_video_to_end(driver, post_id, result, started_at, report, abort_check)
    else:
        report("post without video - waiting until the page is fully loaded")
        _wait_until_fully_loaded(driver, post_id, result, started_at, report, abort_check)
    return _finish(result, started_at)


def _wait_until_fully_loaded(driver, post_id, result, started_at, report, abort_check):
    while True:
        time.sleep(config.POLL_INTERVAL_SECONDS)
        elapsed = time.monotonic() - started_at
        abort_reason = abort_check(elapsed)
        if abort_reason:
            result.reason = abort_reason
            return
        driver.execute_script(DISMISS_OVERLAYS_SCRIPT, post_id)
        post_state = driver.execute_script(POST_STATE_SCRIPT, post_id)
        blocked_reason = _blocked_reason(post_state)
        if blocked_reason:
            result.reason = blocked_reason
            return
        content_complete = (post_state["ready_state"] == "complete" and post_state["has_post"]
                            and post_state["images_loaded"] >= post_state["images_total"])
        if content_complete and post_state["ms_since_last_request"] >= config.NETWORK_IDLE_SECONDS * 1000:
            result.completed = True
            result.reason = "fully loaded (network idle)"
            result.load_seconds = round(elapsed, 1)
            return
        if elapsed >= config.MAX_PAGE_LOAD_SECONDS:
            if content_complete:
                result.completed = True
                result.reason = "fully loaded (page kept polling in background)"
                result.load_seconds = round(elapsed, 1)
            else:
                result.reason = (f"not fully loaded after {config.MAX_PAGE_LOAD_SECONDS}s "
                                 f"(images {post_state['images_loaded']}/{post_state['images_total']})")
            return


def _play_video_to_end(driver, post_id, result, started_at, report, abort_check):
    driver.execute_script(START_VIDEO_SCRIPT, post_id, config.MUTE_AUDIO)
    furthest_position, last_position = 0.0, -1.0
    last_progress_at = time.monotonic()
    last_report_at = 0.0
    near_end_since = None
    buffering = False
    duration = 0.0
    while True:
        time.sleep(config.POLL_INTERVAL_SECONDS)
        now = time.monotonic()
        try:
            post_state = driver.execute_script(POST_STATE_SCRIPT, post_id)
        except WebDriverException as script_error:
            result.reason = f"browser stopped responding: {script_error.msg}"
            return
        abort_reason = abort_check(now - started_at)
        if abort_reason:
            result.reason = abort_reason
            return
        blocked_reason = _blocked_reason(post_state)
        if blocked_reason:
            result.reason = blocked_reason
            return
        if not post_state["has_video"]:
            result.reason = "video disappeared from the post"
            return
        duration = post_state["duration"] or duration
        position = post_state["current_time"] or 0.0
        if result.load_seconds == 0 and post_state["ready_state"] == "complete":
            result.load_seconds = round(now - started_at, 1)

        if position > last_position + 0.05:
            last_progress_at, buffering = now, False
        elif not buffering and not post_state["paused"]:
            buffering = True
            result.rebuffer_events += 1
        looped_back = (duration > 0 and furthest_position >= duration * LOOP_COMPLETION_FRACTION
                       and position < furthest_position - 1)
        last_position = position
        furthest_position = max(furthest_position, position)

        near_end = duration > 0 and position >= duration - config.END_TOLERANCE_SECONDS
        if near_end and near_end_since is None:
            near_end_since = now
        if post_state["ended"] or looped_back or (near_end and now - near_end_since >= END_GRACE_SECONDS):
            result.completed = True
            result.reason = "video played to end"
            furthest_position = max(furthest_position, duration if post_state["ended"] else position)
            break
        if near_end:
            continue
        if post_state["paused"] or (config.MUTE_AUDIO and post_state["muted"] is False):
            driver.execute_script(DISMISS_OVERLAYS_SCRIPT, post_id)
            driver.execute_script(START_VIDEO_SCRIPT, post_id, config.MUTE_AUDIO)
        if now - last_progress_at > config.STALL_TIMEOUT:
            result.reason = f"video stalled for {config.STALL_TIMEOUT}s at {_format_clock(position)}"
            break
        allowed_seconds = (duration or 300) * config.MAX_PLAYBACK_FACTOR + config.POST_READY_TIMEOUT
        if now - started_at > allowed_seconds:
            result.reason = f"too slow: exceeded {allowed_seconds:.0f}s"
            break
        if now - last_report_at >= config.PROGRESS_PRINT_INTERVAL_SECONDS:
            last_report_at = now
            report(f"video {_format_clock(position)} / {_format_clock(duration)}  muted={post_state['muted']}")
    result.video_duration_seconds = round(duration, 2)
    result.played_until_seconds = round(furthest_position, 2)


def _finish(result, started_at):
    result.wall_seconds = round(time.monotonic() - started_at, 1)
    return result
