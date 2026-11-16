"""
File: capture.py
Purpose:
    Records the traffic between one slot's tor process and the Tor network
    into one file per playback.

Two capture engines:
    "dumpcap"   - Wireshark's dumpcap + Npcap driver. Used when Wireshark and
                  Npcap are installed on the laptop. Output: .pcapng
    "rawsocket" - built into Windows, nothing to install: a raw IPv4 socket
                  with SIO_RCVALL receives every IPv4 packet sent or received
                  on the interface (needs Administrator). One receiver thread
                  serves all slots and writes each packet into the file of the
                  slot whose tor connection it belongs to. Output: .pcap with
                  link type RAW (IPv4 header first), readable by Wireshark.
    Design decision (portable package): Npcap is a kernel driver that must be
    installed, and its licence does not allow bundling it with other
    software, so the portable package relies on "rawsocket" unless the
    laptop already has Wireshark/Npcap.

Both engines keep headers only (CAPTURE_SNAPLEN) and store the original
packet length, so sizes, directions and timestamps are exact.

Author: Lt Col Dey Sanjeetkumar (2025JCS2949) · Lt Col Saurabh Kumar Singh (2025JCS3011)
Date:   2026-11-12
"""

import os
import signal
import socket
import struct
import subprocess
import threading
import time
from dataclasses import dataclass

import config

# Seconds dumpcap is given to start before we check it has not exited with
# an error (missing Npcap / admin rights / bad interface).
DUMPCAP_STARTUP_CHECK_SECONDS = 2
# Seconds dumpcap is given to flush and exit after CTRL_BREAK.
DUMPCAP_STOP_TIMEOUT_SECONDS = 15
# A capture file with no packets is < 1 KB (file + interface headers);
# anything beyond this means packets are being recorded.
EMPTY_CAPTURE_ALLOWANCE_BYTES = 2048
# Npcap installs its DLLs here; dumpcap cannot capture without them.
NPCAP_DIRECTORY = r"C:\Windows\System32\Npcap"

# pcap constants (classic libpcap file format)
PCAP_MAGIC_MICROSECONDS = 0xA1B2C3D4
LINKTYPE_RAW_IP = 101            # packet data starts with the IP header
RAW_SOCKET_RECEIVE_BUFFER = 64 * 1024 * 1024   # large: no drops during HD bursts
IP_PROTOCOL_TCP = 6


@dataclass
class CaptureInterface:
    ip_address: str
    description: str
    npcap_name: str          # \Device\NPF_{GUID} for dumpcap ("" if unknown)


@dataclass
class CaptureSummary:
    packets: int
    wire_bytes: int


# ----------------------------------------------------------------- interface
def default_route_ip():
    """Local IPv4 address used to reach the internet (no packet is sent:
    connect() on a UDP socket only selects the route)."""
    probe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe_socket.connect(("1.1.1.1", 443))
        return probe_socket.getsockname()[0]
    finally:
        probe_socket.close()


def _powershell(command):
    try:
        return subprocess.run(["powershell", "-NoProfile", "-Command", command],
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def list_capture_interfaces():
    """[(description, ip, npcap name)] for adapters that have an IPv4 address."""
    if os.name != "nt":
        return []
    listing = _powershell(
        "Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { $a = Get-NetAdapter -InterfaceIndex "
        "$_.InterfaceIndex -ErrorAction SilentlyContinue; if ($a) { \"$($a.InterfaceDescription)|"
        "$($_.IPAddress)|$($a.InterfaceGuid)\" } }")
    rows = []
    for line in listing.splitlines():
        parts = line.split("|")
        if len(parts) == 3:
            rows.append((parts[0], parts[1], f"\\Device\\NPF_{parts[2]}"))
    return rows


def resolve_capture_interface():
    """Interface named in config (IP, description or NPF name), else the
    interface carrying the default route."""
    interfaces = list_capture_interfaces()
    if config.CAPTURE_INTERFACE:
        wanted = config.CAPTURE_INTERFACE.lower()
        for description, ip_address, npcap_name in interfaces:
            if wanted in (description.lower(), ip_address, npcap_name.lower()):
                return CaptureInterface(ip_address, description, npcap_name)
        raise ValueError(f'CAPTURE_INTERFACE "{config.CAPTURE_INTERFACE}" not found - see "Check setup"')
    ip_address = default_route_ip()
    for description, interface_ip, npcap_name in interfaces:
        if interface_ip == ip_address:
            return CaptureInterface(ip_address, description, npcap_name)
    return CaptureInterface(ip_address, "default route", "")


# -------------------------------------------------------------------- engine
def npcap_installed():
    return os.path.isdir(NPCAP_DIRECTORY)


def selected_capture_engine():
    dumpcap_usable = os.path.exists(config.DUMPCAP_PATH) and npcap_installed()
    if config.CAPTURE_ENGINE == "dumpcap":
        if not dumpcap_usable:
            raise FileNotFoundError("CAPTURE_ENGINE = 'dumpcap' needs Wireshark (dumpcap.exe) and Npcap installed")
        return "dumpcap"
    if config.CAPTURE_ENGINE == "rawsocket":
        return "rawsocket"
    return "dumpcap" if dumpcap_usable else "rawsocket"


def capture_file_extension(engine):
    return ".pcapng" if engine == "dumpcap" else ".pcap"


def build_capture_filter(tor_connections, guard_addresses=()):
    """BPF-syntax description of what one slot captures (dumpcap uses it as
    its filter; for rawsocket it is recorded in the log for reference).

    Preferred: the slot's own tor connections, each pinned by remote address
    AND local port - five slots may share a guard relay, never a local port.
    """
    if tor_connections:
        connection_terms = " or ".join(f"(host {remote_ip} and port {local_port})"
                                       for remote_ip, _remote_port, local_port, *_local_ip in tor_connections)
        return f"tcp and ({connection_terms})"
    if guard_addresses:
        return "tcp and (" + " or ".join(f"host {address}" for address in guard_addresses) + ")"
    return "tcp"


# ------------------------------------------------------------ raw socket hub
class _RawSocketHub:
    """One SIO_RCVALL socket for the whole app; packets are routed to the
    slot whose tor connection they belong to."""

    def __init__(self):
        self._lock = threading.Lock()
        self._routes = {}                 # (remote_ip, local_port or None) -> PacketCapture
        self._receiver_thread = None
        self._raw_socket = None
        self._bound_ip = None
        # Windows' time.time() ticks in ~15 ms steps; perf_counter() is
        # sub-microsecond. Timestamp = wall clock at start + elapsed counter.
        self._wall_clock_base = time.time()
        self._counter_base = time.perf_counter()

    def _ensure_running(self, local_ip):
        if self._receiver_thread is not None and self._receiver_thread.is_alive():
            if local_ip != self._bound_ip:
                print(f"  [WARN] raw socket bound to {self._bound_ip}, but a tor connection uses {local_ip}")
            return
        raw_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
        raw_socket.bind((local_ip, 0))
        raw_socket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
        raw_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RAW_SOCKET_RECEIVE_BUFFER)
        # SIO_RCVALL: receive ALL IPv4 packets of this interface, both
        # directions (Windows-only ioctl, requires Administrator).
        raw_socket.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
        raw_socket.settimeout(1.0)
        self._raw_socket = raw_socket
        self._bound_ip = local_ip
        self._receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._receiver_thread.start()

    def register(self, packet_capture, local_ip, tor_connections, guard_addresses):
        with self._lock:
            self._ensure_running(local_ip)
            for remote_ip, _remote_port, local_port, *_local_ip in tor_connections:
                self._routes[(remote_ip, local_port)] = packet_capture
            if not tor_connections:
                for remote_ip in guard_addresses:
                    self._routes[(remote_ip, None)] = packet_capture

    def unregister(self, packet_capture):
        with self._lock:
            for route_key in [key for key, owner in self._routes.items() if owner is packet_capture]:
                del self._routes[route_key]

    def _receive_loop(self):
        while True:
            try:
                packet = self._raw_socket.recv(65535)
            except socket.timeout:
                continue
            except OSError as receive_error:
                print(f"  [ERROR] raw socket capture stopped: {receive_error}")
                return
            timestamp = self._wall_clock_base + (time.perf_counter() - self._counter_base)
            if len(packet) < 20 or packet[0] >> 4 != 4 or packet[9] != IP_PROTOCOL_TCP:
                continue
            header_length = (packet[0] & 0x0F) * 4
            if len(packet) < header_length + 4:
                continue
            source_ip = socket.inet_ntoa(packet[12:16])
            destination_ip = socket.inet_ntoa(packet[16:20])
            source_port, destination_port = struct.unpack("!HH", packet[header_length:header_length + 4])
            # Incoming: relay -> us (our port = destination); outgoing: us -> relay.
            with self._lock:
                owner = (self._routes.get((source_ip, destination_port))
                         or self._routes.get((destination_ip, source_port))
                         or self._routes.get((source_ip, None))
                         or self._routes.get((destination_ip, None)))
            if owner is not None:
                original_length = struct.unpack("!H", packet[2:4])[0] or len(packet)
                owner.write_raw_ip_packet(timestamp, packet, original_length)


_RAW_SOCKET_HUB = _RawSocketHub()


# ------------------------------------------------------------ per-slot capture
class PacketCapture:
    def __init__(self, engine, interface, bpf_filter, output_path, max_duration_seconds,
                 tor_connections=(), guard_addresses=()):
        self.engine = engine
        self.interface = interface
        self.bpf_filter = bpf_filter
        self.output_path = output_path
        self.max_duration_seconds = int(max_duration_seconds)
        self.tor_connections = list(tor_connections)
        self.guard_addresses = list(guard_addresses)
        self.bytes_written = 0
        self.raw_packets_written = 0
        self._output_file = None
        self._file_lock = threading.Lock()
        self._dumpcap_process = None
        self._reader_thread = None

    def start(self):
        if self.engine == "dumpcap":
            self._start_dumpcap()
        else:
            self._start_rawsocket()

    def packets_seen(self):
        """True once at least one packet has been recorded."""
        if self.engine == "rawsocket":
            return self.raw_packets_written > 0
        return self.bytes_written > EMPTY_CAPTURE_ALLOWANCE_BYTES

    # -- rawsocket
    def _start_rawsocket(self):
        self._output_file = open(self.output_path, "wb")
        global_header = struct.pack("<IHHiIII", PCAP_MAGIC_MICROSECONDS, 2, 4, 0, 0,
                                    config.CAPTURE_SNAPLEN, LINKTYPE_RAW_IP)
        self._output_file.write(global_header)
        # Bind to the local address tor's sockets really use (from netstat);
        # this cannot be the wrong adapter.
        local_ip = next((connection[3] for connection in self.tor_connections if len(connection) > 3),
                        self.interface.ip_address)
        _RAW_SOCKET_HUB.register(self, local_ip, self.tor_connections, self.guard_addresses)

    def write_raw_ip_packet(self, timestamp, packet, original_length):
        captured_bytes = packet[:config.CAPTURE_SNAPLEN]
        seconds = int(timestamp)
        microseconds = int((timestamp - seconds) * 1_000_000)
        record = struct.pack("<IIII", seconds, microseconds, len(captured_bytes), original_length) + captured_bytes
        with self._file_lock:
            if self._output_file is not None:
                self._output_file.write(record)
                self.bytes_written += len(record)
                self.raw_packets_written += 1

    # -- dumpcap
    def _start_dumpcap(self):
        # Writing to a PIPE ("-w -") makes dumpcap flush after every packet;
        # a reader thread writes the stream to disk, so whatever was captured
        # is on disk however dumpcap ends (first test run lost its buffer).
        dumpcap_command = [
            config.DUMPCAP_PATH,
            "-i", self.interface.npcap_name,
            "-f", self.bpf_filter,
            "-s", str(config.CAPTURE_SNAPLEN),
            "-w", "-",
            "-a", f"duration:{self.max_duration_seconds}",   # safety net if the app crashes
            "-q",
        ]
        self._output_file = open(self.output_path, "wb")
        self._dumpcap_process = subprocess.Popen(
            dumpcap_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        self._reader_thread = threading.Thread(target=self._copy_dumpcap_output, daemon=True)
        self._reader_thread.start()
        time.sleep(DUMPCAP_STARTUP_CHECK_SECONDS)
        if self._dumpcap_process.poll() is not None:
            error_text = self._dumpcap_process.stderr.read().decode(errors="replace").strip()
            self.stop()
            raise RuntimeError(f"dumpcap exited at start-up: {error_text}")

    def _copy_dumpcap_output(self):
        while True:
            chunk = self._dumpcap_process.stdout.read1(65536)
            if not chunk:
                break
            self._output_file.write(chunk)
            self._output_file.flush()
            self.bytes_written += len(chunk)

    def stop(self):
        if self.engine == "rawsocket":
            _RAW_SOCKET_HUB.unregister(self)
        if self._dumpcap_process is not None:
            if self._dumpcap_process.poll() is None:
                # Windows: dumpcap runs in its own process group, so
                # CTRL_BREAK reaches only it and it closes its output cleanly.
                self._dumpcap_process.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGINT))
                try:
                    self._dumpcap_process.wait(timeout=DUMPCAP_STOP_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    self._dumpcap_process.terminate()
                    self._dumpcap_process.wait(timeout=5)
            if self._reader_thread is not None:
                self._reader_thread.join(timeout=10)
            self._dumpcap_process = None
        with self._file_lock:
            if self._output_file is not None:
                self._output_file.close()
                self._output_file = None


# ---------------------------------------------------------------- self test
SELF_TEST_TARGET = ("1.1.1.1", 443)      # any reachable HTTPS server will do
SELF_TEST_MIN_PACKETS = 3                # SYN, SYN-ACK, ACK at least


def capture_self_test(engine, interface, work_dir):
    """Capture one test TCP connection with the given engine.
    Returns (passed, message). Run before collecting, so a capture that
    would record nothing is found in seconds instead of after a whole video.
    """
    test_path = os.path.join(work_dir, f"capture_self_test{capture_file_extension(engine)}")
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.settimeout(10)
    test_socket.bind((interface.ip_address, 0))
    local_port = test_socket.getsockname()[1]
    test_connection = [(SELF_TEST_TARGET[0], SELF_TEST_TARGET[1], local_port, interface.ip_address)]
    test_capture = PacketCapture(engine, interface, build_capture_filter(test_connection), test_path, 60,
                                 tor_connections=test_connection)
    try:
        test_capture.start()
        time.sleep(1)
        test_socket.connect(SELF_TEST_TARGET)
        test_socket.close()
        time.sleep(2)
    except (OSError, RuntimeError, AttributeError) as test_error:
        # AttributeError: socket.SIO_RCVALL exists only on Windows.
        return False, f"{type(test_error).__name__}: {test_error}"
    finally:
        test_socket.close()
        test_capture.stop()
    try:
        summary = summarize_capture(test_path)
    finally:
        if os.path.exists(test_path):
            os.remove(test_path)
    if summary.packets >= SELF_TEST_MIN_PACKETS:
        return True, f"saw {summary.packets} packets of a test connection on {interface.ip_address}"
    return False, (f"saw only {summary.packets} packets of a test connection on {interface.ip_address} "
                   f"({interface.description})")


def choose_working_engine(interface, work_dir, report=print):
    """Engine to use for this run: the configured one, or with "auto" the
    first of dumpcap / rawsocket whose self test passes."""
    if config.CAPTURE_ENGINE in ("dumpcap", "rawsocket"):
        candidates = [selected_capture_engine()]
    else:
        candidates = (["dumpcap"] if os.path.exists(config.DUMPCAP_PATH) and npcap_installed() else []) + ["rawsocket"]
    failures = []
    for engine in candidates:
        passed, message = capture_self_test(engine, interface, work_dir)
        report(f"capture self-test [{engine}]: {'PASS' if passed else 'FAIL'} - {message}")
        if passed:
            return engine
        failures.append(f"{engine}: {message}")
    raise RuntimeError("no capture engine works on this laptop (" + "; ".join(failures) +
                       "). Run as Administrator; allow python.exe in the Windows Firewall prompt.")


# ------------------------------------------------------------------ summary
def summarize_capture(capture_path):
    """Count packets and original (on-the-wire) bytes of a .pcap or .pcapng
    file without any third-party library."""
    if not os.path.exists(capture_path) or os.path.getsize(capture_path) == 0:
        return CaptureSummary(0, 0)
    packet_count = 0
    wire_bytes = 0
    with open(capture_path, "rb") as capture_file:
        file_start = capture_file.read(4)
        if file_start == b"\x0a\x0d\x0d\x0a":                      # pcapng
            capture_file.seek(8)
            byte_order = "<" if capture_file.read(4) == b"\x4d\x3c\x2b\x1a" else ">"
            capture_file.seek(0)
            while True:
                block_header = capture_file.read(8)
                if len(block_header) < 8:
                    break
                block_type, block_length = struct.unpack(byte_order + "II", block_header)
                if block_length < 12:
                    raise ValueError(f"corrupt pcapng block in {capture_path}")
                block_body = capture_file.read(block_length - 8)
                if len(block_body) < block_length - 8:
                    break                                           # truncated last block
                if block_type == 6:                                 # Enhanced Packet Block
                    packet_count += 1
                    wire_bytes += struct.unpack(byte_order + "I", block_body[16:20])[0]
                elif block_type == 3:                               # Simple Packet Block
                    packet_count += 1
                    wire_bytes += struct.unpack(byte_order + "I", block_body[0:4])[0]
        else:                                                       # classic pcap
            magic = struct.unpack("<I", file_start)[0]
            byte_order = "<" if magic in (0xA1B2C3D4, 0xA1B23C4D) else ">"
            capture_file.seek(24)
            while True:
                record_header = capture_file.read(16)
                if len(record_header) < 16:
                    break
                _seconds, _fraction, captured_length, original_length = struct.unpack(byte_order + "IIII", record_header)
                if len(capture_file.read(captured_length)) < captured_length:
                    break
                packet_count += 1
                wire_bytes += original_length
    return CaptureSummary(packet_count, wire_bytes)
