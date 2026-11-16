"""
File: failure_policy.py
Purpose:
    Decides what a failed attempt means for the whole run, and keeps evidence.

    Two kinds of failure:
      - SITE REFUSAL: the site answered, but would not serve the content
        ("not a bot", Google "unusual traffic", login wall, post not shown,
        YouTube player errors, playback too slow). Expected in bursts -
        never a reason to stop. After REFUSALS_BEFORE_COOLDOWN of them in a
        row (all slots together) every slot pauses for a cool-down (5 min,
        doubling up to COOLDOWN_MINUTES_MAX), then continues. Only after
        MAX_COOLDOWNS_IN_A_ROW cool-downs without a single success does the
        run stop.
      - TECHNICAL: the tool itself is not working (capture records nothing,
        browser does not start, connection errors). MAX_CONSECUTIVE_FAILURES
        of these in a row stop the run at once - retrying cannot help.

    Evidence: for the first DEBUG_SNAPSHOTS_PER_REASON failures of each kind,
    a screenshot and the page text are saved to data/debug/, so the reason
    for a failure can be seen instead of guessed.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import os
import re
import threading
import time
from collections import Counter

import config

SITE_REFUSAL_MARKERS = (
    "blocked", "player error", "login", "post did not appear", "player did not appear",
    "resume failed", "too slow", "stalled", "not fully loaded", "something went wrong",
    "navigated to another video", "video disappeared", "live stream",
)

PAGE_TEXT_SCRIPT = "return location.href + '\\n\\n' + (document.body ? document.body.innerText : '');"


def is_site_refusal(reason):
    reason_lower = (reason or "").lower()
    return any(marker in reason_lower for marker in SITE_REFUSAL_MARKERS)


def reason_key(reason):
    """Short file-name-safe key of a failure reason (for debug snapshots)."""
    head = (reason or "unknown").split("(")[0].split("[")[0][:40]
    return re.sub(r"[^A-Za-z0-9]+", "-", head).strip("-").lower() or "unknown"


class FailurePolicy:
    def __init__(self, stop_event, report=print):
        self.stop_event = stop_event
        self.report = report
        self._lock = threading.Lock()
        self.consecutive_technical = 0
        self.consecutive_refusals = 0
        self.cooldowns_in_a_row = 0
        self.cooldown_until = 0.0
        self.snapshots_per_reason = Counter()

    def record(self, kept, reason):
        if reason == "stopped by user":
            return
        with self._lock:
            if kept:
                self.consecutive_technical = self.consecutive_refusals = self.cooldowns_in_a_row = 0
                return
            if is_site_refusal(reason):
                self.consecutive_technical = 0
                self.consecutive_refusals += 1
                if not getattr(config, "COOLDOWN_ENABLED", True):
                    # No pausing: the caller restarts at once with a new
                    # session; stop only if the site refuses everything.
                    if self.consecutive_refusals >= config.MAX_REFUSALS_WITHOUT_SUCCESS:
                        self.report(f"[STOP] {config.MAX_REFUSALS_WITHOUT_SUCCESS} refusals in a row without a "
                                    "single success - the site refuses everything. See data/debug. Stopping.")
                        self.stop_event.set()
                    return
                if self.consecutive_refusals >= config.REFUSALS_BEFORE_COOLDOWN and time.time() >= self.cooldown_until:
                    self.cooldowns_in_a_row += 1
                    self.consecutive_refusals = 0
                    if self.cooldowns_in_a_row > config.MAX_COOLDOWNS_IN_A_ROW:
                        self.report(f"[STOP] {config.MAX_COOLDOWNS_IN_A_ROW} cool-downs in a row without a single "
                                    "success - the site keeps refusing. See data/debug and the log. Stopping.")
                        self.stop_event.set()
                        return
                    minutes = min(config.COOLDOWN_MINUTES_START * 2 ** (self.cooldowns_in_a_row - 1),
                                  config.COOLDOWN_MINUTES_MAX)
                    self.cooldown_until = time.time() + minutes * 60
                    self.report(f"[PAUSE] {config.REFUSALS_BEFORE_COOLDOWN} refusals in a row (last: {reason[:60]}) - "
                                f"all slots pause {minutes} min, then continue "
                                f"(cool-down {self.cooldowns_in_a_row}/{config.MAX_COOLDOWNS_IN_A_ROW})")
            else:
                self.consecutive_technical += 1
                if self.consecutive_technical >= config.MAX_CONSECUTIVE_FAILURES:
                    self.report(f"[STOP] {config.MAX_CONSECUTIVE_FAILURES} technical failures in a row "
                                f"(last: {reason[:80]}) - retrying cannot help. Stopping.")
                    self.stop_event.set()

    def wait_if_cooling_down(self):
        while not self.stop_event.is_set():
            with self._lock:
                remaining = self.cooldown_until - time.time()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 5))

    def save_snapshot(self, web_driver, instance_label, reason):
        """Screenshot + page text of a failed attempt (first few per reason)."""
        key = reason_key(reason)
        with self._lock:
            if self.snapshots_per_reason[key] >= config.DEBUG_SNAPSHOTS_PER_REASON:
                return None
            self.snapshots_per_reason[key] += 1
        debug_dir = os.path.join(os.path.dirname(config.DATA_RAW_DIR), "debug")
        os.makedirs(debug_dir, exist_ok=True)
        base_path = os.path.join(debug_dir, f"{key}__{instance_label}")
        try:
            web_driver.save_screenshot(base_path + ".png")
            page_text = web_driver.execute_script(PAGE_TEXT_SCRIPT) or ""
        except Exception as snapshot_error:  # browser may already be broken; evidence is optional
            page_text = f"(could not read page: {snapshot_error})"
        with open(base_path + ".txt", "w", encoding="utf-8") as text_file:
            text_file.write(f"reason: {reason}\n\n{page_text[:20000]}")
        return base_path
