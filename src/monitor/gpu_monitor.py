"""
gpu_monitor.py
GPU utilization monitoring for Intel Mac with dual GPU.
MacBook Pro 2017: Radeon Pro 555 (discrete) + Intel HD Graphics 630 (integrated).
Uses `system_profiler` and `ioreg` since no NVML on macOS.
"""

import subprocess
import re
import time
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class GPUInfo:
    name: str
    vendor: str
    vram_mb: int
    is_active: bool


@dataclass
class GPUSnapshot:
    timestamp: float
    active_gpu: str = "Unknown"
    gpus: List[GPUInfo] = field(default_factory=list)
    # Utilization via powermetrics (requires sudo)
    gpu_utilization_percent: Optional[float] = None
    gpu_power_watts: Optional[float] = None
    vram_used_mb: Optional[float] = None


def get_gpu_info() -> List[GPUInfo]:
    """List all GPUs via system_profiler."""
    gpus = []
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True, text=True, timeout=5
        )
        import json
        data = json.loads(result.stdout)
        displays = data.get("SPDisplaysDataType", [])
        for gpu in displays:
            name = gpu.get("sppci_model", "Unknown GPU")
            vendor = gpu.get("sppci_vendor", "Unknown")
            vram_str = gpu.get("spdisplays_vram", "0 MB")
            vram_mb = _parse_mb(vram_str)
            # "spdisplays_ndrvs" presence = display attached = active
            is_active = "spdisplays_ndrvs" in gpu
            gpus.append(GPUInfo(name=name, vendor=vendor, vram_mb=vram_mb, is_active=is_active))
    except Exception:
        pass
    return gpus


def _parse_mb(vram_str: str) -> int:
    match = re.search(r'(\d+)', vram_str)
    if match:
        val = int(match.group(1))
        if 'GB' in vram_str.upper():
            return val * 1024
        return val
    return 0


def get_gpu_utilization_powermetrics(sample_ms: int = 500) -> Optional[float]:
    """
    Get GPU busy % from powermetrics.
    Requires passwordless sudo. Returns None if unavailable.
    """
    try:
        result = subprocess.run(
            ["sudo", "-n", "powermetrics", "--samplers", "gpu_power",
             "-n", "1", "-i", str(sample_ms), "--format", "text"],
            capture_output=True, text=True, timeout=5
        )
        match = re.search(r'GPU\s+(?:Active|Busy):\s*([\d.]+)%', result.stdout, re.IGNORECASE)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return None


def get_gpu_snapshot() -> GPUSnapshot:
    snap = GPUSnapshot(timestamp=time.time())
    snap.gpus = get_gpu_info()

    # Determine active GPU
    active = [g for g in snap.gpus if g.is_active]
    if active:
        snap.active_gpu = active[0].name

    util = get_gpu_utilization_powermetrics()
    if util is not None:
        snap.gpu_utilization_percent = util

    return snap
