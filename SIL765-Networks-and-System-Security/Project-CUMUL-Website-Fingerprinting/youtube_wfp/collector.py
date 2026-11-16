"""
File: collector.py
Purpose:
    Runs PARALLEL_INSTANCES slots at the same time. Each slot (own tor, own
    browser, own capture) takes the next instance number from a shared queue
    and, for that instance: new Tor circuit -> fresh browser -> capture pinned
    to the slot's tor connections -> video played muted to its end -> stop
    capture -> keep the file only if the playback completed and the capture
    is sane. Every attempt (kept or discarded) goes to data/collection_log.csv.
    Playlist mode with VIDEOS_PER_CIRCUIT > 1: one circuit + browser per
    SESSION of several playlist videos (one capture each, the next video
    reached from the previous one's watch page) - _run_playlist_session().

File naming:
    data/raw/<VIDEO_LABEL>_<NNN>.pcapng          completed instance
    data/raw/<VIDEO_LABEL>_<NNN>.partial.pcapng  being written (removed if the
                                                 attempt fails)
    Completed files are skipped on the next run, so an interrupted run resumes.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import csv
import glob
import itertools
import os
import queue
import random
import struct
import threading
import time
from collections import Counter
from datetime import datetime

import stem
from selenium.common.exceptions import WebDriverException

import config
import browser
import failure_policy
import browsing
import playlist
import random_periods
import capture
import youtube
from tor_control import TorSession

LOG_COLUMNS = [
    "timestamp", "video_label", "instance", "slot", "attempt", "session", "position_in_session",
    "period", "parallel_in_period",
    "mode", "playlist_position", "video_id", "navigation", "entry_url", "dwell_s", "click_epoch", "click_offset_s",
    "status", "reason",
    "video_title", "video_duration_s", "played_until_s", "wall_time_s",
    "ads_seen", "ads_count", "ads_skipped", "ad_seconds", "rebuffer_events", "resumes", "quality_requested", "quality", "quality_share",
    "speed_requested", "speed", "speed_changed_at_s",
    "packets", "wire_bytes",
    "capture_engine", "capture_filter", "local_ip", "tor_connections", "circuit_path", "browser", "file",
]

PLACEHOLDER_VIDEO_ID = "PASTE_VIDEO_ID_HERE"

_print_lock = threading.Lock()
_log_lock = threading.Lock()
_stop_requested = threading.Event()
_progress_lock = threading.Lock()
_progress = {"kept": 0, "target": 0}
_policy = failure_policy.FailurePolicy(_stop_requested, report=lambda message: say("[all slots]", message))
_scheduler = None   # random_periods.RandomPeriodScheduler, created per run
_playlist_videos = []   # playlist.PlaylistVideo list (MODE = "playlist")
_video_info = {}        # title + channel of the single-mode video (NAVIGATION = "browse")
_session_counter = itertools.count(1)
_attempts_lock = threading.Lock()
_attempts = Counter()   # attempts per instance number (playlist sessions)


def instance_name(instance_index):
    """<label>_<NNN>: zero-padded to 3 digits, more if INSTANCES > 1000."""
    width = max(3, len(str(max(config.INSTANCES, 1) - 1)))
    return f"{config.VIDEO_LABEL}_{instance_index:0{width}d}"


def say(prefix, message):
    """Thread-safe console line, prefixed with the slot / instance."""
    with _print_lock:
        print(f"  {prefix} {message}", flush=True)


_quality_lock = threading.Lock()
_quality_rotation = {"next": 0}


def _pick(values, selection, rotation_key):
    """One of values: the only one, or at random / in rotation."""
    if len(values) == 1:
        return values[0]
    if selection == "rotate":
        with _quality_lock:
            value = values[_quality_rotation.setdefault(rotation_key, 0) % len(values)]
            _quality_rotation[rotation_key] += 1
        return value
    return random.choice(values)


def pick_speed():
    """Playback speed for the next capture (PLAYBACK_SPEED / PLAYBACK_SPEED_SELECTION)."""
    return _pick(youtube.configured_speeds(), config.PLAYBACK_SPEED_SELECTION, "speed")


def pick_quality():
    """Resolution (player code, None = Auto) for the next capture: the single
    configured one, or one of the list - at random, or in rotation."""
    qualities = youtube.configured_qualities()
    if len(qualities) == 1:
        return qualities[0]
    if config.VIDEO_QUALITY_SELECTION == "rotate":
        with _quality_lock:
            quality = qualities[_quality_rotation["next"] % len(qualities)]
            _quality_rotation["next"] += 1
        return quality
    return random.choice(qualities)


def validate_video_settings():
    youtube.configured_qualities()   # raises ValueError for an unknown resolution name
    youtube.configured_speeds()      # raises ValueError for an unsupported speed
    if config.PLAYBACK_SPEED_SELECTION not in ("random", "rotate"):
        raise ValueError('PLAYBACK_SPEED_SELECTION must be "random" or "rotate"')
    if config.VIDEO_QUALITY_SELECTION not in ("random", "rotate"):
        raise ValueError('VIDEO_QUALITY_SELECTION must be "random" or "rotate"')
    if "_" in config.VIDEO_LABEL or not config.VIDEO_LABEL:
        raise ValueError("VIDEO_LABEL must be non-empty and contain no underscore.")
    if config.MODE not in ("single", "playlist"):
        raise ValueError('MODE must be "single" or "playlist"')
    if config.MODE == "playlist":
        videos_per_circuit_range()   # raises ValueError for a bad VIDEOS_PER_CIRCUIT
        if config.NEXT_VIDEO not in ("click", "in_order"):
            raise ValueError('NEXT_VIDEO must be "click" or "in_order"')
        if config.PLAYLIST_VIDEO_URLS:
            return f"{len(config.PLAYLIST_VIDEO_URLS)} videos listed in PLAYLIST_VIDEO_URLS"
        list_id = playlist.playlist_id()
        if not list_id or "PASTE_" in list_id:
            raise ValueError("Set YOUTUBE_PLAYLIST_URL in config.py to a real playlist link first.")
        return f"playlist {list_id}"
    video_id = youtube.extract_video_id(config.YOUTUBE_VIDEO_URL)
    if not video_id or video_id == PLACEHOLDER_VIDEO_ID:
        raise ValueError("Set YOUTUBE_VIDEO_URL in config.py to a real YouTube link first.")
    return video_id


def videos_per_circuit_range():
    """VIDEOS_PER_CIRCUIT as (low, high): 12 -> (12, 12); (10, 15) stays."""
    setting = config.VIDEOS_PER_CIRCUIT
    low, high = (setting, setting) if isinstance(setting, int) else tuple(setting)
    if not (1 <= low <= high):
        raise ValueError("VIDEOS_PER_CIRCUIT must be a number >= 1 or a range (low, high) with 1 <= low <= high")
    return low, high


def playlist_sessions_enabled():
    return config.MODE == "playlist" and videos_per_circuit_range()[1] > 1


def _next_video_in_session(previous_video):
    """Video for the next position of a playlist session."""
    if previous_video is None:
        return playlist.pick_random_video(_playlist_videos)        # first video: any
    if config.NEXT_VIDEO == "in_order":
        index = next((i for i, v in enumerate(_playlist_videos) if v.video_id == previous_video.video_id), -1)
        return _playlist_videos[(index + 1) % len(_playlist_videos)]
    others = [v for v in _playlist_videos if v.video_id != previous_video.video_id] or _playlist_videos
    return random.choice(others)


def completed_instance_path(instance_index):
    if config.MODE == "playlist":
        # Playlist captures sit in one folder per video: <label>/vNN/<label>_NNN.ext
        for extension in (".pcapng", ".pcap"):
            matches = glob.glob(os.path.join(playlist.playlist_folder(), "v*",
                                             instance_name(instance_index) + extension))
            if matches:
                return matches[0]
        return None
    for extension in (".pcapng", ".pcap"):
        candidate = os.path.join(config.DATA_RAW_DIR, instance_name(instance_index) + extension)
        if os.path.exists(candidate):
            return candidate
    return None


def append_log_row(log_row):
    with _log_lock:
        os.makedirs(os.path.dirname(config.COLLECTION_LOG_PATH), exist_ok=True)
        write_header = not os.path.exists(config.COLLECTION_LOG_PATH)
        if not write_header:
            with open(config.COLLECTION_LOG_PATH, newline="", encoding="utf-8") as log_file:
                existing_header = next(csv.reader(log_file), [])
            if existing_header != LOG_COLUMNS:
                # Log written by an earlier version of this app: keep it
                # aside and start a new one with the current columns.
                os.replace(config.COLLECTION_LOG_PATH,
                           config.COLLECTION_LOG_PATH.replace(".csv", f"_old_{int(time.time())}.csv"))
                write_header = True
        with open(config.COLLECTION_LOG_PATH, "a", newline="", encoding="utf-8") as log_file:
            log_writer = csv.DictWriter(log_file, fieldnames=LOG_COLUMNS)
            if write_header:
                log_writer.writeheader()
            log_writer.writerow({column: log_row.get(column, "") for column in LOG_COLUMNS})


def capture_one_attempt(tor_session, capture_engine, capture_interface, instance_index, attempt_number,
                        period_info=(0, 0), session=None):
    """One playback + capture in one slot. Returns True if the instance was kept.

    session None : own circuit and own browser for this one video (opened
                   and closed here).
    session dict : playlist session - the browser in session["web_driver"]
                   is already open on this slot's circuit; position 1 reaches
                   its video like a single capture, later positions from the
                   previous video's watch page (NEXT_VIDEO). session["video"]
                   is updated to the video played."""
    prefix = (f"[slot {tor_session.slot_index + 1} | {instance_name(instance_index)} try {attempt_number}"
              + (f" | session {session['id']} video {session['position']}]" if session else "]"))
    report = lambda message: say(prefix, message)  # noqa: E731

    extension = capture.capture_file_extension(capture_engine)
    previous_video = session["video"] if session else None
    if config.MODE == "playlist":
        # Session: the next video by NEXT_VIDEO; otherwise one at random.
        chosen_video = _next_video_in_session(previous_video)
        if previous_video is not None or config.NAVIGATION != "browse":
            report(f"{'next' if previous_video else 'random'} playlist video {chosen_video.position}: "
                   f"{chosen_video.title[:50] or chosen_video.video_id}")
        # The partial file sits beside the vNN folders: with the Next button
        # the video (and so its folder) is only known after the click.
        partial_path = os.path.join(playlist.playlist_folder(),
                                    instance_name(instance_index) + f".partial{extension}")
        os.makedirs(playlist.playlist_folder(), exist_ok=True)
    else:
        chosen_video = None
        partial_path = os.path.join(config.DATA_RAW_DIR, instance_name(instance_index) + f".partial{extension}")

    def final_path_for(video):
        if video is None:
            return os.path.join(config.DATA_RAW_DIR, instance_name(instance_index) + extension)
        return os.path.join(playlist.playlist_folder(), video.position, instance_name(instance_index) + extension)
    final_path = final_path_for(chosen_video)
    if os.path.exists(partial_path):
        os.remove(partial_path)

    log_row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "video_label": config.VIDEO_LABEL,
        "instance": instance_index,
        "slot": tor_session.slot_index + 1,
        "attempt": attempt_number,
        "session": session["id"] if session else "",
        "position_in_session": session["position"] if session else "",
        "period": period_info[0],
        "parallel_in_period": period_info[1],
        "capture_engine": capture_engine,
        "local_ip": capture_interface.ip_address,
        "browser": config.BROWSER,
        "mode": config.MODE,
        "playlist_position": chosen_video.position if chosen_video else "",
        "video_id": chosen_video.video_id if chosen_video else youtube.extract_video_id(config.YOUTUBE_VIDEO_URL),
    }
    video_url = chosen_video.url if chosen_video else config.YOUTUBE_VIDEO_URL
    playback_result = youtube.PlaybackResult()
    packet_capture = None
    web_driver = session["web_driver"] if session else None

    def abort_check(playback_seconds):
        if _stop_requested.is_set():
            return "stopped by user"
        if playback_seconds > 3 and not log_row.get("circuit_path"):
            log_row["circuit_path"] = tor_session.circuit_path_for() or "-"
            report(f"circuit: {log_row['circuit_path']}")
        if (packet_capture is not None and playback_seconds >= config.CAPTURE_HEALTH_CHECK_SECONDS
                and not packet_capture.packets_seen()):
            return (f"capture recorded nothing after {config.CAPTURE_HEALTH_CHECK_SECONDS}s of playback "
                    f"- wrong interface or filter [{log_row.get('capture_filter')}]")
        return None

    try:
        if session is None:
            # Rotate BEFORE launching the browser: NEWNYM affects new connections only.
            report("new Tor circuit, launching browser")
            tor_session.new_circuit()
            web_driver = browser.open_browser(tor_session)
            time.sleep(config.BROWSER_SETTLE_SECONDS)

        tor_connections = tor_session.network_connections()
        guard_addresses = [] if tor_connections else tor_session.guard_addresses()
        capture_filter = capture.build_capture_filter(tor_connections, guard_addresses)
        log_row["tor_connections"] = " ".join(f"{ip}:{rport}<-{lip}:{lport}" for ip, rport, lport, lip in tor_connections) \
            or "guards " + " ".join(guard_addresses)
        log_row["capture_filter"] = capture_filter
        report(f"capture on: {capture_filter}")

        # dumpcap auto-stop is only a crash safety net.
        capture_time_limit = config.PAGE_LOAD_TIMEOUT + config.PLAYER_READY_TIMEOUT + 6 * 3600
        packet_capture = capture.PacketCapture(capture_engine, capture_interface, capture_filter,
                                               partial_path, capture_time_limit,
                                               tor_connections=tor_connections, guard_addresses=guard_addresses)
        packet_capture.start()

        capture_start_epoch = time.time()
        quality = pick_quality()
        speed = pick_speed()
        if quality or speed != 1.0:
            report(f"this capture: resolution {youtube.resolution_label(quality)}, speed {speed:g}x")
        navigation = browsing.NavigationResult(navigation="direct")
        if previous_video is not None:
            # Session, video 2 onward: from the previous video's watch page.
            how = "next_button" if config.NEXT_VIDEO == "in_order" else "click"
            navigation, opened_video_id = browsing.next_in_session(
                web_driver, chosen_video.video_id, previous_video.video_id, how, report, abort_check, quality=quality,
                known_video_ids=[video.video_id for video in _playlist_videos])
            if navigation.opened and opened_video_id != chosen_video.video_id:
                opened_video = next((v for v in _playlist_videos if v.video_id == opened_video_id), None)
                if opened_video is None:
                    raise RuntimeError(f"the next video opened is not in the playlist list ({opened_video_id})")
                report(f"next video is {opened_video.position} (instead of {chosen_video.position})")
                chosen_video = opened_video
                video_url = chosen_video.url
                final_path = final_path_for(chosen_video)
                log_row.update(playlist_position=chosen_video.position, video_id=chosen_video.video_id)
            if not navigation.opened:
                report(f"browsing: {navigation.notes[-1] if navigation.notes else 'next video not opened'}")
                navigation.navigation = "direct-fallback"
        if (config.NAVIGATION == "browse" and chosen_video is not None and not navigation.opened
                and navigation.failure != "stopped"):
            # Playlist: open the playlist page and click one of the videos in
            # view (as a viewer would) - not a search for a particular one.
            navigation, opened_video_id = browsing.browse_playlist_page(
                web_driver, playlist.playlist_page_urls()[0], playlist.playlist_id(),
                [video.video_id for video in _playlist_videos], report, abort_check, quality=quality)
            if navigation.opened:
                chosen_video = next(video for video in _playlist_videos if video.video_id == opened_video_id)
                video_url = chosen_video.url
                final_path = final_path_for(chosen_video)
                log_row.update(playlist_position=chosen_video.position, video_id=chosen_video.video_id)
                report(f"playlist video {chosen_video.position}: {chosen_video.title[:50] or chosen_video.video_id}")
            else:
                report(f"browsing: {navigation.notes[-1] if navigation.notes else 'no video clicked'}")
                navigation.navigation = "direct-fallback"
        elif (config.NAVIGATION == "browse" and chosen_video is None and not navigation.opened
              and navigation.failure != "stopped"):
            # Single mode: the channel's Videos tab -> find this video (search
            # by title only if the channel page does not show it).
            entry_pages = [("channel", browsing.channel_videos_url(_video_info["channel_url"]))]
            title = _video_info.get("title", "")
            navigation = browsing.browse_to_video(web_driver, video_url, entry_pages, title, report, abort_check,
                                                  quality=quality)
        if not navigation.opened:
            # Direct mode, or browsing found no way to click the video.
            navigation.click_epoch = time.time()
            if navigation.navigation == "direct-fallback":
                report("browsing: opening the video link directly (fallback)")
        log_row.update({
            "navigation": navigation.navigation, "entry_url": navigation.entry_url,
            "dwell_s": navigation.dwell_seconds, "click_epoch": f"{navigation.click_epoch:.3f}",
            "click_offset_s": round(navigation.click_epoch - capture_start_epoch, 3),
        })
        playback_result = youtube.play_video_to_end(web_driver, video_url, report, abort_check,
                                                    already_open=navigation.opened, quality=quality,
                                                    speed=speed, hold_at_end=session is not None)
        if not playback_result.completed and playback_result.reason != "stopped by user":
            snapshot = _policy.save_snapshot(web_driver, instance_name(instance_index) + f"_try{attempt_number}",
                                             playback_result.reason)
            if snapshot:
                report(f"evidence saved: {os.path.relpath(snapshot, config.PROJECT_DIR)}.png/.txt")

        # Stop the player at once (no next video), then keep capturing
        # briefly so the tail of the transfer is included. In a session the
        # page stays (the next video is chosen from it); only the player stops.
        try:
            if session is not None:
                web_driver.execute_script(youtube.PAUSE_PLAYER_SCRIPT)
            else:
                web_driver.get("about:blank")
        except WebDriverException:
            pass  # browser already gone; the capture is still valid
        time.sleep(config.POST_VIDEO_WAIT_SECONDS)
    except (WebDriverException, RuntimeError, OSError, ValueError, stem.ControllerError) as attempt_error:
        error_message = getattr(attempt_error, "msg", None) or str(attempt_error)
        playback_result.reason = f"{type(attempt_error).__name__}: {' '.join(error_message.split())[:200]}"
    finally:
        if packet_capture is not None:
            packet_capture.stop()
        if web_driver is not None and session is None:
            browser.close_browser(web_driver)
    if session is not None:
        session["video"] = chosen_video

    capture_summary = capture.CaptureSummary(0, 0)
    if os.path.exists(partial_path):
        try:
            capture_summary = capture.summarize_capture(partial_path)
        except (OSError, struct.error, ValueError) as read_error:
            playback_result.completed = False
            playback_result.reason += f" | capture unreadable: {read_error}"

    kept = playback_result.completed and capture_summary.packets >= config.MIN_PACKETS
    if playback_result.completed and not kept:
        playback_result.reason = (f"capture too small: {capture_summary.packets} packets "
                                  f"(< MIN_PACKETS {config.MIN_PACKETS}) - check interface/filter")
    if kept:
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        os.replace(partial_path, final_path)
    elif os.path.exists(partial_path):
        os.remove(partial_path)

    log_row.update({
        "status": "OK" if kept else "FAILED",
        "reason": playback_result.reason,
        "video_title": playback_result.video_title,
        "video_duration_s": playback_result.video_duration_seconds,
        "played_until_s": playback_result.played_until_seconds,
        "wall_time_s": playback_result.wall_seconds,
        "ads_seen": playback_result.ads_seen,
        "ads_count": playback_result.ads_count,
        "ads_skipped": playback_result.ads_skipped,
        "ad_seconds": playback_result.ad_seconds,
        "rebuffer_events": playback_result.rebuffer_events,
        "resumes": playback_result.resumes,
        "quality_requested": playback_result.quality_requested,
        "quality": playback_result.quality,
        "quality_share": playback_result.quality_share,
        "speed_requested": playback_result.speed_requested,
        "speed": playback_result.speed,
        "speed_changed_at_s": playback_result.speed_changed_at_seconds,
        "packets": capture_summary.packets,
        "wire_bytes": capture_summary.wire_bytes,
        "file": os.path.relpath(final_path, config.DATA_RAW_DIR) if kept else "",
    })
    append_log_row(log_row)

    with _progress_lock:
        if kept:
            _progress["kept"] += 1
        kept_so_far, target = _progress["kept"], _progress["target"]
    _policy.record(kept, playback_result.reason)
    if kept:
        report(f"OK  {capture_summary.packets:,} packets, {capture_summary.wire_bytes / 1e6:.1f} MB, "
               f"{playback_result.resumes} resume(s) -> {os.path.basename(final_path)}   "
               f"[successful: {kept_so_far}/{target}]")
    else:
        report(f"FAILED: {playback_result.reason}  (packets captured: {capture_summary.packets})")
    return kept


def _run_playlist_session(tor_session, capture_engine, capture_interface, pending_instances, outcome, slot_prefix):
    """Playlist session: one new circuit + one browser, then a random number
    (VIDEOS_PER_CIRCUIT) of playlist videos one after the other, one capture
    each. A failed video ends the session; it and the session's unplayed
    instance numbers go back to the queue for a later session (new circuit).
    Returns False when there was nothing left to do."""
    session_size = random.randint(*videos_per_circuit_range())
    instance_numbers = []
    while len(instance_numbers) < session_size:
        try:
            instance_numbers.append(pending_instances.get_nowait())
        except queue.Empty:
            break
    if not instance_numbers:
        return False
    done = []
    period_info = _scheduler.acquire()
    if period_info is None:
        for instance_index in instance_numbers:
            pending_instances.put(instance_index)
        return True
    session = {"id": next(_session_counter), "position": 0, "video": None, "web_driver": None}
    try:
        say(slot_prefix, f"session {session['id']}: new Tor circuit, launching browser for "
                         f"{len(instance_numbers)} playlist video(s)")
        tor_session.new_circuit()   # BEFORE the browser: NEWNYM affects new connections only
        session["web_driver"] = browser.open_browser(tor_session)
        time.sleep(config.BROWSER_SETTLE_SECONDS)
        for instance_index in instance_numbers:
            if _stop_requested.is_set():
                break
            session["position"] += 1
            with _attempts_lock:
                _attempts[instance_index] += 1
                attempt_number = _attempts[instance_index]
            if not capture_one_attempt(tor_session, capture_engine, capture_interface, instance_index,
                                       attempt_number, period_info, session):
                say(slot_prefix, f"session {session['id']}: video failed - ending this session; "
                                 "the rest continue in a new session on a new circuit")
                break
            done.append(instance_index)
    except (WebDriverException, RuntimeError, OSError, ValueError, stem.ControllerError) as session_error:
        error_message = getattr(session_error, "msg", None) or str(session_error)
        reason = f"{type(session_error).__name__}: {' '.join(error_message.split())[:200]}"
        say(slot_prefix, f"session {session['id']} FAILED to start: {reason}")
        _policy.record(False, reason)
        append_log_row({"timestamp": datetime.now().isoformat(timespec="seconds"),
                        "video_label": config.VIDEO_LABEL, "instance": instance_numbers[len(done)],
                        "slot": tor_session.slot_index + 1, "session": session["id"],
                        "position_in_session": session["position"], "period": period_info[0],
                        "parallel_in_period": period_info[1], "mode": config.MODE, "status": "FAILED",
                        "reason": reason, "browser": config.BROWSER})
    finally:
        if session["web_driver"] is not None:
            browser.close_browser(session["web_driver"])
        _scheduler.release()
    outcome["kept"].extend(done)
    for instance_index in instance_numbers:
        if instance_index not in done:
            pending_instances.put(instance_index)
    return True


def _slot_worker(slot_index, pending_instances, capture_engine, capture_interface, outcome):
    """One parallel slot: own tor, own browser per instance. Takes instance
    numbers from the shared queue and retries each one (new circuit every
    attempt) until it is captured successfully - so the run ends with
    exactly INSTANCES successful captures, no gaps."""
    slot_prefix = f"[slot {slot_index + 1}]"
    time.sleep(slot_index * config.SLOT_START_STAGGER_SECONDS)
    if _stop_requested.is_set():
        return
    tor_session = TorSession(slot_index, report=lambda message: say(slot_prefix, message))
    try:
        tor_session.start()
        while playlist_sessions_enabled() and not _stop_requested.is_set():
            _policy.wait_if_cooling_down()
            if _stop_requested.is_set():
                break
            if not tor_session.is_alive():
                say(slot_prefix, "tor connection lost - restarting this slot's tor")
                tor_session.close()
                tor_session.start()
            if not _run_playlist_session(tor_session, capture_engine, capture_interface,
                                         pending_instances, outcome, slot_prefix):
                return
            if not pending_instances.empty():
                time.sleep(random.uniform(*config.INTER_INSTANCE_DELAY_RANGE))
        while not _stop_requested.is_set():
            try:
                instance_index = pending_instances.get_nowait()
            except queue.Empty:
                return
            attempt_number = 0
            while not _stop_requested.is_set():
                _policy.wait_if_cooling_down()
                if _stop_requested.is_set():
                    break
                attempt_number += 1
                if not tor_session.is_alive():
                    say(slot_prefix, "tor connection lost - restarting this slot's tor")
                    tor_session.close()
                    tor_session.start()
                # Random periods: wait until the current period allows one
                # more browser (random_periods.py).
                period_info = _scheduler.acquire()
                if period_info is None:
                    break
                try:
                    kept = capture_one_attempt(tor_session, capture_engine, capture_interface,
                                               instance_index, attempt_number, period_info)
                finally:
                    _scheduler.release()
                if kept:
                    outcome["kept"].append(instance_index)
                    break
            else:
                pending_instances.put(instance_index)   # interrupted: leave it for the next run
            if not pending_instances.empty():
                time.sleep(random.uniform(*config.INTER_INSTANCE_DELAY_RANGE))
    except (RuntimeError, OSError, TimeoutError, stem.ControllerError) as slot_error:
        say(slot_prefix, f"[ERROR] slot stopped: {type(slot_error).__name__}: {slot_error}")
    finally:
        tor_session.close()


def run_collection(instance_count=None):
    instance_count = instance_count or config.INSTANCES
    video_id = validate_video_settings()
    os.makedirs(config.DATA_RAW_DIR, exist_ok=True)
    _stop_requested.clear()
    if config.MODE == "playlist":
        global _playlist_videos

        def start_reader_tor():
            reader_tor = TorSession(0, report=lambda message: say("[playlist]", message))
            reader_tor.start()
            return reader_tor
        _playlist_videos = playlist.load_playlist(start_reader_tor, report=lambda message: say("[playlist]", message))
    elif config.NAVIGATION == "browse":
        global _video_info

        def open_lookup_browser():
            lookup_tor = TorSession(0, report=lambda message: say("[browse]", message))
            lookup_tor.start()
            lookup_driver = browser.open_browser(lookup_tor)

            def close_lookup(web_driver):
                browser.close_browser(web_driver)
                lookup_tor.close()
            return lookup_driver, close_lookup
        _video_info = browsing.resolve_video_info(open_lookup_browser, config.YOUTUBE_VIDEO_URL,
                                                  report=lambda message: say("[browse]", message))

    pending_instances = queue.Queue()
    already_done = []
    for instance_index in range(instance_count):
        if completed_instance_path(instance_index):
            already_done.append(instance_index)
        else:
            pending_instances.put(instance_index)
    slot_count = max(1, min(config.PARALLEL_INSTANCES, pending_instances.qsize()))
    with _progress_lock:
        _progress.update(kept=len(already_done), target=instance_count)
    global _policy
    _policy = failure_policy.FailurePolicy(_stop_requested, report=lambda message: say("[all slots]", message))

    capture_interface = capture.resolve_capture_interface()
    capture_engine = capture.choose_working_engine(capture_interface, config.DATA_RAW_DIR,
                                                   report=lambda message: print(f"  {message}"))
    print("=" * 72)
    if config.MODE == "playlist":
        print(f"  Playlist  : {config.YOUTUBE_PLAYLIST_URL}")
        print(f"              {len(_playlist_videos)} videos "
              f"(list: {os.path.relpath(playlist.playlist_file(), config.PROJECT_DIR)})")
        low, high = videos_per_circuit_range()
        if playlist_sessions_enabled():
            next_way = ("a random other video clicked in the playlist panel" if config.NEXT_VIDEO == "click"
                        else "the player's Next button (playlist order)")
            print(f"  Sessions  : {low}-{high} videos per circuit/browser; first video at random, "
                  f"then {next_way}")
        else:
            print("  Sessions  : 1 video per circuit/browser (a random playlist video)")
    else:
        print(f"  Video     : {config.YOUTUBE_VIDEO_URL}  (id {video_id})")
    print(f"  Label     : {config.VIDEO_LABEL}   Instances: {instance_count} "
          f"({len(already_done)} already done)   Parallel: {slot_count}   Browser: {config.BROWSER}")
    print(f"  Capture   : {capture_engine} on {capture_interface.description} ({capture_interface.ip_address})")
    print(f"  Muted     : {config.MUTE_AUDIO}   On YouTube error: {config.ON_PLAYER_ERROR}")
    qualities = [youtube.resolution_label(code) for code in youtube.configured_qualities()]
    print(f"  Resolution: {', '.join(qualities)}"
          + (f" ({config.VIDEO_QUALITY_SELECTION} per capture)" if len(qualities) > 1 else ""))
    speeds = [f"{speed:g}x" for speed in youtube.configured_speeds()]
    print(f"  Speed     : {', '.join(speeds)}"
          + (f" ({config.PLAYBACK_SPEED_SELECTION} per capture)" if len(speeds) > 1 else "")
          + (f", changed {config.SPEED_CHANGE_AFTER_SECONDS[0]}-{config.SPEED_CHANGE_AFTER_SECONDS[1]} s "
             "into the video" if speeds != ["1x"] else ""))
    if config.NAVIGATION == "browse":
        entry = "playlist page" if config.MODE == "playlist" else f"channel {_video_info.get('channel_url', '?')}"
        print(f"  Browsing  : {entry} -> {config.BROWSE_DWELL_SECONDS[0]}-{config.BROWSE_DWELL_SECONDS[1]} s, "
              "scroll -> click the video (click time logged)")
    else:
        print("  Browsing  : off - video links opened directly")
    if config.RANDOM_PERIODS_ENABLED:
        print(f"  Rhythm    : random periods of {config.PERIOD_MINUTES_RANGE[0]}-{config.PERIOD_MINUTES_RANGE[1]} min, "
              f"{config.PARALLEL_RANGE[0]}-{min(config.PARALLEL_RANGE[1], slot_count)} browsers in parallel per period")
    print("=" * 72)
    if pending_instances.empty():
        print("  Nothing to do - all instances already captured.")
        return

    outcome = {"kept": [], "failed": []}
    global _scheduler
    _scheduler = random_periods.RandomPeriodScheduler(_stop_requested, slot_count,
                                                      report=lambda message: say("[all slots]", message))
    _scheduler.start()
    slot_threads = [threading.Thread(target=_slot_worker, daemon=True,
                                     args=(slot_index, pending_instances, capture_engine, capture_interface, outcome))
                    for slot_index in range(slot_count)]
    for slot_thread in slot_threads:
        slot_thread.start()
    try:
        # join() with a timeout keeps the main thread responsive to Ctrl+C.
        while any(slot_thread.is_alive() for slot_thread in slot_threads):
            for slot_thread in slot_threads:
                slot_thread.join(timeout=0.5)
    except KeyboardInterrupt:
        print("\n  Ctrl+C - stopping all slots (closing browsers, captures and tor)...")
        _stop_requested.set()
        for slot_thread in slot_threads:
            slot_thread.join(timeout=60)
        raise

    print("=" * 72)
    complete_now = len(already_done) + len(outcome["kept"])
    print(f"  Successful captures: {complete_now}/{instance_count}")
    if complete_now < instance_count:
        print("  Not finished - run again to continue from where it stopped.")
    print(f"  Captures: {config.DATA_RAW_DIR}")
    print(f"  Log     : {config.COLLECTION_LOG_PATH}")
    print("=" * 72)


def show_status():
    capture_files = sorted(f for f in glob.glob(os.path.join(config.DATA_RAW_DIR, "**", "*.pcap*"), recursive=True)
                           if ".partial." not in f)
    # single mode: per label; playlist mode: per <label>/vNN folder (video)
    files_per_label = Counter(os.path.relpath(os.path.dirname(f), config.DATA_RAW_DIR).replace("\\", "/")
                              if os.path.dirname(f) != config.DATA_RAW_DIR else os.path.basename(f).rsplit("_", 1)[0]
                              for f in capture_files)
    print(f"\n  Captures in {config.DATA_RAW_DIR}:")
    if not files_per_label:
        print("    none yet")
    for label, count in sorted(files_per_label.items()):
        print(f"    {label:<20} {count} instance(s)")

    if not os.path.exists(config.COLLECTION_LOG_PATH):
        return
    with open(config.COLLECTION_LOG_PATH, newline="", encoding="utf-8") as log_file:
        log_rows = list(csv.DictReader(log_file))
    attempt_status = Counter(row.get("status", "") for row in log_rows)
    failure_reasons = Counter((row.get("reason") or "").split(":")[0] for row in log_rows
                              if row.get("status") != "OK")
    print(f"\n  Attempts logged: {len(log_rows)}  (OK {attempt_status.get('OK', 0)}, "
          f"FAILED {attempt_status.get('FAILED', 0)})")
    for reason, count in failure_reasons.most_common(8):
        print(f"    {count:3d} x {reason}")
    print("\n  Last 8 attempts:")
    for row in log_rows[-8:]:
        print(f"    {row.get('timestamp')}  #{int(row.get('instance') or 0):04d} slot {row.get('slot', '-')} "
              f"try {row.get('attempt')}  {row.get('status', ''):<6} "
              f"played {row.get('played_until_s')}/{row.get('video_duration_s')}s  {(row.get('reason') or '')[:50]}")
