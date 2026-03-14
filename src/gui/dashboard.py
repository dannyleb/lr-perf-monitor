"""
dashboard.py
Live metrics dashboard — real-time stat cards for LR process + system.
"""

from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QVBoxLayout, QHBoxLayout,
    QLabel, QGroupBox, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..monitor.session import CombinedSnapshot
from ..monitor.disk_monitor import DiskMonitor


def _fmt_mb(val, suffix="MB"):
    if val is None:
        return "—"
    return f"{val:.0f} {suffix}"


def _fmt_pct(val):
    if val is None:
        return "—"
    return f"{val:.1f}%"


def _fmt_temp(val):
    if val is None:
        return "—"
    return f"{val:.0f}°C"


class StatCard(QFrame):
    """Single metric display card."""
    PRESSURE_COLORS = {
        "Normal": "#a6e3a1",
        "Fair": "#f9e2af",
        "Serious": "#fab387",
        "Critical": "#f38ba8",
        "Unknown": "#6c7086",
    }

    def __init__(self, label: str, unit: str = "", warn_threshold: float = None,
                 crit_threshold: float = None):
        super().__init__()
        self.label_text = label
        self.unit = unit
        self.warn_threshold = warn_threshold
        self.crit_threshold = crit_threshold

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            StatCard {
                background: #181825;
                border: 1px solid #313244;
                border-radius: 10px;
                padding: 4px;
            }
        """)
        self.setMinimumSize(140, 90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.label = QLabel(label)
        self.label.setStyleSheet("color: #6c7086; font-size: 11px; font-weight: bold;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.value_label = QLabel("—")
        self.value_label.setFont(QFont("SF Mono", 22, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #cdd6f4;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.sub_label = QLabel("")
        self.sub_label.setStyleSheet("color: #585b70; font-size: 11px;")

        layout.addWidget(self.label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.sub_label)

    def set_value(self, value_str: str, numeric: float = None, sub: str = ""):
        self.value_label.setText(value_str)
        self.sub_label.setText(sub)

        color = "#cdd6f4"
        if numeric is not None:
            if self.crit_threshold and numeric >= self.crit_threshold:
                color = "#f38ba8"
            elif self.warn_threshold and numeric >= self.warn_threshold:
                color = "#f9e2af"
            else:
                color = "#a6e3a1"
        self.value_label.setStyleSheet(f"color: {color};")

    def set_pressure(self, pressure: str):
        color = self.PRESSURE_COLORS.get(pressure, "#6c7086")
        self.value_label.setText(pressure)
        self.value_label.setStyleSheet(f"color: {color};")


class DashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(10)

        # --- LR Process Group ---
        lr_box = QGroupBox("Lightroom Classic Process")
        lr_layout = QHBoxLayout(lr_box)
        lr_layout.setSpacing(10)

        self.lr_cpu = StatCard("LR CPU", "%", warn_threshold=60, crit_threshold=90)
        self.lr_ram = StatCard("LR RAM", "MB", warn_threshold=8000, crit_threshold=12000)
        self.lr_threads = StatCard("Threads")
        self.lr_files = StatCard("Open Files")

        for w in [self.lr_cpu, self.lr_ram, self.lr_threads, self.lr_files]:
            lr_layout.addWidget(w)

        # --- System Group ---
        sys_box = QGroupBox("System Resources")
        sys_layout = QHBoxLayout(sys_box)
        sys_layout.setSpacing(10)

        self.sys_cpu = StatCard("System CPU", "%", warn_threshold=70, crit_threshold=90)
        self.sys_ram_used = StatCard("RAM Used", "MB", warn_threshold=13000, crit_threshold=15000)
        self.sys_ram_pct = StatCard("RAM %", "%", warn_threshold=80, crit_threshold=92)
        self.swap_used = StatCard("Swap", "MB", warn_threshold=1000, crit_threshold=4000)

        for w in [self.sys_cpu, self.sys_ram_used, self.sys_ram_pct, self.swap_used]:
            sys_layout.addWidget(w)

        # --- Disk Group ---
        disk_box = QGroupBox("Disk I/O")
        disk_layout = QHBoxLayout(disk_box)

        self.disk_read = StatCard("Read Speed")
        self.disk_write = StatCard("Write Speed")
        self.disk_free = StatCard("Disk Free", "GB")

        for w in [self.disk_read, self.disk_write, self.disk_free]:
            disk_layout.addWidget(w)

        # --- Thermal/GPU Group ---
        hw_box = QGroupBox("Thermal & GPU")
        hw_layout = QHBoxLayout(hw_box)

        self.thermal_pressure = StatCard("Thermal State")
        self.cpu_temp = StatCard("CPU Temp", "°C", warn_threshold=85, crit_threshold=100)
        self.gpu_temp = StatCard("GPU Temp", "°C", warn_threshold=80, crit_threshold=95)
        self.active_gpu = StatCard("Active GPU")

        for w in [self.thermal_pressure, self.cpu_temp, self.gpu_temp, self.active_gpu]:
            hw_layout.addWidget(w)

        root.addWidget(lr_box)
        root.addWidget(sys_box)
        root.addWidget(disk_box)
        root.addWidget(hw_box)
        root.addStretch()

    def update(self, snap: CombinedSnapshot):
        p = snap.process
        s = snap.system
        d = snap.disk
        t = snap.thermal
        g = snap.gpu

        # LR process
        if p:
            self.lr_cpu.set_value(f"{p.cpu_percent:.1f}%", p.cpu_percent)
            self.lr_ram.set_value(f"{p.memory_rss_mb:.0f}", p.memory_rss_mb, "MB RSS")
            self.lr_threads.set_value(str(p.num_threads))
            self.lr_files.set_value(
                str(p.num_open_files) if p.num_open_files >= 0 else "N/A"
            )
        else:
            for w in [self.lr_cpu, self.lr_ram, self.lr_threads, self.lr_files]:
                w.set_value("—")

        # System
        self.sys_cpu.set_value(f"{s.cpu_percent_total:.1f}%", s.cpu_percent_total)
        self.sys_ram_used.set_value(f"{s.memory_used_mb:.0f}", s.memory_used_mb, "MB")
        self.sys_ram_pct.set_value(f"{s.memory_percent:.1f}%", s.memory_percent)
        self.swap_used.set_value(f"{s.swap_used_mb:.0f}", s.swap_used_mb, "MB swap")

        # Disk
        self.disk_read.set_value(DiskMonitor.format_bytes(d.read_bytes_per_sec))
        self.disk_write.set_value(DiskMonitor.format_bytes(d.write_bytes_per_sec))
        self.disk_free.set_value(f"{d.disk_free_gb:.1f}", sub="GB free")

        # Thermal
        self.thermal_pressure.set_pressure(t.thermal_pressure)
        self.cpu_temp.set_value(
            _fmt_temp(t.cpu_die_temp_c), t.cpu_die_temp_c,
            sub="requires sudo" if t.cpu_die_temp_c is None else ""
        )
        self.gpu_temp.set_value(
            _fmt_temp(t.gpu_temp_c), t.gpu_temp_c,
            sub="requires sudo" if t.gpu_temp_c is None else ""
        )

        # GPU
        gpu_name = g.active_gpu or "Unknown"
        if len(gpu_name) > 16:
            gpu_name = gpu_name[:14] + "…"
        self.active_gpu.set_value(gpu_name)
