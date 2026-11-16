"""
File: capture.py
Purpose:
    Captures the traffic of each parallel browser into its own file, without
    Tor. All browsers share one IP address and often the same X servers, so
    traffic is split by PROCESS:

    packet source  ->  router  ->  per-instance capture
      (all IPv4 TCP     (local port      (records kept in memory,
       on the NIC)       -> browser)      written sorted on stop)
                            ^
                connection tracker: Windows' TCP table (owner PID per local
                port) + process tree (Firefox and its child processes),
                polled every CONNECTION_POLL_SECONDS

    Packet sources:
      "rawsocket" - built into Windows: raw IPv4 socket + SIO_RCVALL, sees
                    both directions on the interface, nothing to install.
      "dumpcap"   - Wireshark's dumpcap + Npcap, all TCP on the interface,
                    streamed through a pipe and parsed here.
    Output: one classic .pcap per instance, link type RAW (IPv4 header first),
    headers only (CAPTURE_SNAPLEN) with the original packet length.

Non-obvious: a connection's first packets (SYN, TLS hello) are on the wire
before the next poll of the TCP table can say which process owns the port.
Packets of not-yet-known ports are therefore parked for up to
PENDING_PACKET_SECONDS and handed to the right capture as soon as the
tracker identifies the owner - no packet of a browser connection is lost.

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

CONNECTION_POLL_SECONDS = 0.2
PENDING_PACKET_SECONDS = 5.0
RAW_SOCKET_RECEIVE_BUFFER = 64 * 1024 * 1024
IP_PROTOCOL_TCP = 6
PCAP_MAGIC_MICROSECONDS = 0xA1B2C3D4
LINKTYPE_ETHERNET = 1
LINKTYPE_RAW_IP = 101
NPCAP_DIRECTORY = r"C:\Windows\System32\Npcap"
DUMPCAP_STARTUP_CHECK_SECONDS = 2


@dataclass
class CaptureInterface:
    ip_address: str
    description: str
    npcap_name: str


@dataclass
class CaptureSummary:
    packets: int
    wire_bytes: int


# ======================================================================
# Interface
# ======================================================================
def default_route_ip():
    """Local IPv4 address used to reach the internet (connect() on a UDP
    socket only selects the route; nothing is sent)."""
    probe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe_socket.connect(("1.1.1.1", 443))
        return probe_socket.getsockname()[0]
    finally:
        probe_socket.close()


def list_capture_interfaces():
    """[(description, ip, npcap name)] of adapters with an IPv4 address."""
    if os.name != "nt":
        return []
    command = ("Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { $a = Get-NetAdapter -InterfaceIndex "
               "$_.InterfaceIndex -ErrorAction SilentlyContinue; if ($a) { \"$($a.InterfaceDescription)|"
               "$($_.IPAddress)|$($a.InterfaceGuid)\" } }")
    try:
        listing = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                                 capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows = []
    for line in listing.splitlines():
        parts = line.strip().split("|")
        if len(parts) == 3:
            rows.append((parts[0], parts[1], f"\\Device\\NPF_{parts[2]}"))
    return rows


def resolve_capture_interface():
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


def npcap_installed():
    return os.path.isdir(NPCAP_DIRECTORY)


# ======================================================================
# Windows process tree and TCP table (ctypes - no extra package)
# ======================================================================
def _process_parent_map():
    """{pid: parent pid} of every running process (Toolhelp snapshot)."""
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot_handle = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)   # TH32CS_SNAPPROCESS
    parent_of = {}
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        has_entry = kernel32.Process32FirstW(snapshot_handle, ctypes.byref(entry))
        while has_entry:
            parent_of[entry.th32ProcessID] = entry.th32ParentProcessID
            has_entry = kernel32.Process32NextW(snapshot_handle, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot_handle)
    return parent_of


def _descendant_pids(root_pid, parent_of):
    children_of = {}
    for pid, parent_pid in parent_of.items():
        children_of.setdefault(parent_pid, []).append(pid)
    found, to_visit = {root_pid}, [root_pid]
    while to_visit:
        for child_pid in children_of.get(to_visit.pop(), []):
            if child_pid not in found and child_pid != 0:
                found.add(child_pid)
                to_visit.append(child_pid)
    return found


def _tcp_table():
    """[(local_ip, local_port, remote_ip, remote_port, owner_pid)] for every
    IPv4 TCP connection (GetExtendedTcpTable, TCP_TABLE_OWNER_PID_ALL)."""
    import ctypes
    from ctypes import wintypes

    class MIB_TCPROW_OWNER_PID(ctypes.Structure):
        _fields_ = [("dwState", wintypes.DWORD), ("dwLocalAddr", wintypes.DWORD),
                    ("dwLocalPort", wintypes.DWORD), ("dwRemoteAddr", wintypes.DWORD),
                    ("dwRemotePort", wintypes.DWORD), ("dwOwningPid", wintypes.DWORD)]

    iphlpapi = ctypes.windll.iphlpapi
    table_size = wintypes.DWORD(0)
    for _retry in range(5):   # the table can grow between the size query and the read
        buffer = ctypes.create_string_buffer(max(table_size.value, 4))
        result = iphlpapi.GetExtendedTcpTable(buffer, ctypes.byref(table_size), False, socket.AF_INET, 5, 0)
        if result == 0:
            break
        if result != 122:                                    # ERROR_INSUFFICIENT_BUFFER
            raise OSError(f"GetExtendedTcpTable failed with code {result}")
    else:
        raise OSError("GetExtendedTcpTable: table kept growing")
    row_count = wintypes.DWORD.from_buffer(buffer).value
    rows = (MIB_TCPROW_OWNER_PID * row_count).from_buffer(buffer, 4)
    return [(socket.inet_ntoa(struct.pack("<I", row.dwLocalAddr)), socket.ntohs(row.dwLocalPort & 0xFFFF),
             socket.inet_ntoa(struct.pack("<I", row.dwRemoteAddr)), socket.ntohs(row.dwRemotePort & 0xFFFF),
             row.dwOwningPid) for row in rows]


# ======================================================================
# Router: packets -> instance captures
# ======================================================================
class _PacketRouter:
    def __init__(self):
        self._lock = threading.Lock()
        self._captures = {}            # capture -> root pid
        self._port_owner = {}          # local port -> capture
        self._pending = {}             # local port -> [(timestamp, packet, original length)]
        self._local_ip = None
        self._source = None
        self._tracker_thread = None

    # ---- lifecycle
    def ensure_running(self, engine, interface):
        with self._lock:
            if self._source is not None:
                return
            self._local_ip = interface.ip_address
            self._source = _RawSocketSource(self, interface) if engine == "rawsocket" \
                else _DumpcapSource(self, interface)
            self._source.start()
            self._tracker_thread = threading.Thread(target=self._track_connections, daemon=True)
            self._tracker_thread.start()

    def stop_source(self):
        with self._lock:
            source, self._source = self._source, None
        if source is not None:
            source.stop()

    def register(self, instance_capture, root_pid):
        with self._lock:
            self._captures[instance_capture] = root_pid

    def unregister(self, instance_capture):
        with self._lock:
            self._captures.pop(instance_capture, None)
            for port in [port for port, owner in self._port_owner.items() if owner is instance_capture]:
                del self._port_owner[port]

    # ---- connection tracking
    def _track_connections(self):
        while True:
            time.sleep(CONNECTION_POLL_SECONDS)
            with self._lock:
                if self._source is None:
                    return
                registered = dict(self._captures)
            if not registered:
                continue
            try:
                parent_of = _process_parent_map()
                tcp_rows = _tcp_table()
            except OSError as table_error:
                print(f"  [WARN] connection table read failed: {table_error}")
                continue
            pid_owner = {}
            for instance_capture, root_pid in registered.items():
                for pid in _descendant_pids(root_pid, parent_of):
                    pid_owner[pid] = instance_capture
            with self._lock:
                for local_ip, local_port, remote_ip, _remote_port, owner_pid in tcp_rows:
                    instance_capture = pid_owner.get(owner_pid)
                    if instance_capture is None or remote_ip in ("0.0.0.0", "127.0.0.1"):
                        continue
                    if local_ip not in (self._local_ip, "0.0.0.0"):
                        continue
                    if self._port_owner.get(local_port) is not instance_capture:
                        self._port_owner[local_port] = instance_capture
                        instance_capture.connection_count += 1
                        for parked in self._pending.pop(local_port, []):
                            instance_capture.add_packet(*parked)

    # ---- packets from the source
    def route_ip_packet(self, timestamp, ip_packet, original_length):
        if len(ip_packet) < 20 or ip_packet[0] >> 4 != 4 or ip_packet[9] != IP_PROTOCOL_TCP:
            return
        header_length = (ip_packet[0] & 0x0F) * 4
        if len(ip_packet) < header_length + 4:
            return
        source_ip = socket.inet_ntoa(ip_packet[12:16])
        destination_ip = socket.inet_ntoa(ip_packet[16:20])
        source_port, destination_port = struct.unpack("!HH", ip_packet[header_length:header_length + 4])
        if source_ip == self._local_ip:
            local_port = source_port
        elif destination_ip == self._local_ip:
            local_port = destination_port
        else:
            return
        with self._lock:
            owner = self._port_owner.get(local_port)
            if owner is None:
                parked_list = self._pending.setdefault(local_port, [])
                parked_list.append((timestamp, ip_packet, original_length))
                if len(self._pending) > 2000 or len(parked_list) > 5000:
                    self._drop_old_pending(timestamp)
                return
        owner.add_packet(timestamp, ip_packet, original_length)

    def _drop_old_pending(self, now):
        for port in list(self._pending):
            fresh = [parked for parked in self._pending[port] if now - parked[0] <= PENDING_PACKET_SECONDS]
            if fresh:
                self._pending[port] = fresh
            else:
                del self._pending[port]

    def periodic_cleanup(self):
        with self._lock:
            self._drop_old_pending(time.time())


_ROUTER = _PacketRouter()


def _cleanup_loop():
    while True:
        time.sleep(PENDING_PACKET_SECONDS)
        _ROUTER.periodic_cleanup()


threading.Thread(target=_cleanup_loop, daemon=True).start()


# ======================================================================
# Packet sources
# ======================================================================
class _PreciseClock:
    """Windows' time.time() ticks in ~15 ms steps; perf_counter() does not."""
    def __init__(self):
        self.wall_base, self.counter_base = time.time(), time.perf_counter()

    def now(self):
        return self.wall_base + (time.perf_counter() - self.counter_base)


class _RawSocketSource:
    def __init__(self, router, interface):
        self.router, self.interface = router, interface
        self.clock = _PreciseClock()
        self.raw_socket = None
        self.running = False

    def start(self):
        raw_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
        raw_socket.bind((self.interface.ip_address, 0))
        raw_socket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
        raw_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RAW_SOCKET_RECEIVE_BUFFER)
        # SIO_RCVALL: all IPv4 packets of this interface, both directions
        # (Windows-only, requires Administrator).
        raw_socket.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
        raw_socket.settimeout(1.0)
        self.raw_socket, self.running = raw_socket, True
        threading.Thread(target=self._receive_loop, daemon=True).start()

    def _receive_loop(self):
        while self.running:
            try:
                packet = self.raw_socket.recv(65535)
            except socket.timeout:
                continue
            except OSError as receive_error:
                if self.running:
                    print(f"  [ERROR] raw socket capture stopped: {receive_error}")
                return
            original_length = struct.unpack("!H", packet[2:4])[0] if len(packet) >= 4 else len(packet)
            self.router.route_ip_packet(self.clock.now(), packet, original_length or len(packet))

    def stop(self):
        self.running = False
        try:
            self.raw_socket.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
        except OSError:
            pass  # socket already closed
        self.raw_socket.close()


class _DumpcapSource:
    """dumpcap writes pcapng to a pipe; the stream is parsed block by block."""

    def __init__(self, router, interface):
        self.router, self.interface = router, interface
        self.process = None
        self.interface_formats = []          # per interface: (linktype, seconds per tick)

    def start(self):
        if not self.interface.npcap_name:
            raise RuntimeError("no Npcap name for the interface - dumpcap cannot capture it")
        self.process = subprocess.Popen(
            [config.DUMPCAP_PATH, "-i", self.interface.npcap_name, "-f", "tcp",
             "-s", str(config.CAPTURE_SNAPLEN + 18), "-w", "-", "-q"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        threading.Thread(target=self._read_stream, daemon=True).start()
        time.sleep(DUMPCAP_STARTUP_CHECK_SECONDS)
        if self.process.poll() is not None:
            raise RuntimeError("dumpcap exited at start-up: " +
                               self.process.stderr.read().decode(errors="replace").strip())

    def _read_exactly(self, byte_count):
        data = b""
        while len(data) < byte_count:
            chunk = self.process.stdout.read(byte_count - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _read_stream(self):
        byte_order = "<"
        while True:
            block_header = self._read_exactly(8)
            if block_header is None:
                return
            if block_header[:4] == b"\x0a\x0d\x0d\x0a":                     # section header
                byte_order_magic = self._read_exactly(4)
                byte_order = "<" if byte_order_magic == b"\x4d\x3c\x2b\x1a" else ">"
                block_length = struct.unpack(byte_order + "I", block_header[4:8])[0]
                self._read_exactly(block_length - 12)
                self.interface_formats = []
                continue
            block_type, block_length = struct.unpack(byte_order + "II", block_header)
            block_body = self._read_exactly(block_length - 8)
            if block_body is None:
                return
            if block_type == 1:                                             # interface description
                linktype = struct.unpack(byte_order + "H", block_body[0:2])[0]
                self.interface_formats.append((linktype, self._timestamp_resolution(block_body[8:-4], byte_order)))
            elif block_type == 6:                                           # enhanced packet
                interface_id, ts_high, ts_low, captured_length, original_length = \
                    struct.unpack(byte_order + "IIIII", block_body[0:20])
                linktype, seconds_per_tick = self.interface_formats[interface_id]
                timestamp = ((ts_high << 32) | ts_low) * seconds_per_tick
                self._route_frame(linktype, block_body[20:20 + captured_length], original_length, timestamp)

    @staticmethod
    def _timestamp_resolution(options, byte_order):
        offset = 0
        while offset + 4 <= len(options):
            option_code, option_length = struct.unpack(byte_order + "HH", options[offset:offset + 4])
            if option_code == 0:
                break
            if option_code == 9 and option_length >= 1:                      # if_tsresol
                value = options[offset + 4]
                return 2.0 ** -(value & 0x7F) if value & 0x80 else 10.0 ** -value
            offset += 4 + option_length + (-option_length % 4)
        return 1e-6

    def _route_frame(self, linktype, frame, original_length, timestamp):
        if linktype == LINKTYPE_ETHERNET:
            ether_type, header_length = struct.unpack("!H", frame[12:14])[0], 14
            if ether_type == 0x8100:                                         # VLAN tag
                ether_type, header_length = struct.unpack("!H", frame[16:18])[0], 18
            if ether_type != 0x0800:
                return
            self.router.route_ip_packet(timestamp, frame[header_length:], original_length - header_length)
        elif linktype in (LINKTYPE_RAW_IP, 228):
            self.router.route_ip_packet(timestamp, frame, original_length)

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGINT))
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.terminate()


# ======================================================================
# Per-instance capture
# ======================================================================
class InstanceCapture:
    """Packets of one browser (process tree rooted at root_pid)."""

    def __init__(self, output_path):
        self.output_path = output_path
        self.records = []
        self.connection_count = 0
        self.started_at = None
        self._lock = threading.Lock()

    def start(self, root_pid):
        self.started_at = time.time()
        _ROUTER.register(self, root_pid)

    def add_packet(self, timestamp, ip_packet, original_length):
        if self.started_at is None or timestamp < self.started_at:
            return   # parked packet from before this capture started
        with self._lock:
            self.records.append((timestamp, ip_packet[:config.CAPTURE_SNAPLEN], original_length))

    def packets_seen(self):
        return len(self.records) > 0

    def stop(self):
        """Stop routing to this capture and write the .pcap (sorted by time:
        parked packets arrive late but carry their true timestamps)."""
        _ROUTER.unregister(self)
        with self._lock:
            records = sorted(self.records, key=lambda record: record[0])
        with open(self.output_path, "wb") as capture_file:
            capture_file.write(struct.pack("<IHHiIII", PCAP_MAGIC_MICROSECONDS, 2, 4, 0, 0,
                                           config.CAPTURE_SNAPLEN, LINKTYPE_RAW_IP))
            for timestamp, captured_bytes, original_length in records:
                seconds = int(timestamp)
                capture_file.write(struct.pack("<IIII", seconds, int((timestamp - seconds) * 1_000_000),
                                               len(captured_bytes), original_length) + captured_bytes)
        return CaptureSummary(len(records), sum(record[2] for record in records))


# ======================================================================
# Engine choice + self test
# ======================================================================
def capture_self_test(engine, interface):
    """Start the engine and capture one test connection made by THIS process
    (tracked exactly like a browser's connections)."""
    _ROUTER.stop_source()
    test_capture = InstanceCapture(output_path=os.devnull)
    try:
        _ROUTER.ensure_running(engine, interface)
        test_capture.start(os.getpid())
        time.sleep(0.5)
        test_socket = socket.create_connection(("1.1.1.1", 443), timeout=10)
        time.sleep(1.0)
        test_socket.close()
        time.sleep(1.0)
    except (OSError, RuntimeError, AttributeError) as test_error:
        _ROUTER.unregister(test_capture)
        _ROUTER.stop_source()
        return False, f"{type(test_error).__name__}: {test_error}"
    packet_count = len(test_capture.records)
    _ROUTER.unregister(test_capture)
    if packet_count >= 3:
        return True, f"saw {packet_count} packets of a test connection on {interface.ip_address}"
    _ROUTER.stop_source()
    return False, f"saw only {packet_count} packets of a test connection on {interface.ip_address}"


def choose_working_engine(interface, report=print):
    """Start the first engine whose self test passes and leave it running."""
    if config.CAPTURE_ENGINE in ("rawsocket", "dumpcap"):
        candidates = [config.CAPTURE_ENGINE]
    else:
        candidates = (["dumpcap"] if os.path.exists(config.DUMPCAP_PATH) and npcap_installed() else []) \
            + ["rawsocket"]
    failures = []
    for engine in candidates:
        passed, message = capture_self_test(engine, interface)
        report(f"capture self-test [{engine}]: {'PASS' if passed else 'FAIL'} - {message}")
        if passed:
            return engine
        failures.append(f"{engine}: {message}")
    raise RuntimeError("no capture engine works on this laptop (" + "; ".join(failures) +
                       "). Run as Administrator; allow python.exe in the Windows Firewall prompt.")


def stop_capture_engine():
    _ROUTER.stop_source()


def summarize_capture(capture_path):
    """Packets and original bytes of a classic .pcap file."""
    packet_count = wire_bytes = 0
    with open(capture_path, "rb") as capture_file:
        capture_file.seek(24)
        while True:
            record_header = capture_file.read(16)
            if len(record_header) < 16:
                break
            _seconds, _microseconds, captured_length, original_length = struct.unpack("<IIII", record_header)
            capture_file.seek(captured_length, 1)
            packet_count += 1
            wire_bytes += original_length
    return CaptureSummary(packet_count, wire_bytes)
