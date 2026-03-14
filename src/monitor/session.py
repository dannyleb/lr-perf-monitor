"""
session.py
Central session controller. Runs all monitors on a configurable interval.
Emits combined DataFrames. Thread-safe for GUI use.
"""

import time
import threading
from dataclasses import dataclass, asdict
from typing import Optional, Callable, List
from collections import deque

import psutil

from .process_monitor import (
    find_lightroom_process,
    get_process_snapshot,
    get_system_snapshot,
    ProcessSnapshot,
    SystemSnapshot,
)
from .disk_monitor import DiskMonitor, DiskSnapshot
from .thermal_monitor import get_thermal_pressure_ioreg, ThermalSnapshot
from .gpu_monitor import get_gpu_snapshot, GPUSnapshot


@dataclass
class CombinedSnapshot:
    process: Optional[ProcessSnapshot]
    system: SystemSnapshot
    disk: DiskSnapshot
    thermal: ThermalSnapshot
    gpu: GPUSnapshot
    lr_running: bool
    timestamp: float


class MonitorSession:
    def __init__(
        self,
        interval_sec: float = 2.0,
        history_size: int = 300,
        on_snapshot: Optional[Callable[[CombinedSnapshot], None]] = None,
        enable_thermal: bool = False,  # Requires sudo
        enable_gpu_util: bool = False,  # Requires sudo
    ):
        self.interval_sec = interval_sec
        self.history: deque[CombinedSnapshot] = deque(maxlen=history_size)
        self.on_snapshot = on_snapshot
        self.enable_thermal = enable_thermal
        self.enable_gpu_util = enable_gpu_util

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._disk_monitor = DiskMonitor()
        self._lr_proc: Optional[psutil.Process] = None
        self._lock = threading.Lock()

        # Pre-initialize CPU percent (first call always returns 0)
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None, percpu=True)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_history(self) -> List[CombinedSnapshot]:
        with self._lock:
            return list(self.history)

    def _loop(self):
        while self._running:
            start = time.time()
            snap = self._collect()

            with self._lock:
                self.history.append(snap)

            if self.on_snapshot:
                try:
                    self.on_snapshot(snap)
                except Exception:
                    pass

            elapsed = time.time() - start
            sleep_time = max(0, self.interval_sec - elapsed)
            time.sleep(sleep_time)

    def _collect(self) -> CombinedSnapshot:
        now = time.time()

        # Re-find LR process if lost
        if self._lr_proc is None or not self._lr_proc.is_running():
            self._lr_proc = find_lightroom_process()

        proc_snap = None
        lr_running = False
        if self._lr_proc:
            proc_snap = get_process_snapshot(self._lr_proc)
            lr_running = proc_snap is not None

        sys_snap = get_system_snapshot()
        disk_snap = self._disk_monitor.snapshot()

        # Thermal - quick ioreg fallback always, powermetrics if enabled
        if self.enable_thermal:
            from .thermal_monitor import get_powermetrics_snapshot
            thermal_snap = get_powermetrics_snapshot()
        else:
            thermal_snap = ThermalSnapshot(
                timestamp=now,
                thermal_pressure=get_thermal_pressure_ioreg(),
                source="ioreg"
            )

        # GPU
        gpu_snap = get_gpu_snapshot()

        return CombinedSnapshot(
            process=proc_snap,
            system=sys_snap,
            disk=disk_snap,
            thermal=thermal_snap,
            gpu=gpu_snap,
            lr_running=lr_running,
            timestamp=now,
        )
