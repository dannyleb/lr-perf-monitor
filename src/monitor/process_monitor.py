"""
process_monitor.py
Detects and monitors Adobe Lightroom Classic process.
Collects: CPU%, RAM, thread count, open files.
"""

import psutil
import time
from dataclasses import dataclass, field
from typing import Optional

LR_PROCESS_NAMES = [
    "Adobe Lightroom Classic",
    "Adobe Lightroom",
    "Lightroom",
]


@dataclass
class ProcessSnapshot:
    timestamp: float
    pid: int
    name: str
    cpu_percent: float
    memory_rss_mb: float
    memory_vms_mb: float
    memory_percent: float
    num_threads: int
    status: str
    num_open_files: int = 0


@dataclass
class SystemSnapshot:
    timestamp: float
    cpu_percent_total: float
    cpu_per_core: list
    memory_total_mb: float
    memory_used_mb: float
    memory_available_mb: float
    memory_percent: float
    swap_used_mb: float
    swap_percent: float


def find_lightroom_process() -> Optional[psutil.Process]:
    """Scan running processes for Lightroom Classic."""
    for proc in psutil.process_iter(['pid', 'name', 'status']):
        try:
            name = proc.info['name'] or ""
            for lr_name in LR_PROCESS_NAMES:
                if lr_name.lower() in name.lower():
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def get_process_snapshot(proc: psutil.Process) -> Optional[ProcessSnapshot]:
    """Capture a single snapshot of LR process metrics."""
    try:
        with proc.oneshot():
            cpu = proc.cpu_percent(interval=None)
            mem = proc.memory_info()
            mem_pct = proc.memory_percent()
            threads = proc.num_threads()
            status = proc.status()
            try:
                open_files = len(proc.open_files())
            except (psutil.AccessDenied, OSError):
                open_files = -1

        return ProcessSnapshot(
            timestamp=time.time(),
            pid=proc.pid,
            name=proc.name(),
            cpu_percent=cpu,
            memory_rss_mb=mem.rss / (1024 * 1024),
            memory_vms_mb=mem.vms / (1024 * 1024),
            memory_percent=mem_pct,
            num_threads=threads,
            status=status,
            num_open_files=open_files,
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def get_system_snapshot() -> SystemSnapshot:
    """Capture system-wide CPU and memory metrics."""
    cpu_total = psutil.cpu_percent(interval=None)
    cpu_cores = psutil.cpu_percent(interval=None, percpu=True)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return SystemSnapshot(
        timestamp=time.time(),
        cpu_percent_total=cpu_total,
        cpu_per_core=cpu_cores,
        memory_total_mb=mem.total / (1024 * 1024),
        memory_used_mb=mem.used / (1024 * 1024),
        memory_available_mb=mem.available / (1024 * 1024),
        memory_percent=mem.percent,
        swap_used_mb=swap.used / (1024 * 1024),
        swap_percent=swap.percent,
    )
