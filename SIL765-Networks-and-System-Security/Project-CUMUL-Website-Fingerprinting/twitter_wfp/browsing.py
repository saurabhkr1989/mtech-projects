"""
File: browsing.py
Purpose:
    Browsing mode (config.NAVIGATION = "browse"): reach the post the way a
    person does instead of opening its link directly -

        poster's profile  ->  stay a random time, scroll  ->  click the post

    Why: X is a single-page app. Clicking a post on a profile does NOT
    reload the site; only the post's data and media are fetched, because the
    site's scripts and styles came with the profile page. A trace that starts
    by opening the post link directly begins instead with a full site load.

    The click is made on the post's timestamp link (it points to
    /status/<post id>), which is what opens a post on X. The click time is
    logged (epoch, and seconds after the capture start), so a trace can be
    used whole or cut at the click.

    X shows logged-out visitors only part of a profile; replies are not on
    the main profile tab at all. If the post is not found after scrolling,
    its link is opened directly and the log says "direct-fallback".

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-14
"""

import random
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from selenium.common.exceptions import (ElementClickInterceptedException, ElementNotInteractableException,
                                        JavascriptException, NoSuchElementException,
                                        StaleElementReferenceException, TimeoutException, WebDriverException)
from selenium.webdriver.common.by import By

import config
import twitter

CLICK_NAVIGATION_TIMEOUT = 20
PROFILE_READY_TIMEOUT = 45

COUNT_POST_LINKS_SCRIPT = r"""
return document.querySelectorAll('a[href*="/status/"] time').length;
"""


@dataclass
class NavigationResult:
    opened: bool = False
    navigation: str = ""          # profile | direct | direct-fallback | refresh
    entry_url: str = ""
    dwell_seconds: float = 0.0
    click_epoch: float = 0.0
    notes: list = field(default_factory=list)


def profile_url(post_url):
    """https://x.com/<user> for https://x.com/<user>/status/<id>."""
    user_name = urlparse(post_url).path.strip("/").split("/")[0]
    return f"https://x.com/{user_name}"


def _random_dwell(web_driver, abort_check, started_at):
    dwell_seconds = random.uniform(*config.BROWSE_DWELL_SECONDS)
    scroll_count = random.randint(*config.BROWSE_SCROLLS)
    started_dwell = time.monotonic()
    scroll_times = sorted(random.uniform(0, dwell_seconds) for _ in range(scroll_count))
    while time.monotonic() - started_dwell < dwell_seconds:
        if abort_check(time.monotonic() - started_at):
            break
        web_driver.execute_script(twitter.DISMISS_OVERLAYS_SCRIPT, None)
        if scroll_times and time.monotonic() - started_dwell >= scroll_times[0]:
            scroll_times.pop(0)
            web_driver.execute_script("window.scrollBy({top: arguments[0], behavior: 'smooth'});",
                                      random.randint(250, 900))
        time.sleep(0.5)
    return round(dwell_seconds, 1)


def _find_post_link(web_driver, post_id, max_scrolls):
    """The post's timestamp link on the profile, scrolling further if needed."""
    for _scroll in range(max_scrolls + 1):
        for element in web_driver.find_elements(By.CSS_SELECTOR, f'a[href*="/status/{post_id}"]'):
            try:
                href = element.get_attribute("href") or ""
                if "/photo/" in href or "/analytics" in href or "/video/" in href:
                    continue
                if element.find_elements(By.CSS_SELECTOR, "time") and element.is_displayed():
                    return element
            except StaleElementReferenceException:
                continue
        web_driver.execute_script("window.scrollBy(0, Math.max(800, window.innerHeight));")
        time.sleep(random.uniform(1.5, 2.5))
    return None


def _click(web_driver, element):
    web_driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
    time.sleep(random.uniform(0.6, 1.6))
    try:
        element.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        # A sign-up banner covers the link: a click dispatched on the link
        # itself follows the same in-page route.
        web_driver.execute_script("arguments[0].click();", element)


def _wait_for_post_address(web_driver, post_id):
    deadline = time.monotonic() + CLICK_NAVIGATION_TIMEOUT
    while time.monotonic() < deadline:
        try:
            if twitter.extract_post_id(web_driver.current_url) == post_id:
                return True
        except WebDriverException:
            pass  # page in the middle of changing; try again
        time.sleep(0.3)
    return False


def browse_to_post(web_driver, post_url, report=print, abort_check=lambda seconds: None):
    """Profile -> dwell/scroll -> click the post. With result.opened False the
    caller opens the link itself (direct-fallback)."""
    result = NavigationResult(navigation="direct-fallback")
    started_at = time.monotonic()
    post_id = twitter.extract_post_id(post_url)
    entry_url = profile_url(post_url)
    report(f"browsing: profile {entry_url}")
    web_driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
    try:
        web_driver.get(entry_url)
    except TimeoutException:
        report("profile load event not reached - continuing with what is shown")

    deadline = time.monotonic() + PROFILE_READY_TIMEOUT
    while time.monotonic() < deadline:
        if abort_check(time.monotonic() - started_at):
            return result
        web_driver.execute_script(twitter.DISMISS_OVERLAYS_SCRIPT, None)
        if web_driver.execute_script(COUNT_POST_LINKS_SCRIPT) > 0:
            break
        time.sleep(1)
    else:
        result.notes.append("profile showed no posts (login wall or error)")
        report(f"browsing: {result.notes[-1]}")
        return result

    result.dwell_seconds = _random_dwell(web_driver, abort_check, started_at)
    link = _find_post_link(web_driver, post_id, config.BROWSE_MAX_SEARCH_SCROLLS)
    if link is None:
        result.notes.append("post not found on the profile (replies and older posts may not be shown)")
        report(f"browsing: {result.notes[-1]}")
        return result
    try:
        result.click_epoch = time.time()
        _click(web_driver, link)
    except (StaleElementReferenceException, NoSuchElementException, JavascriptException) as click_error:
        result.notes.append(f"click failed ({type(click_error).__name__})")
        return result
    if not _wait_for_post_address(web_driver, post_id):
        result.notes.append("click did not open the post")
        return result
    result.opened, result.navigation, result.entry_url = True, "profile", entry_url
    report(f"clicked the post after {result.dwell_seconds:.0f}s on the profile")
    return result
