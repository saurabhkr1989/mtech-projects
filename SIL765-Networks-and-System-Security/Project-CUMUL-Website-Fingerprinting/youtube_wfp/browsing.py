"""
File: browsing.py
Purpose:
    Browsing mode (config.NAVIGATION = "browse"): reach the video the way a
    viewer does instead of opening its link directly -

        entry page  ->  stay a random time, scroll  ->  click the thumbnail
        (channel's Videos tab, or the playlist page in playlist mode)

    Why: YouTube is a single-page app. A viewer who clicks a thumbnail does
    NOT reload the site - only the video's data and stream are fetched,
    because the site's scripts and styles were already loaded with the
    channel page. A trace that starts by opening the video link directly
    begins instead with a full site load. Captures made this way therefore
    have the same structure as real viewing: entry page load, a pause,
    then the click and the stream.

    The click time is recorded (epoch seconds, and seconds after the capture
    start), so a trace can be used whole or cut at the click.

    If the video's thumbnail is not found on the entry page, YouTube search
    (the video's title) is tried; as a last resort the link is opened
    directly. The log column "navigation" says which way each capture took.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-14
"""

import json
import os
import random
import time
from dataclasses import dataclass, field
from urllib.parse import quote_plus

from selenium.common.exceptions import (ElementClickInterceptedException, ElementNotInteractableException,
                                        JavascriptException, NoSuchElementException,
                                        StaleElementReferenceException, TimeoutException, WebDriverException)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

import config
import youtube

# Seconds to wait, after a click, for the address bar to show the video.
CLICK_NAVIGATION_TIMEOUT = 20
# Seconds to wait for an entry page to show any video links at all.
ENTRY_PAGE_READY_TIMEOUT = 45

# Links that open the video: thumbnails and titles on channel, playlist and
# search pages. "{id}" is replaced by the video id.
VIDEO_LINK_SELECTORS = (
    'a#video-title-link[href*="v={id}"]', 'a#video-title[href*="v={id}"]',
    'a#thumbnail[href*="v={id}"]', 'a[href*="/watch?v={id}"]', 'a[href*="/shorts/{id}"]',
)

COUNT_VIDEO_LINKS_SCRIPT = r"""
return document.querySelectorAll('a[href*="/watch?v="], a[href*="/shorts/"]').length;
"""

# Fetches the video's title and channel through YouTube's public oEmbed
# endpoint, from inside the (Tor) browser, same-origin, before any capture.
OEMBED_SCRIPT = r"""
const done = arguments[arguments.length - 1];
fetch('/oembed?format=json&url=' + encodeURIComponent(arguments[0]))
  .then(r => r.ok ? r.json() : null).then(j => done(j)).catch(() => done(null));
"""


@dataclass
class NavigationResult:
    opened: bool = False
    navigation: str = ""            # channel | playlist | search | direct | direct-fallback
    entry_url: str = ""
    dwell_seconds: float = 0.0
    click_epoch: float = 0.0
    notes: list = field(default_factory=list)
    failure: str = ""


# --------------------------------------------------------------- video info
def video_info_path():
    return os.path.join(os.path.dirname(config.DATA_RAW_DIR), "video_info.json")


def resolve_video_info(open_browser_for_lookup, video_url, report=print):
    """Title and channel of the single-mode video (cached in data/video_info.json).
    open_browser_for_lookup() returns (web_driver, close_function)."""
    video_id = youtube.extract_video_id(video_url)
    cached = {}
    if os.path.exists(video_info_path()):
        with open(video_info_path(), encoding="utf-8") as info_file:
            cached = json.load(info_file)
    if cached.get("video_id") == video_id and cached.get("channel_url"):
        return cached
    if config.YOUTUBE_CHANNEL_URL:
        info = {"video_id": video_id, "title": cached.get("title", ""), "channel_url": config.YOUTUBE_CHANNEL_URL}
    else:
        web_driver, close_browser = open_browser_for_lookup()
        try:
            web_driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
            web_driver.get("https://www.youtube.com/robots.txt")
            web_driver.set_script_timeout(60)
            oembed = web_driver.execute_async_script(OEMBED_SCRIPT, f"https://www.youtube.com/watch?v={video_id}")
        finally:
            close_browser(web_driver)
        if not oembed or not oembed.get("author_url"):
            raise RuntimeError("could not look up the video's channel - set YOUTUBE_CHANNEL_URL in config.py")
        info = {"video_id": video_id, "title": oembed.get("title", ""), "channel_url": oembed["author_url"]}
    with open(video_info_path(), "w", encoding="utf-8") as info_file:
        json.dump(info, info_file, indent=2)
    report(f"video: '{info['title'][:60]}'  channel: {info['channel_url']}")
    return info


def channel_videos_url(channel_url):
    return channel_url.rstrip("/") + "/videos"


# ------------------------------------------------------------------ helpers
def _random_dwell(web_driver, abort_check, started_at, report=print):
    """Stay on the page a random time, scrolling a little now and then, as
    a person looking at the list would."""
    dwell_seconds = random.uniform(*config.BROWSE_DWELL_SECONDS)
    scroll_count = random.randint(*config.BROWSE_SCROLLS)
    scroll_times = sorted(random.uniform(0, dwell_seconds) for _ in range(scroll_count))
    deadline = time.monotonic() + dwell_seconds
    while time.monotonic() < deadline:
        if abort_check(time.monotonic() - started_at):
            break
        if youtube.dismiss_consent(web_driver, report):   # may appear while looking at the page
            time.sleep(2)
        if scroll_times and time.monotonic() >= deadline - dwell_seconds + scroll_times[0]:
            scroll_times.pop(0)
            web_driver.execute_script("window.scrollBy({top: arguments[0], behavior: 'smooth'});",
                                      random.randint(250, 900))
        time.sleep(0.25)
    return round(dwell_seconds, 1)


def _find_video_link(web_driver, video_id, max_scrolls):
    """The page's link to the video, scrolling further down if needed."""
    for _scroll in range(max_scrolls + 1):
        for selector in VIDEO_LINK_SELECTORS:
            for element in web_driver.find_elements(By.CSS_SELECTOR, selector.format(id=video_id)):
                try:
                    if element.is_displayed() or element.get_attribute("id") in ("thumbnail", "video-title"):
                        return element
                except StaleElementReferenceException:
                    continue
        youtube.dismiss_consent(web_driver)
        web_driver.execute_script("window.scrollBy(0, Math.max(800, window.innerHeight));")
        time.sleep(random.uniform(1.5, 2.5))
    return None


def _click(web_driver, element):
    """Bring the link into view, pause like a person aiming, then click it."""
    web_driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
    time.sleep(random.uniform(0.6, 1.6))
    try:
        element.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        # Something (cookie banner, hover preview) covers the link: a click
        # dispatched on the link itself follows the same in-page route.
        web_driver.execute_script("arguments[0].click();", element)


def _wait_for_video_address(web_driver, video_id):
    deadline = time.monotonic() + CLICK_NAVIGATION_TIMEOUT
    while time.monotonic() < deadline:
        try:
            if youtube.extract_video_id(web_driver.current_url) == video_id:
                return True
        except WebDriverException:
            pass  # page in the middle of changing; try again
        time.sleep(0.3)
    return False


def _open_entry_page(web_driver, entry_url, report, abort_check, started_at):
    try:
        web_driver.get(entry_url)
    except TimeoutException:
        report("entry page load event not reached - continuing with what is shown")
    deadline = time.monotonic() + ENTRY_PAGE_READY_TIMEOUT
    while time.monotonic() < deadline:
        if abort_check(time.monotonic() - started_at):
            return False
        if youtube.dismiss_consent(web_driver, report):
            time.sleep(3)
            continue
        if web_driver.execute_script(COUNT_VIDEO_LINKS_SCRIPT) > 0:
            return True
        time.sleep(1)
    return False


def _try_entry(web_driver, navigation, entry_url, video_id, result, report, abort_check, started_at, max_scrolls,
               quality=None):
    """Entry page -> dwell -> find -> click. True if the video page opened."""
    report(f"browsing: {navigation} page {entry_url}")
    if not _open_entry_page(web_driver, entry_url, report, abort_check, started_at):
        result.notes.append(f"{navigation}: page showed no videos")
        return False
    result.dwell_seconds = _random_dwell(web_driver, abort_check, started_at, report)
    youtube.dismiss_consent(web_driver, report)
    link = _find_video_link(web_driver, video_id, max_scrolls)
    if link is None:
        result.notes.append(f"{navigation}: video not found")
        return False
    if quality:
        # Resolution preference stored before the click, so the player starts
        # the video at it (see youtube.QUALITY_PREFERENCE_SCRIPT).
        web_driver.execute_script(youtube.QUALITY_PREFERENCE_SCRIPT, youtube.CODE_HEIGHTS[quality])
    try:
        result.click_epoch = time.time()
        _click(web_driver, link)
    except (StaleElementReferenceException, NoSuchElementException, JavascriptException) as click_error:
        result.notes.append(f"{navigation}: click failed ({type(click_error).__name__})")
        return False
    if not _wait_for_video_address(web_driver, video_id):
        result.notes.append(f"{navigation}: click did not open the video")
        return False
    result.navigation, result.entry_url, result.opened = navigation, entry_url, True
    report(f"clicked the video after {result.dwell_seconds:.0f}s on the {navigation} page")
    return True


# --------------------------------------------------------------- public API
def browse_to_video(web_driver, video_url, entry_pages, title, report=print,
                    abort_check=lambda seconds: None, quality=None):
    """Reach video_url by browsing. entry_pages: [(navigation name, url)] in
    the order to try. Falls back to YouTube search (if a title is known),
    then to opening the link directly. Returns a NavigationResult; with
    result.opened False the caller opens the link itself (direct-fallback)."""
    result = NavigationResult()
    started_at = time.monotonic()
    video_id = youtube.extract_video_id(video_url)
    web_driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
    attempts = list(entry_pages)
    if title:
        attempts.append(("search", f"https://www.youtube.com/results?search_query={quote_plus(title)}"))
    for navigation, entry_url in attempts:
        if abort_check(time.monotonic() - started_at):
            result.failure = "stopped"
            return result
        max_scrolls = config.BROWSE_MAX_SEARCH_SCROLLS if navigation != "search" else 3
        if _try_entry(web_driver, navigation, entry_url, video_id, result, report, abort_check,
                      started_at, max_scrolls, quality):
            return result
        report(f"browsing: {result.notes[-1]}")
    result.navigation = "direct-fallback"
    return result


# ------------------------------------------------------- playlist sessions
# Next video of a playlist session, from the watch page of the previous one:
#   "click"    : a viewer picks another video in the playlist panel beside
#                the player;
#   "in_order" : a viewer presses the player's Next button (playlist order,
#                what autoplay would do).
PANEL_LINK_SELECTORS = (
    'ytd-playlist-panel-video-renderer a#wc-endpoint[href*="v={id}"]',
    'ytd-playlist-panel-renderer a[href*="v={id}"]',
)
NEXT_BUTTON_SELECTOR = "#movie_player .ytp-next-button"


def _panel_link(web_driver, video_id):
    for selector in PANEL_LINK_SELECTORS:
        for element in web_driver.find_elements(By.CSS_SELECTOR, selector.format(id=video_id)):
            return element
    return None


def _wait_for_new_video(web_driver, previous_video_id):
    """Video id in the address bar once it differs from previous_video_id."""
    deadline = time.monotonic() + CLICK_NAVIGATION_TIMEOUT
    while time.monotonic() < deadline:
        try:
            current_video_id = youtube.extract_video_id(web_driver.current_url)
            if current_video_id and current_video_id != previous_video_id:
                return current_video_id
        except WebDriverException:
            pass  # page in the middle of changing; try again
        time.sleep(0.3)
    return None


def _random_panel_link(web_driver, known_video_ids, previous_video_id):
    """(link, video id) of a random panel entry that is in the playlist list."""
    candidates = []
    for element in web_driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-panel-video-renderer a#wc-endpoint"):
        try:
            video_id = youtube.extract_video_id(element.get_attribute("href") or "")
        except StaleElementReferenceException:
            continue
        if video_id and video_id != previous_video_id and video_id in known_video_ids:
            candidates.append((element, video_id))
    return random.choice(candidates) if candidates else (None, None)


def next_in_session(web_driver, target_video_id, previous_video_id, how, report=print,
                    abort_check=lambda seconds: None, quality=None, known_video_ids=()):
    """Open the next video of a session from the current watch page.
    how: "click" (target_video_id in the playlist panel) or "next_button"
    (player's Next button; the video it opens may differ from the target,
    e.g. when the playlist skips an unavailable one). With known_video_ids,
    a target not shown in the panel is replaced by a random panel video that
    is in that set. Returns
    (NavigationResult, opened video id or None)."""
    result = NavigationResult(entry_url="(watch page of the previous video)")
    started_at = time.monotonic()
    result.dwell_seconds = round(random.uniform(*config.BETWEEN_VIDEOS_SECONDS), 1)
    deadline = time.monotonic() + result.dwell_seconds
    while time.monotonic() < deadline:          # a moment before choosing the next one
        if abort_check(time.monotonic() - started_at):
            result.failure = "stopped"
            return result, None
        youtube.dismiss_consent(web_driver, report)
        time.sleep(0.25)
    if quality:
        web_driver.execute_script(youtube.QUALITY_PREFERENCE_SCRIPT, youtube.CODE_HEIGHTS[quality])

    if how == "next_button":
        buttons = web_driver.find_elements(By.CSS_SELECTOR, NEXT_BUTTON_SELECTOR)
        if buttons:
            try:
                # Controls show while the pointer is over the player.
                ActionChains(web_driver).move_to_element(
                    web_driver.find_element(By.CSS_SELECTOR, "#movie_player")).perform()
                time.sleep(random.uniform(0.4, 1.0))
                result.click_epoch = time.time()
                _click(web_driver, buttons[0])
                opened_video_id = _wait_for_new_video(web_driver, previous_video_id)
                if opened_video_id:
                    result.navigation, result.opened = "next-button", True
                    report("pressed the player's Next button")
                    return result, opened_video_id
                result.notes.append("Next button did not open another video")
            except (StaleElementReferenceException, NoSuchElementException, JavascriptException,
                    WebDriverException) as click_error:
                result.notes.append(f"Next button click failed ({type(click_error).__name__})")
        else:
            result.notes.append("no Next button")
        report(f"browsing: {result.notes[-1]} - choosing it in the playlist panel")

    link = _panel_link(web_driver, target_video_id)
    if link is None and known_video_ids:
        # Long playlists: the panel lists only part of the playlist (~200
        # videos around the current one) - pick one of those instead.
        link, target_video_id = _random_panel_link(web_driver, set(known_video_ids), previous_video_id)
    if link is None:
        result.notes.append("video not in the playlist panel")
        return result, None
    try:
        result.click_epoch = time.time()
        _click(web_driver, link)
    except (StaleElementReferenceException, NoSuchElementException, JavascriptException) as click_error:
        result.notes.append(f"panel click failed ({type(click_error).__name__})")
        return result, None
    if not _wait_for_video_address(web_driver, target_video_id):
        result.notes.append("panel click did not open the video")
        return result, None
    result.navigation, result.opened = "playlist-panel", True
    report(f"clicked the next video in the playlist panel after {result.dwell_seconds:.0f}s")
    return result, target_video_id


# Ids of the playlist's video links currently inside the visible part of the
# window (what a viewer can see and click without searching).
VISIBLE_PLAYLIST_LINKS_SCRIPT = r"""
const listId = arguments[0];
const ids = [];
for (const link of document.querySelectorAll('a[href*="/watch?v="]')) {
  let url; try { url = new URL(link.href); } catch (e) { continue; }
  if (listId && url.searchParams.get('list') !== listId) continue;
  const id = url.searchParams.get('v');
  const box = link.getBoundingClientRect();
  if (!id || box.width < 20 || box.height < 10) continue;
  if (box.bottom < 60 || box.top > window.innerHeight - 20) continue;
  if (!ids.includes(id)) ids.push(id);
}
return ids;
"""


def browse_playlist_page(web_driver, entry_url, playlist_list_id, known_video_ids, report=print,
                         abort_check=lambda seconds: None, quality=None):
    """Playlist page -> look and scroll a little -> click one of the videos
    in view, as a viewer would (no searching for a particular video).
    Returns (NavigationResult, clicked video id or None)."""
    result = NavigationResult()
    started_at = time.monotonic()
    web_driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
    report(f"browsing: playlist page {entry_url}")
    if not _open_entry_page(web_driver, entry_url, report, abort_check, started_at):
        result.notes.append("playlist: page showed no videos")
        return result, None
    result.dwell_seconds = _random_dwell(web_driver, abort_check, started_at, report)
    youtube.dismiss_consent(web_driver, report)
    known = set(known_video_ids)
    in_view = [video_id for video_id in web_driver.execute_script(VISIBLE_PLAYLIST_LINKS_SCRIPT, playlist_list_id)
               if video_id in known]
    if not in_view:
        result.notes.append("playlist: no playlist video in view")
        return result, None
    video_id = random.choice(in_view)
    link = None
    for element in web_driver.find_elements(By.CSS_SELECTOR, f'a[href*="v={video_id}"]'):
        try:
            if element.is_displayed():
                link = element
                break
        except StaleElementReferenceException:
            continue
    if link is None:
        result.notes.append("playlist: chosen link vanished")
        return result, None
    if quality:
        web_driver.execute_script(youtube.QUALITY_PREFERENCE_SCRIPT, youtube.CODE_HEIGHTS[quality])
    try:
        result.click_epoch = time.time()
        _click(web_driver, link)
    except (StaleElementReferenceException, NoSuchElementException, JavascriptException) as click_error:
        result.notes.append(f"playlist: click failed ({type(click_error).__name__})")
        return result, None
    if not _wait_for_video_address(web_driver, video_id):
        result.notes.append("playlist: click did not open the video")
        return result, None
    result.navigation, result.entry_url, result.opened = "playlist", entry_url, True
    report(f"clicked a video in view after {result.dwell_seconds:.0f}s on the playlist page")
    return result, video_id
