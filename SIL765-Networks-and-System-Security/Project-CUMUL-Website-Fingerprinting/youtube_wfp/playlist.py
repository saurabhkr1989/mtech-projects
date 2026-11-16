"""
File: playlist.py
Purpose:
    Playlist mode (config.MODE = "playlist"): every instance plays ONE video
    chosen at random from a YouTube playlist, to its end. The random periods
    and the random number of parallel browsers (random_periods.py) apply
    exactly as in single-video mode.

    The list of videos is read once from the playlist page - over Tor, in
    Tor Browser, like every other page of this tool - and kept in
    data/raw/<VIDEO_LABEL>/playlist_videos.csv. Later runs reuse that file,
    so the video numbers (v01, v02, ...) and therefore the class folders
    stay the same; delete the file (or set PLAYLIST_REFRESH = True) to read
    the playlist again. Alternatively PLAYLIST_VIDEO_URLS lists the videos
    by hand and the page is not read at all.

    Each video is one class for the classifier:
        data/raw/<VIDEO_LABEL>/v03/<VIDEO_LABEL>_0123.pcapng
    (instance numbers are global across the playlist; the folder names the
    video, playlist_videos.csv maps v03 -> video id and title).

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-13
"""

import csv
import os
import random
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from selenium.common.exceptions import TimeoutException, WebDriverException

import config
import browser
import youtube

# Seconds to wait for the playlist page to show its videos.
PLAYLIST_PAGE_TIMEOUT = 90
# Scrolls to the bottom of the playlist page (each loads ~100 more videos).
MAX_PLAYLIST_SCROLLS = 30
# Titles YouTube shows for entries that cannot be played.
UNPLAYABLE_TITLES = ("[private video]", "[deleted video]", "[unavailable video]")

# Video entries of the playlist page: from the page's own data
# (ytInitialData, first ~100 videos) plus the rendered list (videos loaded
# by scrolling). Entries are merged by video id, in playlist order.
READ_PLAYLIST_SCRIPT = r"""
const found = [];
try {
  const tabs = window.ytInitialData.contents.twoColumnBrowseResultsRenderer.tabs;
  for (const tab of tabs) {
    const sections = tab.tabRenderer && tab.tabRenderer.content && tab.tabRenderer.content.sectionListRenderer;
    if (!sections) continue;
    for (const section of sections.contents) {
      for (const item of (section.itemSectionRenderer ? section.itemSectionRenderer.contents : [])) {
        const list = item.playlistVideoListRenderer;
        if (!list) continue;
        for (const entry of list.contents) {
          const video = entry.playlistVideoRenderer;
          if (!video) continue;
          found.push({video_id: video.videoId,
                      title: (video.title && (video.title.simpleText || (video.title.runs || []).map(r => r.text).join(''))) || '',
                      seconds: Number(video.lengthSeconds || 0),
                      playable: video.isPlayable !== false});
        }
      }
    }
  }
} catch (e) {}
// Newer playlist page format (seen 15 Nov 2026): entries are "lockupViewModel"
// objects (contentId = video id) instead of playlistVideoRenderer.
const clockSeconds = text => {
  if (!/^\d+(:\d\d)+$/.test((text || '').trim())) return 0;
  let seconds = 0; for (const part of text.trim().split(':')) seconds = seconds * 60 + Number(part);
  return seconds;
};
try {
  const lockups = [];
  const walk = (node, depth) => {
    if (!node || typeof node !== 'object' || depth > 40) return;
    if (Array.isArray(node)) { for (const child of node) walk(child, depth + 1); return; }
    for (const key of Object.keys(node)) {
      if (key === 'lockupViewModel') lockups.push(node[key]);
      else walk(node[key], depth + 1);
    }
  };
  walk(window.ytInitialData.contents.twoColumnBrowseResultsRenderer, 0);
  for (const lockup of lockups) {
    if (!lockup.contentId || (lockup.contentType && lockup.contentType !== 'LOCKUP_CONTENT_TYPE_VIDEO')) continue;
    const meta = lockup.metadata && lockup.metadata.lockupMetadataViewModel;
    let seconds = 0;
    try {
      for (const overlay of lockup.contentImage.thumbnailViewModel.overlays || []) {
        const bottom = overlay.thumbnailBottomOverlayViewModel;
        for (const badge of (bottom && bottom.badges) || []) {
          seconds = seconds || clockSeconds(badge.thumbnailBadgeViewModel && badge.thumbnailBadgeViewModel.text);
        }
      }
    } catch (e) {}
    found.push({video_id: lockup.contentId, title: (meta && meta.title && meta.title.content) || '',
                seconds: seconds, playable: true});
  }
} catch (e) {}
// Same format as rendered on the page (also the entries loaded by scrolling).
{
  const listId = new URLSearchParams(location.search).get('list');
  for (const lockup of document.querySelectorAll('yt-lockup-view-model')) {
    const link = Array.from(lockup.querySelectorAll('a[href*="v="]'))
                      .find(a => !listId || new URL(a.href).searchParams.get('list') === listId);
    const match = link && link.href.match(/[?&]v=([^&]+)/);
    if (!match) continue;
    const heading = lockup.querySelector('h3, .yt-lockup-metadata-view-model__title, [title]');
    const title = heading ? (heading.getAttribute('title') || heading.textContent || '').trim() : '';
    let seconds = 0;
    for (const badge of lockup.querySelectorAll('badge-shape, .yt-badge-shape__text, div, span')) {
      seconds = clockSeconds(badge.textContent);
      if (seconds) break;
    }
    found.push({video_id: match[1], title: title, seconds: seconds, playable: true});
  }
}
// Watch page with a playlist panel (watch?v=...&list=..., also YouTube "Mix" lists)
try {
  const panel = window.ytInitialData.contents.twoColumnWatchNextResults.playlist.playlist;
  for (const entry of panel.contents) {
    const video = entry.playlistPanelVideoRenderer;
    if (!video) continue;
    const text = video.lengthText && (video.lengthText.simpleText || '');
    const parts = text.split(':').map(Number);
    let seconds = 0; for (const part of parts) seconds = seconds * 60 + (isFinite(part) ? part : 0);
    found.push({video_id: video.videoId,
                title: (video.title && (video.title.simpleText || (video.title.runs || []).map(r => r.text).join(''))) || '',
                seconds: seconds, playable: !video.unplayableText});
  }
} catch (e) {}
for (const row of document.querySelectorAll('ytd-playlist-panel-video-renderer')) {
  const link = row.querySelector('a#wc-endpoint, a');
  const match = link && link.href.match(/[?&]v=([^&]+)/);
  const title = row.querySelector('#video-title');
  if (match) found.push({video_id: match[1], title: title ? (title.title || title.textContent || '').trim() : '',
                         seconds: 0, playable: true});
}
for (const row of document.querySelectorAll('ytd-playlist-video-renderer')) {
  const link = row.querySelector('a#video-title');
  const match = link && link.href.match(/[?&]v=([^&]+)/);
  if (match) found.push({video_id: match[1], title: (link.title || link.textContent || '').trim(),
                         seconds: 0, playable: true});
}
const header = document.querySelector('ytd-playlist-header-renderer, yt-page-header-renderer');
return {videos: found, page_title: document.title, header_text: header ? header.innerText.slice(0, 300) : '',
        url: location.href};
"""


@dataclass
class PlaylistVideo:
    position: str        # "v01", "v02", ... - class / folder name
    video_id: str
    title: str
    seconds: int

    @property
    def url(self):
        """Watch URL inside the playlist, as a viewer clicking the video in
        the playlist would open it."""
        return f"https://www.youtube.com/watch?v={self.video_id}&list={playlist_id()}"


def playlist_id():
    return parse_qs(urlparse(config.YOUTUBE_PLAYLIST_URL).query).get("list", [""])[0]


def playlist_page_urls():
    """Pages to read the video list from, in order.

    Seen on 13 Nov 2026: the configured link was a WATCH link
    (watch?v=...&list=PL...), which shows the playlist only in a side
    panel. The playlist's own page (youtube.com/playlist?list=ID) lists all
    videos and is read first; the configured link (its side panel) is the
    fallback - needed for YouTube "Mix" lists (list=RD...), which have no
    playlist page.
    """
    canonical_page = f"https://www.youtube.com/playlist?list={playlist_id()}"
    pages = [canonical_page]
    if config.YOUTUBE_PLAYLIST_URL.split("#")[0] != canonical_page:
        pages.append(config.YOUTUBE_PLAYLIST_URL)
    return pages


def playlist_folder():
    return os.path.join(config.DATA_RAW_DIR, config.VIDEO_LABEL)


def playlist_file():
    return os.path.join(playlist_folder(), "playlist_videos.csv")


def _position_label(index, total):
    return f"v{index + 1:0{max(2, len(str(total)))}d}"


def _save(videos):
    os.makedirs(playlist_folder(), exist_ok=True)
    with open(playlist_file(), "w", newline="", encoding="utf-8") as playlist_csv:
        writer = csv.writer(playlist_csv)
        writer.writerow(["position", "video_id", "title", "seconds", "url"])
        for video in videos:
            writer.writerow([video.position, video.video_id, video.title, video.seconds, video.url])


def _load_saved():
    if not os.path.exists(playlist_file()):
        return None
    with open(playlist_file(), newline="", encoding="utf-8") as playlist_csv:
        return [PlaylistVideo(row["position"], row["video_id"], row["title"], int(row["seconds"] or 0))
                for row in csv.DictReader(playlist_csv)]


def _from_config_list():
    video_ids = [youtube.extract_video_id(url) for url in config.PLAYLIST_VIDEO_URLS]
    video_ids = [video_id for video_id in video_ids if video_id]
    return [PlaylistVideo(_position_label(index, len(video_ids)), video_id, "", 0)
            for index, video_id in enumerate(video_ids)]


def _read_one_page(web_driver, page_url, report):
    web_driver.set_page_load_timeout(PLAYLIST_PAGE_TIMEOUT)
    try:
        web_driver.get(page_url)
    except TimeoutException:
        report("playlist page load event not reached - reading what is there")
    deadline = time.monotonic() + PLAYLIST_PAGE_TIMEOUT
    page = {"videos": []}
    while time.monotonic() < deadline:
        if youtube.dismiss_consent(web_driver, report):
            time.sleep(3)
        page = web_driver.execute_script(READ_PLAYLIST_SCRIPT)
        if page["videos"]:
            break
        time.sleep(2)
    if not page["videos"]:
        return page
    # Scroll to the bottom until no new videos appear (long playlists).
    known_count = 0
    for _scroll in range(MAX_PLAYLIST_SCROLLS):
        unique_ids = {video["video_id"] for video in page["videos"]}
        if len(unique_ids) == known_count:
            break
        known_count = len(unique_ids)
        youtube.dismiss_consent(web_driver, report)
        web_driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(3)
        page = web_driver.execute_script(READ_PLAYLIST_SCRIPT)
    return page


def _save_evidence(web_driver, page_url):
    """Screenshot + text of a playlist page that showed no videos."""
    debug_dir = os.path.join(os.path.dirname(config.DATA_RAW_DIR), "debug")
    os.makedirs(debug_dir, exist_ok=True)
    base_path = os.path.join(debug_dir, f"playlist-not-read__{int(time.time())}")
    try:
        web_driver.save_screenshot(base_path + ".png")
        page_text = web_driver.execute_script("return location.href + '\\n\\n' + document.body.innerText;")
    except WebDriverException as evidence_error:
        page_text = f"(could not read page: {evidence_error.msg})"
    with open(base_path + ".txt", "w", encoding="utf-8") as text_file:
        text_file.write(f"page: {page_url}\n\n{(page_text or '')[:20000]}")
    return base_path


def _read_playlist_page(tor_session, report):
    """Open the playlist page(s) in Tor Browser and return its playable videos."""
    web_driver = browser.open_browser(tor_session)
    page = {"videos": []}
    try:
        for page_url in playlist_page_urls():
            report(f"reading {page_url}")
            page = _read_one_page(web_driver, page_url, report)
            if page["videos"]:
                break
            evidence = _save_evidence(web_driver, page_url)
            report(f"no videos found there ({page.get('page_title', '')[:60]}) - evidence: "
                   f"{os.path.relpath(evidence, config.PROJECT_DIR)}.png/.txt")
    finally:
        browser.close_browser(web_driver)
    if not page["videos"]:
        raise RuntimeError("no videos found on the playlist page")

    merged = {}
    for video in page["videos"]:
        entry = merged.setdefault(video["video_id"], dict(video))
        entry["seconds"] = entry["seconds"] or video["seconds"]
        entry["title"] = entry["title"] or video["title"]
        entry["playable"] = entry["playable"] and video["playable"]
    playable = [video for video in merged.values()
                if video["playable"] and video["title"].strip().lower() not in UNPLAYABLE_TITLES]
    skipped = len(merged) - len(playable)
    if skipped:
        report(f"skipped {skipped} private / deleted / unavailable video(s) of the playlist")
    return [PlaylistVideo(_position_label(index, len(playable)), video["video_id"],
                          " ".join(video["title"].split()), int(video["seconds"] or 0))
            for index, video in enumerate(playable)]


def load_playlist(tor_session_factory, report=print):
    """The playlist's videos: from PLAYLIST_VIDEO_URLS, else the saved list,
    else read from the playlist page over Tor (with retries on a new
    circuit if YouTube refuses the page)."""
    if config.PLAYLIST_VIDEO_URLS:
        videos = _from_config_list()
        source = "PLAYLIST_VIDEO_URLS in config.py"
    else:
        videos = None if config.PLAYLIST_REFRESH else _load_saved()
        source = f"saved list {os.path.relpath(playlist_file(), config.PROJECT_DIR)}"
        if not videos:
            tor_session = tor_session_factory()
            try:
                last_error = None
                for attempt in range(1, 4):
                    try:
                        report(f"reading playlist page over Tor (attempt {attempt}/3)")
                        tor_session.new_circuit()
                        videos = _read_playlist_page(tor_session, report)
                        break
                    except (RuntimeError, WebDriverException) as read_error:
                        last_error = read_error
                        report(f"could not read the playlist: {getattr(read_error, 'msg', None) or read_error}")
                if not videos:
                    raise RuntimeError(f"playlist could not be read: {last_error}. You can list the videos "
                                       "by hand in PLAYLIST_VIDEO_URLS in config.py instead.")
            finally:
                tor_session.close()
            source = "playlist page"
    if not videos:
        raise RuntimeError("the playlist has no playable videos")
    _save(videos)
    report(f"playlist: {len(videos)} video(s) from {source} -> {os.path.relpath(playlist_file(), config.PROJECT_DIR)}")
    return videos


def pick_random_video(videos):
    return random.choice(videos)
