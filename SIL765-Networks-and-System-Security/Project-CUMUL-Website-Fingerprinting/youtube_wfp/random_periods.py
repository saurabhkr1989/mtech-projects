"""
File: random_periods.py
Purpose:
    Gives the run a natural, irregular rhythm instead of a constant five
    browsers: the whole operation is divided into periods of random length
    (PERIOD_MINUTES_RANGE), and in each period a random number of browsers
    (PARALLEL_RANGE, never more than PARALLEL_INSTANCES = 5) may play videos
    at the same time.

    How it works: a scheduler thread draws a new (duration, number of
    browsers) pair at the start of every period. A slot asks for a permit
    before every attempt and returns it afterwards; at most "number of
    browsers" permits are out at once. When a period with fewer browsers
    begins, videos already playing finish normally - the extra slots simply
    wait for the next permit, so no capture is ever cut short.

    All five slots keep their tor.exe running throughout (an idle tor sends
    only occasional keep-alive cells), so a slot can start immediately when
    a later period allows more browsers.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-13
"""

import random
import threading
import time

import config


class RandomPeriodScheduler:
    def __init__(self, stop_event, slot_count, report=print):
        self.stop_event = stop_event
        self.slot_count = slot_count
        self.report = report
        self._condition = threading.Condition()
        self.allowed = slot_count
        self.active = 0
        self.period_number = 0
        self.period_ends_at = 0.0
        self._thread = None

    # ----------------------------------------------------------- scheduling
    def _parallel_range(self):
        lowest, highest = config.PARALLEL_RANGE
        highest = min(highest, self.slot_count)
        lowest = max(1, min(lowest, highest))
        return lowest, highest

    def _start_next_period(self):
        lowest, highest = self._parallel_range()
        minutes = random.uniform(*config.PERIOD_MINUTES_RANGE)
        with self._condition:
            self.period_number += 1
            self.allowed = random.randint(lowest, highest)
            self.period_ends_at = time.time() + minutes * 60
            self._condition.notify_all()
        self.report(f"[period {self.period_number}] {self.allowed} browser(s) in parallel for "
                    f"{minutes:.0f} min (until {time.strftime('%H:%M', time.localtime(self.period_ends_at))})")

    def _run(self):
        while not self.stop_event.is_set():
            self._start_next_period()
            while not self.stop_event.is_set() and time.time() < self.period_ends_at:
                time.sleep(1)
        with self._condition:
            self._condition.notify_all()

    def start(self):
        if not config.RANDOM_PERIODS_ENABLED:
            self.allowed = self.slot_count
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # -------------------------------------------------------------- permits
    def acquire(self):
        """Block until this slot may start an attempt. Returns
        (period number, browsers allowed in the period), or None if the run
        is stopping."""
        with self._condition:
            while not self.stop_event.is_set() and self.active >= self.allowed:
                self._condition.wait(timeout=1)
            if self.stop_event.is_set():
                return None
            self.active += 1
            return self.period_number, self.allowed

    def release(self):
        with self._condition:
            self.active = max(0, self.active - 1)
            self._condition.notify_all()
