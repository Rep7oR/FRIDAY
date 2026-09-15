"""Real local system telemetry for the HUD's CPU/RAM/disk/network widgets -- actual
numbers from the machine Jarvis is running on, via psutil."""
from __future__ import annotations

import getpass
import socket
import time

import psutil

_start_time = time.monotonic()
_last_net: tuple[float, int, int] | None = None  # (timestamp, bytes_sent, bytes_recv)


def _network_throughput_kbps() -> tuple[float, float]:
    """Bytes/sec since the last call, in KB/s. Zero on the very first call (no baseline yet)."""
    global _last_net
    counters = psutil.net_io_counters()
    now = time.monotonic()
    if _last_net is None:
        _last_net = (now, counters.bytes_sent, counters.bytes_recv)
        return 0.0, 0.0
    prev_time, prev_sent, prev_recv = _last_net
    elapsed = max(now - prev_time, 0.001)
    sent_kbps = max(counters.bytes_sent - prev_sent, 0) / 1024 / elapsed
    recv_kbps = max(counters.bytes_recv - prev_recv, 0) / 1024 / elapsed
    _last_net = (now, counters.bytes_sent, counters.bytes_recv)
    return round(sent_kbps, 1), round(recv_kbps, 1)


def get_system_stats() -> dict:
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    sent_kbps, recv_kbps = _network_throughput_kbps()
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "mem_percent": mem.percent,
        "mem_used_gb": round(mem.used / (1024**3), 1),
        "mem_total_gb": round(mem.total / (1024**3), 1),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "net_sent_kbps": sent_kbps,
        "net_recv_kbps": recv_kbps,
        "uptime_seconds": round(time.monotonic() - _start_time),
        "hostname": socket.gethostname(),
        "username": getpass.getuser(),
    }
