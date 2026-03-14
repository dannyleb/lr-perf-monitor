"""
disk_monitor.py
Tracks disk I/O — system-wide and scoped to LR process where possible.
Intel Mac / macOS Ventura compatible.
"""

import psutil
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class DiskSnapshot:
    timestamp: float
    read_bytes_per_sec: float
    write_bytes_per_sec: float
    read_count_per_sec: float
    write_count_per_sec: float
    disk_usage_percent: float
    disk_free_gb: float
    disk_total_gb: float


class DiskMonitor:
    def __init__(self, mount_point: str = "/"):
        self.mount_point = mount_point
        self._last_io = psutil.disk_io_counters()
        self._last_time = time.time()

    def snapshot(self) -> DiskSnapshot:
        now = time.time()
        current_io = psutil.disk_io_counters()
        elapsed = now - self._last_time

        if elapsed > 0 and self._last_io:
            read_bps = (current_io.read_bytes - self._last_io.read_bytes) / elapsed
            write_bps = (current_io.write_bytes - self._last_io.write_bytes) / elapsed
            read_cps = (current_io.read_count - self._last_io.read_count) / elapsed
            write_cps = (current_io.write_count - self._last_io.write_count) / elapsed
        else:
            read_bps = write_bps = read_cps = write_cps = 0.0

        self._last_io = current_io
        self._last_time = now

        usage = psutil.disk_usage(self.mount_point)

        return DiskSnapshot(
            timestamp=now,
            read_bytes_per_sec=read_bps,
            write_bytes_per_sec=write_bps,
            read_count_per_sec=read_cps,
            write_count_per_sec=write_cps,
            disk_usage_percent=usage.percent,
            disk_free_gb=usage.free / (1024 ** 3),
            disk_total_gb=usage.total / (1024 ** 3),
        )

    @staticmethod
    def format_bytes(bps: float) -> str:
        if bps >= 1024 ** 2:
            return f"{bps / (1024 ** 2):.1f} MB/s"
        elif bps >= 1024:
            return f"{bps / 1024:.1f} KB/s"
        return f"{bps:.0f} B/s"
