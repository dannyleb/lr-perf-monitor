"""
diagnostics.py
Real-time performance diagnosis engine.
Watches snapshots, fires plain-English recommendations based on actual
conditions observed on Danny's machine (2017 MBP, 16GB, dual GPU).
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional, Deque
from collections import deque
from enum import Enum

from ..monitor.session import CombinedSnapshot


class Severity(Enum):
    OK      = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Recommendation:
    severity: Severity
    title: str
    detail: str
    action: str
    timestamp: float = field(default_factory=time.time)
    key: str = ""          # unique ID so we don't spam duplicates


class DiagnosticsEngine:
    """
    Stateful rules engine. Call feed(snapshot) on every new sample.
    Maintains a list of active recommendations. Cleared recommendations
    are removed when conditions resolve.
    """

    RAM_TOTAL_MB = 16384.0   # 16GB — hardcoded for this machine
    RAM_WARN_PCT  = 75.0     # 12GB
    RAM_CRIT_PCT  = 87.5     # ~14GB
    CPU_SPIKE_PCT = 80.0
    CPU_SPIKE_SECS = 30      # sustained seconds before firing
    DISK_WRITE_WARN_MB = 50.0
    SWAP_WARN_MB = 512.0

    def __init__(self, history_window: int = 30):
        # history_window = number of samples to look back for sustained checks
        self._history: Deque[CombinedSnapshot] = deque(maxlen=history_window)
        self._active: dict[str, Recommendation] = {}
        self._log: List[Recommendation] = []   # full session history
        self._last_gpu: Optional[str] = None

    def feed(self, snap: CombinedSnapshot) -> List[Recommendation]:
        """
        Ingest one snapshot. Returns list of NEW recommendations fired this tick.
        """
        self._history.append(snap)
        new = []

        new += self._check_ram(snap)
        new += self._check_swap(snap)
        new += self._check_cpu_sustained(snap)
        new += self._check_thermal(snap)
        new += self._check_disk(snap)
        new += self._check_gpu(snap)

        for r in new:
            self._active[r.key] = r
            self._log.append(r)

        self._resolve_stale(snap)
        return new

    def get_active(self) -> List[Recommendation]:
        return sorted(self._active.values(), key=lambda r: r.timestamp, reverse=True)

    def get_log(self) -> List[Recommendation]:
        return list(reversed(self._log))

    def clear_log(self):
        self._log.clear()

    # ------------------------------------------------------------------ #
    # Rules
    # ------------------------------------------------------------------ #

    def _check_ram(self, snap: CombinedSnapshot) -> List[Recommendation]:
        recs = []
        used = snap.system.memory_used_mb
        pct  = (used / self.RAM_TOTAL_MB) * 100

        if pct >= self.RAM_CRIT_PCT:
            r = Recommendation(
                severity=Severity.CRITICAL,
                key="ram_critical",
                title="RAM Critical — Lightroom may freeze",
                detail=f"System RAM at {used/1024:.1f} GB / 16 GB ({pct:.0f}%). "
                       f"macOS will start compressing memory and swapping, causing Lightroom freezes and slow response.",
                action="Quit unused apps. In Lightroom: Preferences → Performance → reduce Camera Raw cache. "
                       "Disable 'Automatically write XMP' if enabled.",
                timestamp=snap.timestamp,
            )
            if "ram_critical" not in self._active:
                recs.append(r)
            else:
                self._active["ram_critical"] = r  # update value

        elif pct >= self.RAM_WARN_PCT:
            r = Recommendation(
                severity=Severity.WARNING,
                key="ram_warning",
                title="RAM High — Performance may degrade",
                detail=f"System RAM at {used/1024:.1f} GB / 16 GB ({pct:.0f}%). "
                       f"Lightroom performs best below 75% memory usage on a 16GB system.",
                action="Close other applications. In Lightroom: Preferences → Performance → "
                       "lower Camera Raw cache maximum size.",
                timestamp=snap.timestamp,
            )
            if "ram_warning" not in self._active:
                recs.append(r)
            else:
                self._active["ram_warning"] = r

        return recs

    def _check_swap(self, snap: CombinedSnapshot) -> List[Recommendation]:
        recs = []
        swap = snap.system.swap_used_mb
        if swap >= self.SWAP_WARN_MB:
            r = Recommendation(
                severity=Severity.WARNING,
                key="swap_active",
                title="Swap Active — macOS paging to disk",
                detail=f"macOS is using {swap/1024:.1f} GB of swap. "
                       f"Disk-based swap is orders of magnitude slower than RAM — "
                       f"this directly causes Lightroom lag and sluggish brush response.",
                action="Quit other apps to free RAM. Restart Lightroom if swap exceeds 2 GB. "
                       "Consider reducing catalog size or splitting into smaller catalogs.",
                timestamp=snap.timestamp,
            )
            if "swap_active" not in self._active:
                recs.append(r)
            else:
                self._active["swap_active"] = r
        return recs

    def _check_cpu_sustained(self, snap: CombinedSnapshot) -> List[Recommendation]:
        recs = []
        if snap.process is None:
            return recs

        # Count how many recent samples had LR CPU > threshold
        high_count = sum(
            1 for s in self._history
            if s.process and s.process.cpu_percent >= self.CPU_SPIKE_PCT
        )
        sustained = len(self._history) > 5 and high_count >= (len(self._history) * 0.7)

        if sustained:
            cpu = snap.process.cpu_percent
            r = Recommendation(
                severity=Severity.WARNING,
                key="cpu_sustained",
                title="Sustained High CPU — Check background tasks",
                detail=f"Lightroom has used {cpu:.0f}%+ CPU for an extended period. "
                       f"This is often background preview rendering, catalog optimisation, "
                       f"or face detection running silently.",
                action="In Lightroom: Library menu → Previews → Stop Rendering Previews. "
                       "Also check Library → Find All Missing Photos (triggers a background scan). "
                       "If in Develop module, disable GPU acceleration temporarily: "
                       "Preferences → Performance → uncheck 'Use GPU for image processing'.",
                timestamp=snap.timestamp,
            )
            if "cpu_sustained" not in self._active:
                recs.append(r)
            else:
                self._active["cpu_sustained"] = r
        return recs

    def _check_thermal(self, snap: CombinedSnapshot) -> List[Recommendation]:
        recs = []
        pressure = snap.thermal.thermal_pressure

        if pressure in ("serious", "critical"):
            severity = Severity.CRITICAL if pressure == "critical" else Severity.WARNING
            r = Recommendation(
                severity=severity,
                key="thermal",
                title=f"Thermal Throttling — {pressure.capitalize()}",
                detail=f"macOS reports thermal pressure: {pressure}. "
                       f"Your CPU and GPU are being throttled to reduce heat. "
                       f"On a 2017 MBP this significantly impacts export and develop speed.",
                action="Stop intensive operations and let the machine cool (5–10 min). "
                       "Elevate the laptop for airflow. Avoid exporting large batches in one go. "
                       "If this is recurring, consider cleaning the fan vents.",
                timestamp=snap.timestamp,
            )
            if "thermal" not in self._active:
                recs.append(r)
            else:
                self._active["thermal"] = r
        return recs

    def _check_disk(self, snap: CombinedSnapshot) -> List[Recommendation]:
        recs = []
        write = snap.disk.write_mb_s
        if write >= self.DISK_WRITE_WARN_MB:
            r = Recommendation(
                severity=Severity.WARNING,
                key="disk_write",
                title="Heavy Disk Writes Detected",
                detail=f"Disk write rate at {write:.1f} MB/s. "
                       f"Sustained heavy writes can slow Lightroom catalog saves, "
                       f"export, and preview cache writes — especially on an aging 2017 SSD.",
                action="Check if an export or preview build is running. "
                       "In Lightroom: Preferences → Performance → move Camera Raw cache "
                       "to your fastest available drive. Avoid running Time Machine during sessions.",
                timestamp=snap.timestamp,
            )
            if "disk_write" not in self._active:
                recs.append(r)
            else:
                self._active["disk_write"] = r
        return recs

    def _check_gpu(self, snap: CombinedSnapshot) -> List[Recommendation]:
        recs = []
        current_gpu = snap.gpu.active_gpu

        # GPU switch detected mid-session
        if self._last_gpu and self._last_gpu != current_gpu and self._last_gpu != "Unknown":
            r = Recommendation(
                severity=Severity.WARNING,
                key="gpu_switch",
                title="GPU Switched Mid-Session",
                detail=f"GPU changed from '{self._last_gpu}' → '{current_gpu}'. "
                       f"macOS automatic graphics switching can cause Lightroom stutters and "
                       f"temporary freezes when the GPU handoff occurs.",
                action="Go to System Preferences → Battery → uncheck 'Automatic graphics switching'. "
                       "This forces the Radeon Pro 555 (your better GPU) to stay active. "
                       "Note: this will reduce battery life.",
                timestamp=snap.timestamp,
            )
            recs.append(r)
            self._active["gpu_switch"] = r

        # Warn if running on integrated GPU only
        if current_gpu and "Intel" in current_gpu and "Radeon" not in current_gpu:
            r = Recommendation(
                severity=Severity.WARNING,
                key="gpu_integrated",
                title="Using Integrated GPU Only",
                detail=f"Lightroom is running on the Intel HD Graphics 630 (integrated). "
                       f"Your Radeon Pro 555 is significantly faster for Develop module operations, "
                       f"lens correction, and GPU-accelerated effects.",
                action="System Preferences → Battery → uncheck 'Automatic graphics switching'. "
                       "Then restart Lightroom. The Radeon should activate within a few minutes of use.",
                timestamp=snap.timestamp,
            )
            if "gpu_integrated" not in self._active:
                recs.append(r)

        self._last_gpu = current_gpu
        return recs

    def _resolve_stale(self, snap: CombinedSnapshot):
        """Remove recommendations whose conditions have cleared."""
        to_remove = []

        # RAM resolved
        pct = (snap.system.memory_used_mb / self.RAM_TOTAL_MB) * 100
        if pct < self.RAM_WARN_PCT:
            to_remove += ["ram_warning", "ram_critical"]
        elif pct < self.RAM_CRIT_PCT:
            to_remove.append("ram_critical")

        # Swap resolved
        if snap.system.swap_used_mb < self.SWAP_WARN_MB:
            to_remove.append("swap_active")

        # CPU resolved
        high_count = sum(
            1 for s in self._history
            if s.process and s.process.cpu_percent >= self.CPU_SPIKE_PCT
        )
        if len(self._history) > 5 and high_count < (len(self._history) * 0.7):
            to_remove.append("cpu_sustained")

        # Thermal resolved
        if snap.thermal.thermal_pressure not in ("serious", "critical"):
            to_remove.append("thermal")

        # Disk resolved
        if snap.disk.write_mb_s < self.DISK_WRITE_WARN_MB:
            to_remove.append("disk_write")

        # GPU integrated resolved (switched back to discrete)
        if snap.gpu.active_gpu and "Radeon" in snap.gpu.active_gpu:
            to_remove.append("gpu_integrated")

        for key in to_remove:
            self._active.pop(key, None)
