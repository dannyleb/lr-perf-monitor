"""
thermal_monitor.py
Reads CPU temperatures and thermal state on Intel Mac / macOS Ventura.
Uses `powermetrics` (requires sudo) with fallback to `ioreg` heuristics.
"""

import subprocess
import re
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ThermalSnapshot:
    timestamp: float
    cpu_die_temp_c: Optional[float] = None
    gpu_temp_c: Optional[float] = None
    thermal_pressure: str = "Unknown"   # Normal / Fair / Serious / Critical
    cpu_power_watts: Optional[float] = None
    gpu_power_watts: Optional[float] = None
    throttling_detected: bool = False
    source: str = "unknown"


def get_thermal_pressure_ioreg() -> str:
    """
    Read macOS thermal pressure level via IOKit.
    Returns: Normal | Fair | Serious | Critical
    """
    try:
        result = subprocess.run(
            ["ioreg", "-r", "-c", "IOPlatformExpertDevice", "-d", "3"],
            capture_output=True, text=True, timeout=3
        )
        match = re.search(r'"IOPlatformThermalProfile"\s*=\s*"([^"]+)"', result.stdout)
        if match:
            return match.group(1)

        # Fallback: check thermalPressureLevel
        result2 = subprocess.run(
            ["sysctl", "-n", "kern.thermal_level"],
            capture_output=True, text=True, timeout=2
        )
        level = result2.stdout.strip()
        mapping = {"0": "Normal", "1": "Fair", "2": "Serious", "3": "Critical"}
        return mapping.get(level, "Normal")
    except Exception:
        return "Unknown"


def get_powermetrics_snapshot(sample_ms: int = 500) -> ThermalSnapshot:
    """
    Run powermetrics for one sample to get CPU/GPU power and temps.
    Requires: sudo — will fail gracefully if not available.
    """
    snap = ThermalSnapshot(timestamp=time.time(), source="powermetrics")
    try:
        result = subprocess.run(
            [
                "sudo", "-n", "powermetrics",
                "--samplers", "cpu_power,gpu_power,thermal",
                "-n", "1",
                "-i", str(sample_ms),
                "--format", "text",
            ],
            capture_output=True, text=True, timeout=5
        )
        out = result.stdout

        # CPU die temp
        temp_match = re.search(r'CPU die temperature:\s*([\d.]+)\s*C', out)
        if temp_match:
            snap.cpu_die_temp_c = float(temp_match.group(1))

        # GPU temp
        gpu_temp_match = re.search(r'GPU die temperature:\s*([\d.]+)\s*C', out)
        if gpu_temp_match:
            snap.gpu_temp_c = float(gpu_temp_match.group(1))

        # CPU power
        cpu_pwr = re.search(r'CPU Power:\s*([\d.]+)\s*mW', out)
        if cpu_pwr:
            snap.cpu_power_watts = float(cpu_pwr.group(1)) / 1000

        # GPU power
        gpu_pwr = re.search(r'GPU Power:\s*([\d.]+)\s*mW', out)
        if gpu_pwr:
            snap.gpu_power_watts = float(gpu_pwr.group(1)) / 1000

        # Throttling
        if re.search(r'thermal pressure.*(?:serious|critical)', out, re.IGNORECASE):
            snap.throttling_detected = True

        snap.thermal_pressure = get_thermal_pressure_ioreg()

    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        snap.source = "ioreg_fallback"
        snap.thermal_pressure = get_thermal_pressure_ioreg()
        snap.throttling_detected = snap.thermal_pressure in ("Serious", "Critical")

    return snap
