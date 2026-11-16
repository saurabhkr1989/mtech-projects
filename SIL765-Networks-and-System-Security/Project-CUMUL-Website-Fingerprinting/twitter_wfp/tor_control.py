"""
File: tor_control.py
Purpose:
    One TorSession per parallel slot: starts the slot's own tor.exe (from the
    Tor Browser bundle), rotates circuits with NEWNYM, and reports the exact
    TCP connections that tor process has to the Tor network - the slot's
    packet capture is pinned to those connections only.

Design decision: one tor process PER SLOT, not one shared tor.
    With a shared tor, five browsers' traffic would be multiplexed inside the
    same TLS connection to the same guard - no capture filter could separate
    the five videos afterwards. A separate tor per slot gives each slot its
    own TCP connection(s) (local port differs even if two tors pick the same
    guard), so each slot's capture contains only its own video.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import os
import re
import shutil
import socket
import threading
import subprocess
import time

import stem
import stem.process
import stem.util.connection
from stem import Signal
from stem.control import Controller

import config

LOOPBACK_ADDRESSES = {"127.0.0.1", "::1", "0.0.0.0", "::"}

# Guard relay currently used by each running slot. Slots must not share a
# guard: each parallel browser then reaches the Tor network through a
# different first hop as well as a different circuit.
_GUARDS_IN_USE = {}
_GUARDS_LOCK = threading.Lock()
# Restarts (with a fresh data folder = fresh guard choice) allowed when a
# slot's tor picked a guard another slot already uses.
MAX_GUARD_RESELECTIONS = 3


def port_is_listening(port, host="127.0.0.1"):
    """True if something accepts TCP connections on host:port."""
    probe_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe_socket.settimeout(1)
    try:
        return probe_socket.connect_ex((host, port)) == 0
    finally:
        probe_socket.close()


def slot_ports(slot_index):
    socks_port = config.TOR_BASE_SOCKS_PORT + 2 * slot_index
    return socks_port, socks_port + 1


class TorSession:
    """The tor process + authenticated control connection of one slot."""

    def __init__(self, slot_index, report=print):
        self.slot_index = slot_index
        self.socks_port, self.control_port = slot_ports(slot_index)
        self.data_dir = os.path.join(config.TOR_DATA_DIR, f"slot{slot_index}")
        self.report = report
        self.controller = None
        self.tor_process = None        # set only if this app launched tor
        self.tor_pid = None
        self.control_cookie_path = None

    # ------------------------------------------------------------------ start
    def start(self):
        self._start_or_attach()
        for _reselection in range(MAX_GUARD_RESELECTIONS):
            guard = self.primary_guard()
            with _GUARDS_LOCK:
                shared_with = [slot for slot, slot_guard in _GUARDS_IN_USE.items()
                               if slot_guard == guard and slot != self.slot_index]
                if guard and not shared_with:
                    _GUARDS_IN_USE[self.slot_index] = guard
                    break
            if self.tor_process is None:
                self.report(f"[WARN] attached tor shares guard {guard} with slot(s) {shared_with}")
                break
            self.report(f"guard {guard} already used by slot {shared_with[0] + 1} - "
                        "restarting this tor with a fresh guard")
            self.close()
            shutil.rmtree(self.data_dir, ignore_errors=True)
            self._start_or_attach()
        self.report(f"tor ready (SOCKS {self.socks_port}, control {self.control_port}, "
                    f"guard {_GUARDS_IN_USE.get(self.slot_index, '?')})")

    def _start_or_attach(self):
        if port_is_listening(self.control_port):
            # Left over from an interrupted earlier run: reuse it.
            self.report(f"tor already on control port {self.control_port} - attaching to it")
        elif port_is_listening(self.socks_port):
            raise RuntimeError(f"Port {self.socks_port} is in use by another program; "
                               "change TOR_BASE_SOCKS_PORT in config.py")
        else:
            self._launch_own_tor()

        self.controller = Controller.from_port(port=self.control_port)
        # authenticate() reads PROTOCOLINFO and picks cookie auth automatically.
        self.controller.authenticate()
        self.control_cookie_path = self.controller.get_protocolinfo().cookie_path
        self.tor_pid = self.tor_process.pid if self.tor_process else self.controller.get_pid(None)
        self._wait_until_bootstrapped()

    def is_alive(self):
        return self.controller is not None and self.controller.is_alive()

    def primary_guard(self):
        """Fingerprint of the guard (first hop) of this tor's built circuits."""
        first_hops = [circuit.path[0][0] for circuit in self.controller.get_circuits([])
                      if circuit.status == "BUILT" and circuit.path]
        return max(set(first_hops), key=first_hops.count) if first_hops else None

    def circuit_path_for(self, host_fragments=("youtube.com", "googlevideo.com", "ytimg.com")):
        """'guard > middle > exit' (nickname~fingerprint prefix) of the circuit
        carrying the YouTube streams - logged as proof of a distinct circuit."""
        for tor_stream in self.controller.get_streams([]):
            if tor_stream.circ_id and any(fragment in (tor_stream.target_address or "")
                                          for fragment in host_fragments):
                try:
                    circuit = self.controller.get_circuit(tor_stream.circ_id)
                except (stem.ControllerError, ValueError):
                    continue
                return " > ".join(f"{nickname}~{fingerprint[:8]}" for fingerprint, nickname in circuit.path)
        return ""

    def _launch_own_tor(self):
        if not os.path.exists(config.TOR_EXE_PATH):
            raise FileNotFoundError(f"tor.exe not found at {config.TOR_EXE_PATH} (check TBB_DIR in config.py)")
        os.makedirs(self.data_dir, exist_ok=True)
        tor_settings = {
            "SocksPort": str(self.socks_port),
            "ControlPort": str(self.control_port),
            # Cookie auth: no password in config.py; the cookie file is
            # readable only by the local user who started tor.
            "CookieAuthentication": "1",
            # Own DataDirectory per slot: tor locks its data folder, and an
            # own folder also means an independently chosen guard.
            "DataDirectory": self.data_dir,
        }
        if os.path.exists(config.TOR_GEOIP_FILE):
            tor_settings["GeoIPFile"] = config.TOR_GEOIP_FILE
            tor_settings["GeoIPv6File"] = config.TOR_GEOIP6_FILE

        self.report("starting tor.exe (first bootstrap can take a minute)")
        # Windows adaptation: stem implements its launch timeout with SIGALRM,
        # which Windows lacks, so timeout must be None here.
        # take_ownership=True: tor exits automatically when this app exits.
        self.tor_process = stem.process.launch_tor_with_config(
            config=tor_settings,
            tor_cmd=config.TOR_EXE_PATH,
            take_ownership=True,
            timeout=None,
            completion_percent=100,
        )

    def _wait_until_bootstrapped(self):
        if self.controller.get_conf("DisableNetwork", "0") == "1":
            self.controller.set_conf("DisableNetwork", "0")
        deadline = time.monotonic() + config.TOR_BOOTSTRAP_TIMEOUT
        while time.monotonic() < deadline:
            if "PROGRESS=100" in self.controller.get_info("status/bootstrap-phase", ""):
                return
            time.sleep(2)
        raise TimeoutError(f"tor did not finish bootstrapping in {config.TOR_BOOTSTRAP_TIMEOUT}s")

    # --------------------------------------------------------------- circuits
    def new_circuit(self):
        """Send NEWNYM so the next browser gets fresh circuits (new exit)."""
        # Non-obvious: NEWNYM only affects NEW connections, so it is sent
        # BEFORE the browser is launched; tor rate-limits it to one per ~10 s
        # and get_newnym_wait() returns the remaining wait.
        remaining_wait = self.controller.get_newnym_wait()
        if remaining_wait > 0:
            time.sleep(remaining_wait)
        self.controller.signal(Signal.NEWNYM)
        time.sleep(config.CIRCUIT_WAIT_SECONDS)

    # ---------------------------------------------------- capture filter data
    def network_connections(self):
        """(remote_ip, remote_port, local_port, local_ip) of every TCP connection this
        tor process has open to the Tor network (loopback SOCKS/control
        connections from the browser and this app are excluded).

        Read from the operating system ("netstat -ano" on Windows), so it is
        exactly what is on the wire - IPv4 or IPv6 - unlike relay addresses
        taken from the consensus.
        """
        if not self.tor_pid:
            return []
        resolver = (stem.util.connection.Resolver.NETSTAT_WINDOWS if os.name == "nt"
                    else stem.util.connection.system_resolvers()[0])
        try:
            connections = stem.util.connection.get_connections(resolver, process_pid=self.tor_pid)
        except IOError as lookup_error:
            self.report(f"[WARN] could not list tor's connections ({lookup_error}); using guard addresses")
            return []
        return sorted({(c.remote_address, c.remote_port, c.local_port, c.local_address) for c in connections
                       if c.remote_address not in LOOPBACK_ADDRESSES})

    def guard_addresses(self):
        """Fallback: IP addresses (from the consensus) of relays tor is
        connected to, used only if the connection table cannot be read."""
        relay_fingerprints = set()
        for line in self.controller.get_info("orconn-status", "").splitlines():
            if line.endswith("CONNECTED"):
                relay_fingerprints.update(re.findall(r"\$([0-9A-Fa-f]{40})", line))
        for circuit in self.controller.get_circuits([]):
            if circuit.status == "BUILT" and circuit.path:
                relay_fingerprints.add(circuit.path[0][0])
        addresses = set()
        for fingerprint in relay_fingerprints:
            try:
                addresses.add(self.controller.get_network_status(fingerprint).address)
            except (stem.ControllerError, ValueError):
                continue  # relay not in the current consensus
        return sorted(addresses)

    # ------------------------------------------------------------------ close
    def close(self):
        with _GUARDS_LOCK:
            _GUARDS_IN_USE.pop(self.slot_index, None)
        if self.controller is not None:
            self.controller.close()
            self.controller = None
        if self.tor_process is not None:
            self.tor_process.terminate()
            try:
                self.tor_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.report("[WARN] tor did not exit within 10 s; killing it")
                self.tor_process.kill()
            self.tor_process = None
