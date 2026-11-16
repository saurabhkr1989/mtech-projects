"""
File: browser.py
Purpose:
    Launches / closes the browser of one instance, with a fresh temporary
    profile every time (empty cache and cookies, a first-time logged-out
    visitor):
      BROWSER = "tor_browser"     : the bundled Tor Browser (always private),
                                    routed through the slot's own tor.exe
      BROWSER = "firefox_private" : the bundled Firefox ESR in permanent
                                    private-browsing mode, direct (no Tor)

    Network settings that matter for the capture:
      - HTTP/3 (QUIC over UDP) off: X and its media CDN would otherwise use
        UDP, which the TCP capture does not record; all traffic is TCP/TLS.
      - IPv6 off for DNS: connections go over IPv4, which the capture records.
      - background services off (telemetry, Safe Browsing, captive-portal and
        connectivity checks, prefetching, push): their connections belong to
        the same Firefox process and would otherwise mix into the trace.

Windows: launches are serialised (lock) so a new window can be identified
and sent behind the user's work; leftover processes are killed on close.

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
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService

import config

_BROWSER_LAUNCH_LOCK = threading.Lock()
GECKODRIVER_PROFILE_MARKER = "rust_mozprofile"
BROWSER_WINDOW_MODES = ("behind", "visible", "offscreen", "headless")
OFFSCREEN_POSITION = -32000
HWND_BOTTOM = 1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
NEW_WINDOW_WAIT_SECONDS = 5


def _firefox_preferences():
    preferences = {
        # Private window for the whole session.
        "browser.privatebrowsing.autostart": True,
        "browser.startup.page": 0,
        "browser.startup.homepage": "about:blank",
        # Capture-relevant network behaviour (see module docstring).
        "network.http.http3.enable": False,
        "network.dns.disableIPv6": True,
        "network.trr.mode": 5,
        "network.prefetch-next": False,
        "network.dns.disablePrefetch": True,
        "network.predictor.enabled": False,
        "network.http.speculative-parallel-limit": 0,
        "browser.urlbar.speculativeConnect.enabled": False,
        # Firefox's private-window tracking protection treats X's own
        # domains (api.x.com, twimg.com) as trackers; blocking them makes X
        # show an error instead of the post. Switched off for this browser.
        "privacy.trackingprotection.pbmode.enabled": False,
        "privacy.trackingprotection.enabled": False,
        "privacy.trackingprotection.socialtracking.enabled": False,
        # Background services off.
        "toolkit.telemetry.enabled": False,
        "datareporting.healthreport.uploadEnabled": False,
        "datareporting.policy.dataSubmissionEnabled": False,
        "app.normandy.enabled": False,
        "app.update.auto": False,
        "browser.safebrowsing.malware.enabled": False,
        "browser.safebrowsing.phishing.enabled": False,
        "browser.safebrowsing.downloads.enabled": False,
        "network.captive-portal-service.enabled": False,
        "network.connectivity-service.enabled": False,
        "dom.push.enabled": False,
        "extensions.update.enabled": False,
        "browser.region.update.enabled": False,
        "browser.newtabpage.enabled": False,
        "media.gmp-manager.updateEnabled": False,
        # Media: autoplay allowed, keep decoding when the window is hidden
        # or covered (the "behind" mode puts it under other windows).
        "media.autoplay.default": 0,
        "media.autoplay.blocking_policy": 0,
        "media.suspend-bkgnd-video.enabled": False,
        "widget.windows.window_occlusion_tracking.enabled": False,
    }
    if config.MUTE_AUDIO:
        preferences["media.volume_scale"] = "0.0"
    return preferences


# ------------------------------------------------------ window placement (Win32)
def _user32():
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
    """Send the new browser window(s) to the bottom of the window stack and
    hand the keyboard focus back to the window the user was working in."""
    import ctypes
    user32 = _user32()
    deadline = time.monotonic() + NEW_WINDOW_WAIT_SECONDS
    new_windows = set()
    while time.monotonic() < deadline and not new_windows:
        new_windows = _visible_top_level_windows() - windows_before_launch
        if not new_windows:
            time.sleep(0.2)
    for window_handle in new_windows:
        user32.SetWindowPos(window_handle, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
    if previous_foreground_window and user32.IsWindow(previous_foreground_window):
        foreground_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        this_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(this_thread, foreground_thread, True)
        user32.SetForegroundWindow(previous_foreground_window)
        user32.AttachThreadInput(this_thread, foreground_thread, False)


# ---------------------------------------------------------------- Tor Browser
def _tor_browser_preferences(tor_session):
    preferences = {
        # Start on a blank page; skip the "Connect to Tor" screen.
        "browser.startup.page": 0,
        "browser.startup.homepage": "about:blank",
        "torbrowser.settings.quickstart.enabled": True,
        # Do not launch the bundled tor; use the slot's own tor.exe.
        "extensions.torlauncher.start_tor": False,
        "extensions.torlauncher.prompt_at_startup": False,
        "extensions.torlauncher.control_port": tor_session.control_port,
        "network.proxy.type": 1,
        "network.proxy.socks": "127.0.0.1",
        "network.proxy.socks_port": tor_session.socks_port,
        "network.proxy.socks_remote_dns": True,
        "extensions.torbutton.socks_port": tor_session.socks_port,
        # Security level "Standard" (4): "Safer"/"Safest" disable JavaScript
        # features X needs to show posts and play videos.
        "browser.security_level.security_slider": 4,
        "media.autoplay.default": 0,
        "media.autoplay.blocking_policy": 0,
        "media.suspend-bkgnd-video.enabled": False,
        "widget.windows.window_occlusion_tracking.enabled": False,
        "app.update.auto": False,
        "app.update.enabled": False,
        "extensions.torbutton.prompted_language": True,
        "intl.language_notification.shown": True,
    }
    if config.MUTE_AUDIO:
        preferences["media.volume_scale"] = "0.0"
    return preferences


def _tor_browser_environment(tor_session):
    """TOR_SKIP_LAUNCH=1 tells Tor Browser tor is already running; since Tor
    Browser 13 the control port must also be given (Tor Project #42160)."""
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


def _browser_executable():
    return config.TBB_FIREFOX_EXE if config.BROWSER == "tor_browser" else config.FIREFOX_EXE


# ------------------------------------------------------------ process cleanup
def _our_firefox_processes():
    """{pid: command line} of firefox.exe main processes started by
    geckodriver from THIS package's Firefox (never the user's own Firefox
    or another app's Tor Browser)."""
    if os.name != "nt":
        return {}
    query = ("Get-CimInstance Win32_Process -Filter \"Name='firefox.exe'\" | "
             "ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }")
    try:
        output = subprocess.run(["powershell", "-NoProfile", "-Command", query],
                                capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    firefox_directory = os.path.dirname(_browser_executable()).lower()
    processes = {}
    for line in output.splitlines():
        pid_text, _, command_line = line.partition("|")
        lowered = command_line.lower()
        if pid_text.strip().isdigit() and GECKODRIVER_PROFILE_MARKER in lowered \
                and firefox_directory in lowered and "-contentproc" not in lowered:
            processes[int(pid_text)] = command_line
    return processes


def _kill_process_tree(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


# ------------------------------------------------------------------ public API
def open_browser(tor_session=None):
    """Launch the configured browser; returns (web_driver, geckodriver pid).
    Firefox and its child processes descend from the geckodriver process."""
    if config.BROWSER_WINDOW not in BROWSER_WINDOW_MODES:
        raise ValueError(f"config.BROWSER_WINDOW must be one of {BROWSER_WINDOW_MODES}")
    if config.BROWSER not in ("tor_browser", "firefox_private"):
        raise ValueError('config.BROWSER must be "tor_browser" or "firefox_private"')
    if not os.path.exists(_browser_executable()):
        raise FileNotFoundError(f"browser not found at {_browser_executable()}")

    browser_options = FirefoxOptions()
    browser_options.binary_location = _browser_executable()
    if config.BROWSER == "tor_browser":
        # FirefoxProfile copies the bundle's profile.default to a temporary
        # folder (NoScript etc. included); the bundle copy is never modified.
        browser_options.profile = FirefoxProfile(config.TBB_PROFILE_DIR)
        preferences = _tor_browser_preferences(tor_session)
        driver_environment = _tor_browser_environment(tor_session)
    else:
        preferences = _firefox_preferences()
        driver_environment = None
    for preference_name, preference_value in preferences.items():
        browser_options.set_preference(preference_name, preference_value)
    window_width, window_height = config.BROWSER_WINDOW_SIZE
    browser_options.add_argument(f"--width={window_width}")
    browser_options.add_argument(f"--height={window_height}")
    if config.BROWSER_WINDOW == "headless":
        browser_options.add_argument("-headless")

    with _BROWSER_LAUNCH_LOCK:
        keep_behind = config.BROWSER_WINDOW == "behind" and os.name == "nt"
        previous_foreground_window = _user32().GetForegroundWindow() if keep_behind else None
        windows_before_launch = _visible_top_level_windows() if keep_behind else set()
        processes_before_launch = _our_firefox_processes()
        driver_service = FirefoxService(executable_path=config.GECKODRIVER_PATH, env=driver_environment)
        try:
            web_driver = webdriver.Firefox(service=driver_service, options=browser_options)
        except WebDriverException:
            for orphan_pid in set(_our_firefox_processes()) - set(processes_before_launch):
                _kill_process_tree(orphan_pid)
            raise
        if config.BROWSER_WINDOW == "offscreen":
            web_driver.set_window_rect(x=OFFSCREEN_POSITION, y=OFFSCREEN_POSITION,
                                       width=window_width, height=window_height)
        if keep_behind:
            _push_new_windows_behind(windows_before_launch, previous_foreground_window)
    return web_driver, driver_service.process.pid


def close_browser(web_driver):
    profile_path = (web_driver.capabilities or {}).get("moz:profile") or ""
    try:
        web_driver.quit()
    except WebDriverException:
        pass  # already gone; the sweep below still runs
    if profile_path:
        for pid, command_line in _our_firefox_processes().items():
            if profile_path.lower() in command_line.lower():
                _kill_process_tree(pid)
        shutil.rmtree(profile_path, ignore_errors=True)
