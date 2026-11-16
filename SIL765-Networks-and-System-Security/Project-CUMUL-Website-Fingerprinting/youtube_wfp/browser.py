"""
File: browser.py
Purpose:
    Launches / closes the browser of one slot, routed through that slot's tor.

    BROWSER = "tor_browser": the real Tor Browser (firefox.exe of the bundle)
    driven by geckodriver. Tor Browser is told NOT to start its own tor and
    to use the slot's tor instead (environment variables + prefs).
    BROWSER = "chrome_tor": Chrome with the slot's tor as SOCKS5 proxy
    (version 1 method).

Design decision: a NEW browser (fresh temporary profile) per instance, so
every instance downloads the whole video with an empty cache, as a
first-time viewer would.

Non-obvious (seen on the first test run): Firefox on Windows sometimes
restarts itself during the first start of a copied profile. The process
geckodriver launched exits with status 0, Selenium reports "Process
unexpectedly closed", and the restarted window stays open with nobody
controlling it. Launches are therefore serialised with a lock, and any
geckodriver-profile firefox.exe that appeared during a failed launch is
killed; after every instance the browser's own processes are killed too.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import os
import shutil
import subprocess
import threading
import time

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService

import config

# One browser launch at a time across all slots (see module docstring).
_BROWSER_LAUNCH_LOCK = threading.Lock()

# Window position far outside any desktop (Windows' own "hidden" coordinate).
OFFSCREEN_POSITION = -32000

# geckodriver always creates its temporary profiles under this name.
GECKODRIVER_PROFILE_MARKER = "rust_mozprofile"


BROWSER_WINDOW_MODES = ("behind", "offscreen", "headless", "visible")

# Win32 constants for SetWindowPos
HWND_BOTTOM = 1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
# Seconds to wait for the new browser window to become visible after launch.
NEW_WINDOW_WAIT_SECONDS = 5


# ------------------------------------------------------ window placement (Win32)
def _user32():
    """user32 with explicit signatures: on 64-bit Python the ctypes default
    (int) can truncate window handles."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    return user32


def _visible_top_level_windows():
    """Set of handles of all visible top-level windows on the desktop."""
    if os.name != "nt":
        return set()
    import ctypes
    from ctypes import wintypes
    user32 = _user32()
    window_handles = set()
    enum_callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def remember_window(window_handle, _unused):
        if user32.IsWindowVisible(window_handle):
            window_handles.add(window_handle)
        return True

    user32.EnumWindows(enum_callback_type(remember_window), 0)
    return window_handles


def _push_new_windows_behind(windows_before_launch, previous_foreground_window):
    """Send the browser's new window(s) to the bottom of the window stack
    and give the keyboard focus back to the window the user was working in.

    The new windows are found as "visible windows that did not exist before
    the launch" - safe because launches are serialised by the launch lock.
    """
    if os.name != "nt":
        return
    import ctypes
    user32 = _user32()
    kernel32 = ctypes.windll.kernel32
    deadline = time.monotonic() + NEW_WINDOW_WAIT_SECONDS
    new_windows = set()
    while time.monotonic() < deadline and not new_windows:
        new_windows = _visible_top_level_windows() - windows_before_launch
        if not new_windows:
            time.sleep(0.2)
    for window_handle in new_windows:
        user32.SetWindowPos(window_handle, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)

    if previous_foreground_window and user32.IsWindow(previous_foreground_window):
        # Windows only lets the foreground thread hand focus to another
        # window; attaching our input queue to it briefly makes the
        # SetForegroundWindow call allowed.
        foreground_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        this_thread = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(this_thread, foreground_thread, True)
        user32.SetForegroundWindow(previous_foreground_window)
        user32.AttachThreadInput(this_thread, foreground_thread, False)


# ----------------------------------------------------------- process cleanup
def _geckodriver_firefox_processes():
    """{pid: command line} of firefox.exe main processes using a geckodriver
    temporary profile (never the user's own Tor Browser)."""
    if os.name != "nt":
        return {}
    powershell_query = ("Get-CimInstance Win32_Process -Filter \"Name='firefox.exe'\" | "
                        "ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }")
    try:
        query_output = subprocess.run(["powershell", "-NoProfile", "-Command", powershell_query],
                                      capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    processes = {}
    for line in query_output.splitlines():
        pid_text, _, command_line = line.partition("|")
        if pid_text.strip().isdigit() and GECKODRIVER_PROFILE_MARKER in command_line \
                and "-contentproc" not in command_line:
            processes[int(pid_text)] = command_line
    return processes


def _kill_process_tree(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


# ---------------------------------------------------------------- Tor Browser
def _tor_browser_preferences(tor_session):
    preferences = {
        # Start on a blank page; skip the "Connect to Tor" screen.
        "browser.startup.page": 0,
        "browser.startup.homepage": "about:blank",
        "torbrowser.settings.quickstart.enabled": True,
        # Do not launch the bundled tor; use the slot's tor.
        "extensions.torlauncher.start_tor": False,
        "extensions.torlauncher.prompt_at_startup": False,
        "extensions.torlauncher.control_port": tor_session.control_port,
        "network.proxy.type": 1,
        "network.proxy.socks": "127.0.0.1",
        "network.proxy.socks_port": tor_session.socks_port,
        "network.proxy.socks_remote_dns": True,
        "extensions.torbutton.socks_port": tor_session.socks_port,
        # Security level "Standard" (4); "Safer"/"Safest" stop YouTube playing.
        "browser.security_level.security_slider": 4,
        # 0 = allow autoplay; Tor Browser blocks it by default and the video
        # would sit paused at 0:00 waiting for a click.
        "media.autoplay.default": 0,
        "media.autoplay.blocking_policy": 0,
        # Firefox stops decoding video in windows it thinks nobody sees
        # (behind other windows, off-screen, headless); keep it decoding so
        # the player keeps requesting video exactly as for a viewer.
        "media.suspend-bkgnd-video.enabled": False,
        # Windows-only: Firefox treats a window fully covered by other
        # windows like a minimised one (throttled). The "behind" mode puts
        # it exactly there, so occlusion tracking is switched off.
        "widget.windows.window_occlusion_tracking.enabled": False,
        # No update checks / language prompts during capture.
        "app.update.auto": False,
        "app.update.enabled": False,
        "extensions.torbutton.prompted_language": True,
        "intl.language_notification.shown": True,
    }
    if config.MUTE_AUDIO:
        # Browser-wide volume 0: silent from the very first frame, before the
        # page script gets a chance to mute the player.
        preferences["media.volume_scale"] = "0.0"
    return preferences


def _tor_browser_environment(tor_session):
    """TOR_SKIP_LAUNCH=1 tells Tor Browser tor is already running. Since Tor
    Browser 13 the control port must also be reachable or the SOCKS
    settings are ignored (Tor Project issue #42160), so it is passed too."""
    environment = dict(os.environ)
    environment.update({
        "TOR_SKIP_LAUNCH": "1",
        "TOR_SOCKS_HOST": "127.0.0.1",
        "TOR_SOCKS_PORT": str(tor_session.socks_port),
        "TOR_CONTROL_HOST": "127.0.0.1",
        "TOR_CONTROL_PORT": str(tor_session.control_port),
    })
    if tor_session.control_cookie_path:
        environment["TOR_CONTROL_COOKIE_AUTH_FILE"] = tor_session.control_cookie_path
    return environment


def _open_tor_browser(tor_session):
    if not os.path.exists(config.TBB_FIREFOX_EXE):
        raise FileNotFoundError(f"Tor Browser not found at {config.TBB_FIREFOX_EXE} (check TBB_DIR in config.py)")
    browser_options = FirefoxOptions()
    browser_options.binary_location = config.TBB_FIREFOX_EXE
    # FirefoxProfile copies profile.default to a temporary folder (lock files
    # excluded): the bundle's own profile is never modified, each instance
    # starts with an empty cache, and NoScript etc. are carried over.
    browser_options.profile = FirefoxProfile(config.TBB_PROFILE_DIR)
    for preference_name, preference_value in _tor_browser_preferences(tor_session).items():
        browser_options.set_preference(preference_name, preference_value)
    window_width, window_height = config.BROWSER_WINDOW_SIZE
    if config.BROWSER_WINDOW == "headless":
        browser_options.add_argument("-headless")
    browser_options.add_argument(f"--width={window_width}")
    browser_options.add_argument(f"--height={window_height}")
    driver_service = FirefoxService(executable_path=config.GECKODRIVER_PATH,
                                    env=_tor_browser_environment(tor_session))
    web_driver = webdriver.Firefox(service=driver_service, options=browser_options)
    if config.BROWSER_WINDOW == "offscreen":
        _move_window_offscreen(web_driver)
    return web_driver


def _move_window_offscreen(web_driver):
    """Keep the window open (rendering and playback behave exactly as for a
    visible window) but place it outside the visible desktop."""
    window_width, window_height = config.BROWSER_WINDOW_SIZE
    web_driver.set_window_rect(x=OFFSCREEN_POSITION, y=OFFSCREEN_POSITION,
                               width=window_width, height=window_height)


# --------------------------------------------------------------------- Chrome
def _open_chrome_via_tor(tor_session):
    browser_options = ChromeOptions()
    browser_options.add_argument(f"--proxy-server=socks5://127.0.0.1:{tor_session.socks_port}")
    # Chromium's documented guard against DNS lookups leaking outside Tor.
    browser_options.add_argument("--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1")
    browser_options.add_argument("--autoplay-policy=no-user-gesture-required")
    if config.MUTE_AUDIO:
        browser_options.add_argument("--mute-audio")
    browser_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    window_width, window_height = config.BROWSER_WINDOW_SIZE
    browser_options.add_argument(f"--window-size={window_width},{window_height}")
    if config.BROWSER_WINDOW == "headless":
        browser_options.add_argument("--headless=new")
    elif config.BROWSER_WINDOW == "offscreen":
        browser_options.add_argument(f"--window-position={OFFSCREEN_POSITION},{OFFSCREEN_POSITION}")
    # Chrome otherwise slows down timers and media in windows it considers hidden.
    browser_options.add_argument("--disable-background-timer-throttling")
    browser_options.add_argument("--disable-renderer-backgrounding")
    browser_options.add_argument("--disable-backgrounding-occluded-windows")
    return webdriver.Chrome(service=ChromeService(executable_path=config.CHROMEDRIVER_PATH),
                            options=browser_options)


# ------------------------------------------------------------------ public API
def open_browser(tor_session):
    if config.BROWSER_WINDOW not in BROWSER_WINDOW_MODES:
        raise ValueError(f'config.BROWSER_WINDOW must be one of {BROWSER_WINDOW_MODES}, '
                         f'got "{config.BROWSER_WINDOW}"')
    if config.BROWSER not in ("tor_browser", "chrome_tor"):
        raise ValueError(f'config.BROWSER must be "tor_browser" or "chrome_tor", got "{config.BROWSER}"')
    with _BROWSER_LAUNCH_LOCK:
        keep_behind = config.BROWSER_WINDOW == "behind" and os.name == "nt"
        previous_foreground_window = _user32().GetForegroundWindow() if keep_behind else None
        windows_before_launch = _visible_top_level_windows() if keep_behind else set()
        if config.BROWSER == "chrome_tor":
            web_driver = _open_chrome_via_tor(tor_session)
        else:
            processes_before_launch = _geckodriver_firefox_processes()
            try:
                web_driver = _open_tor_browser(tor_session)
            except WebDriverException:
                # Kill the orphan window left by a self-restarting Firefox.
                for orphan_pid in set(_geckodriver_firefox_processes()) - set(processes_before_launch):
                    _kill_process_tree(orphan_pid)
                raise
        if keep_behind:
            _push_new_windows_behind(windows_before_launch, previous_foreground_window)
        return web_driver


def close_browser(web_driver):
    """Quit the browser and make sure none of its processes stay behind."""
    profile_path = (web_driver.capabilities or {}).get("moz:profile") or ""
    try:
        web_driver.quit()
    except WebDriverException:
        pass  # already gone; the process sweep below still runs
    if profile_path:
        for pid, command_line in _geckodriver_firefox_processes().items():
            if profile_path.lower() in command_line.lower():
                _kill_process_tree(pid)
        # Over 1000 instances, left-over temporary profiles (~16 MB each)
        # would fill the disk; geckodriver normally deletes it, this makes sure.
        shutil.rmtree(profile_path, ignore_errors=True)
