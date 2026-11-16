"""
File: collector.py
Purpose:
    Runs PARALLEL_INSTANCES slots at the same time over a shared list of
    browser SESSIONS. A session = new Tor circuit + fresh browser, the post
    loaded once and then refreshed REFRESHES_PER_SESSION times; every load
    (first load and each refresh) is captured into its own file and counts
    as one instance. A load that fails ends the session at once; its
    remaining instances go back to the list and a new session (new circuit,
    new browser) picks them up. Runs until every post has
    INSTANCES_PER_POST successful captures; every load is logged.

Files:
    data/raw/<post label>/<post label>_<NNNN>.pcap   one per successful instance
    data/collection_log.csv                          one row per attempt
    Existing captures are skipped, so an interrupted run resumes.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import csv
import glob
import itertools
import os
import queue
import random
import threading
import time
from collections import Counter
from datetime import datetime

import stem
from selenium.common.exceptions import WebDriverException

import config
import browser
import failure_policy
import capture
import browsing
import twitter
from tor_control import TorSession

# Hosts whose Tor streams identify the circuit carrying the post.
X_HOST_FRAGMENTS = ("x.com", "twitter.com", "twimg.com")

LOG_COLUMNS = [
    "timestamp", "post_label", "post_url", "instance", "slot", "session", "load_in_session",
    "navigation", "entry_url", "dwell_s", "click_epoch", "click_offset_s", "status", "reason",
    "has_video", "video_duration_s", "played_until_s", "load_s", "wall_time_s", "rebuffer_events",
    "packets", "wire_bytes", "connections", "capture_engine", "local_ip", "browser", "capture_root_pid",
    "circuit_path", "file",
]

_print_lock = threading.Lock()
_log_lock = threading.Lock()
_progress_lock = threading.Lock()
_stop_requested = threading.Event()
_progress = {"kept": 0, "target": 0}
_policy = failure_policy.FailurePolicy(_stop_requested, report=lambda message: say("[all slots]", message))


def say(prefix, message):
    with _print_lock:
        print(f"  {prefix} {message}", flush=True)


def validate_post_settings():
    problems = []
    for label, url in config.TWITTER_POSTS.items():
        if not label or "_" in label:
            problems.append(f'label "{label}": must be non-empty without underscore')
        if not twitter.extract_post_id(url) or "PASTE_" in url:
            problems.append(f'"{label}": not a post link ({url})')
    if not config.TWITTER_POSTS:
        problems.append("TWITTER_POSTS is empty")
    if problems:
        raise ValueError("Fix TWITTER_POSTS in config.py: " + "; ".join(problems))


def instance_name(post_label, instance_index):
    width = max(4, len(str(max(config.INSTANCES_PER_POST, 1) - 1)))
    return f"{post_label}_{instance_index:0{width}d}"


def instance_path(post_label, instance_index):
    return os.path.join(config.DATA_RAW_DIR, post_label, instance_name(post_label, instance_index) + ".pcap")


def append_log_row(log_row):
    with _log_lock:
        os.makedirs(os.path.dirname(config.COLLECTION_LOG_PATH), exist_ok=True)
        write_header = not os.path.exists(config.COLLECTION_LOG_PATH)
        if not write_header:
            with open(config.COLLECTION_LOG_PATH, newline="", encoding="utf-8") as log_file:
                existing_header = next(csv.reader(log_file), [])
            if existing_header != LOG_COLUMNS:
                # Log of an earlier version (other columns): keep it aside.
                os.replace(config.COLLECTION_LOG_PATH,
                           config.COLLECTION_LOG_PATH.replace(".csv", f"_old_{int(time.time())}.csv"))
                write_header = True
        with open(config.COLLECTION_LOG_PATH, "a", newline="", encoding="utf-8") as log_file:
            log_writer = csv.DictWriter(log_file, fieldnames=LOG_COLUMNS)
            if write_header:
                log_writer.writeheader()
            log_writer.writerow({column: log_row.get(column, "") for column in LOG_COLUMNS})


def _capture_one_load(session, web_driver, post_label, post_url, instance_index, load_number):
    """Capture one load (first load or a refresh) of the post in an already
    open browser. Returns (kept, reason)."""
    prefix = (f"[slot {session['slot'] + 1} | {instance_name(post_label, instance_index)} "
              f"session {session['id']} load {load_number}]")
    report = lambda message: say(prefix, message)  # noqa: E731
    final_path = instance_path(post_label, instance_index)
    partial_path = final_path.replace(".pcap", ".partial.pcap")
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    tor_session = session["tor_session"]

    log_row = {"timestamp": datetime.now().isoformat(timespec="seconds"), "post_label": post_label,
               "post_url": post_url, "instance": instance_index, "slot": session["slot"] + 1,
               "session": session["id"], "load_in_session": load_number,
               "capture_engine": session["capture_engine"], "local_ip": session["local_ip"],
               "browser": config.BROWSER, "capture_root_pid": session["capture_root_pid"],
               "circuit_path": session.get("circuit_path", "")}
    instance_capture = capture.InstanceCapture(partial_path)

    def abort_check(seconds_on_page):
        if _stop_requested.is_set():
            return "stopped by user"
        if seconds_on_page >= config.CAPTURE_HEALTH_CHECK_SECONDS and not instance_capture.packets_seen():
            return f"capture recorded nothing after {config.CAPTURE_HEALTH_CHECK_SECONDS}s"
        if tor_session is not None and seconds_on_page > 5 and not session.get("circuit_path"):
            # Proof of the circuit carrying this session (guard > middle > exit).
            session["circuit_path"] = tor_session.circuit_path_for(X_HOST_FRAGMENTS) or "-"
            log_row["circuit_path"] = session["circuit_path"]
            report(f"circuit: {session['circuit_path']}")
        return None

    post_result = twitter.PostResult()
    instance_capture.start(session["capture_root_pid"])
    capture_start_epoch = time.time()
    try:
        # First load of a session: browse to the post (profile -> wait,
        # scroll -> click) or open it directly; later loads: F5 on the post.
        if load_number > 0:
            navigation = browsing.NavigationResult(navigation="refresh")
        elif config.NAVIGATION == "browse":
            navigation = browsing.browse_to_post(web_driver, post_url, report, abort_check)
        else:
            navigation = browsing.NavigationResult(navigation="direct")
        if not navigation.opened:
            navigation.click_epoch = time.time()
            if navigation.navigation == "direct-fallback":
                report("browsing: opening the post link directly (fallback)")
        log_row.update({
            "navigation": navigation.navigation, "entry_url": navigation.entry_url,
            "dwell_s": navigation.dwell_seconds, "click_epoch": f"{navigation.click_epoch:.3f}",
            "click_offset_s": round(navigation.click_epoch - capture_start_epoch, 3),
        })
        post_result = twitter.load_post(web_driver, post_url, report, abort_check, reload=load_number > 0,
                                        already_open=navigation.opened)
        if not post_result.completed and post_result.reason != "stopped by user":
            snapshot = _policy.save_snapshot(web_driver, f"{instance_name(post_label, instance_index)}"
                                             f"_s{session['id']}_load{load_number}", post_result.reason)
            if snapshot:
                report(f"evidence saved: {os.path.relpath(snapshot, config.PROJECT_DIR)}.png/.txt")
        time.sleep(config.POST_LOAD_WAIT_SECONDS)
    except (WebDriverException, RuntimeError, OSError, ValueError, stem.ControllerError) as load_error:
        error_message = getattr(load_error, "msg", None) or str(load_error)
        post_result.reason = f"{type(load_error).__name__}: {' '.join(error_message.split())[:200]}"
    finally:
        capture_summary = instance_capture.stop()

    kept = post_result.completed and capture_summary.packets >= config.MIN_PACKETS
    if post_result.completed and not kept:
        post_result.reason = f"capture too small: {capture_summary.packets} packets (< MIN_PACKETS)"
    if kept:
        os.replace(partial_path, final_path)
    elif os.path.exists(partial_path):
        os.remove(partial_path)
    with _progress_lock:
        if kept:
            _progress["kept"] += 1
        kept_so_far, target = _progress["kept"], _progress["target"]
    _policy.record(kept, post_result.reason)

    log_row.update({
        "status": "OK" if kept else "FAILED", "reason": post_result.reason,
        "has_video": post_result.has_video, "video_duration_s": post_result.video_duration_seconds,
        "played_until_s": post_result.played_until_seconds, "load_s": post_result.load_seconds,
        "wall_time_s": post_result.wall_seconds, "rebuffer_events": post_result.rebuffer_events,
        "packets": capture_summary.packets, "wire_bytes": capture_summary.wire_bytes,
        "connections": instance_capture.connection_count,
        "file": os.path.relpath(final_path, config.DATA_RAW_DIR) if kept else "",
    })
    append_log_row(log_row)
    if kept:
        report(f"OK  {capture_summary.packets:,} packets, {capture_summary.wire_bytes / 1e6:.1f} MB "
               f"-> {os.path.basename(final_path)}   [successful: {kept_so_far}/{target}]")
    else:
        report(f"FAILED: {post_result.reason}  (packets: {capture_summary.packets})")
    return kept, post_result.reason


def run_session(slot_index, tor_session, capture_engine, capture_interface, post_label, post_url,
                instance_indices, session_id):
    """One browser session: new circuit + fresh browser, the post loaded once
    and then refreshed, one capture per load. Ends early (and the caller
    starts a new session) as soon as a load fails. Returns the instance
    numbers NOT captured, to be done in a later session."""
    session = {"slot": slot_index, "id": session_id, "tor_session": tor_session,
               "capture_engine": capture_engine, "local_ip": capture_interface.ip_address}
    prefix = f"[slot {slot_index + 1} | session {session_id}]"
    web_driver = None
    remaining = list(instance_indices)
    try:
        if tor_session is not None:
            # New circuit BEFORE the browser starts: NEWNYM affects new
            # connections only.
            say(prefix, f"new Tor circuit, Tor Browser: {post_label} x {len(remaining)} loads "
                        f"(1 + {len(remaining) - 1} refreshes)")
            tor_session.new_circuit()
        else:
            say(prefix, f"private Firefox (no Tor): {post_label} x {len(remaining)} loads")
        web_driver, geckodriver_pid = browser.open_browser(tor_session)
        # Tor mode: all of this slot's traffic leaves through its own tor.exe,
        # so captures follow tor.exe's connections to the Tor network.
        session["capture_root_pid"] = tor_session.tor_pid if tor_session is not None else geckodriver_pid
        time.sleep(config.BROWSER_SETTLE_SECONDS)
        for load_number, instance_index in enumerate(list(remaining)):
            if _stop_requested.is_set():
                break
            kept, reason = _capture_one_load(session, web_driver, post_label, post_url, instance_index, load_number)
            if not kept:
                if reason != "stopped by user":
                    say(prefix, "load failed - ending this session; a new session starts on a new circuit")
                break
            remaining.remove(instance_index)
    except (WebDriverException, RuntimeError, OSError, ValueError, stem.ControllerError) as session_error:
        error_message = getattr(session_error, "msg", None) or str(session_error)
        reason = f"{type(session_error).__name__}: {' '.join(error_message.split())[:200]}"
        say(prefix, f"FAILED to start: {reason}")
        _policy.record(False, reason)
        append_log_row({"timestamp": datetime.now().isoformat(timespec="seconds"), "post_label": post_label,
                        "post_url": post_url, "instance": remaining[0] if remaining else "",
                        "slot": slot_index + 1, "session": session_id, "status": "FAILED",
                        "reason": reason, "browser": config.BROWSER})
    finally:
        if web_driver is not None:
            browser.close_browser(web_driver)
    return remaining


_session_counter = itertools.count(1)


def _slot_worker(slot_index, job_queue, capture_engine, capture_interface):
    slot_prefix = f"[slot {slot_index + 1}]"
    time.sleep(slot_index * config.SLOT_START_STAGGER_SECONDS)
    if _stop_requested.is_set():
        return
    tor_session = None
    if config.BROWSER == "tor_browser":
        tor_session = TorSession(slot_index, report=lambda message: say(slot_prefix, message))
    try:
        if tor_session is not None:
            tor_session.start()
        while not _stop_requested.is_set():
            _policy.wait_if_cooling_down()
            try:
                post_label, post_url, instance_indices = job_queue.get_nowait()
            except queue.Empty:
                return
            if tor_session is not None and not tor_session.is_alive():
                say(slot_prefix, "tor connection lost - restarting this slot's tor")
                tor_session.close()
                tor_session.start()
            remaining = run_session(slot_index, tor_session, capture_engine, capture_interface,
                                    post_label, post_url, instance_indices, next(_session_counter))
            if remaining:
                job_queue.put((post_label, post_url, remaining))   # restart them in a new session
            time.sleep(random.uniform(*config.INTER_INSTANCE_DELAY_RANGE))
    except (RuntimeError, OSError, TimeoutError, stem.ControllerError) as slot_error:
        say(slot_prefix, f"[ERROR] slot stopped: {type(slot_error).__name__}: {slot_error}")
    finally:
        if tor_session is not None:
            tor_session.close()


def run_collection(instances_per_post=None, only_first_post=False):
    instances_per_post = instances_per_post or config.INSTANCES_PER_POST
    validate_post_settings()
    posts = list(config.TWITTER_POSTS.items())[:1] if only_first_post else list(config.TWITTER_POSTS.items())
    _stop_requested.clear()

    # Jobs = browser sessions of (1 + REFRESHES_PER_SESSION) loads of one
    # post; posts are interleaved (post1, post2, post1, ...).
    loads_per_session = 1 + max(0, config.REFRESHES_PER_SESSION)
    pending_per_post = {}
    already_done = 0
    for post_label, post_url in posts:
        pending_per_post[post_label] = []
        for instance_index in range(instances_per_post):
            if os.path.exists(instance_path(post_label, instance_index)):
                already_done += 1
            else:
                pending_per_post[post_label].append(instance_index)
    job_queue = queue.Queue()
    post_urls = dict(posts)
    while any(pending_per_post.values()):
        for post_label in pending_per_post:
            chunk = pending_per_post[post_label][:loads_per_session]
            if chunk:
                job_queue.put((post_label, post_urls[post_label], chunk))
                del pending_per_post[post_label][:loads_per_session]
    target = instances_per_post * len(posts)
    slot_count = max(1, min(config.PARALLEL_INSTANCES, job_queue.qsize()))
    with _progress_lock:
        _progress.update(kept=already_done, target=target)
    global _policy
    _policy = failure_policy.FailurePolicy(_stop_requested, report=lambda message: say("[all slots]", message))

    capture_interface = capture.resolve_capture_interface()
    print("=" * 76)
    print(f"  Posts      : {len(posts)}  x  {instances_per_post} successful captures each "
          f"({already_done}/{target} already done)")
    print(f"  Sessions   : each browser loads the post once + {config.REFRESHES_PER_SESSION} refreshes "
          f"= {loads_per_session} captures per circuit")
    if config.NAVIGATION == "browse":
        print(f"  Browsing   : first load via the poster's profile -> {config.BROWSE_DWELL_SECONDS[0]}-"
              f"{config.BROWSE_DWELL_SECONDS[1]} s, scroll -> click the post (click time logged)")
    else:
        print("  Browsing   : off - post links opened directly")
    browser_description = ("Tor Browser windows, each slot with its own tor.exe and a new circuit per instance"
                           if config.BROWSER == "tor_browser" else "private Firefox windows (direct, no Tor)")
    print(f"  Parallel   : {slot_count} {browser_description} ({config.BROWSER_WINDOW})")
    capture_engine = capture.choose_working_engine(capture_interface, report=lambda m: print(f"  {m}"))
    print(f"  Capture    : {capture_engine} on {capture_interface.description} ({capture_interface.ip_address})")
    print("=" * 76)
    if job_queue.empty():
        print("  Nothing to do - all captures already exist.")
        capture.stop_capture_engine()
        return

    slot_threads = [threading.Thread(target=_slot_worker, daemon=True,
                                     args=(slot_index, job_queue, capture_engine, capture_interface))
                    for slot_index in range(slot_count)]
    for slot_thread in slot_threads:
        slot_thread.start()
    try:
        while any(slot_thread.is_alive() for slot_thread in slot_threads):
            for slot_thread in slot_threads:
                slot_thread.join(timeout=0.5)
    except KeyboardInterrupt:
        print("\n  Ctrl+C - stopping all slots (closing browsers, writing captures)...")
        _stop_requested.set()
        for slot_thread in slot_threads:
            slot_thread.join(timeout=60)
        raise
    finally:
        capture.stop_capture_engine()

    with _progress_lock:
        kept = _progress["kept"]
    print("=" * 76)
    print(f"  Successful captures: {kept}/{target}")
    if kept < target:
        print("  Not finished - run again to continue from where it stopped.")
    print(f"  Captures: {config.DATA_RAW_DIR}")
    print(f"  Log     : {config.COLLECTION_LOG_PATH}")
    print("=" * 76)


def show_status():
    print(f"\n  Captures in {config.DATA_RAW_DIR}:")
    for post_label in config.TWITTER_POSTS:
        files = [f for f in glob.glob(os.path.join(config.DATA_RAW_DIR, post_label, "*.pcap"))
                 if ".partial." not in f]
        print(f"    {post_label:<20} {len(files)}/{config.INSTANCES_PER_POST}")
    if not os.path.exists(config.COLLECTION_LOG_PATH):
        return
    with open(config.COLLECTION_LOG_PATH, newline="", encoding="utf-8") as log_file:
        log_rows = list(csv.DictReader(log_file))
    status_counts = Counter(row.get("status", "") for row in log_rows)
    failure_reasons = Counter((row.get("reason") or "").split(":")[0] for row in log_rows if row.get("status") != "OK")
    print(f"\n  Attempts logged: {len(log_rows)}  (OK {status_counts.get('OK', 0)}, "
          f"FAILED {status_counts.get('FAILED', 0)})")
    for reason, count in failure_reasons.most_common(8):
        print(f"    {count:4d} x {reason}")
    print("\n  Last 8 attempts:")
    for row in log_rows[-8:]:
        print(f"    {row['timestamp']}  {row['post_label']} #{row['instance']} slot {row['slot']} "
              f"session {row.get('session', '')} load {row.get('load_in_session', '')}  {row['status']:<6} "
              f"{row['packets']} pkts  {row['reason'][:45]}")
