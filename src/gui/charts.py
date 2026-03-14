"""
charts.py
Real-time scrolling charts using pyqtgraph.
Shows LR CPU, system RAM, disk I/O over time.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import numpy as np
from typing import List

from ..monitor.session import CombinedSnapshot
from ..data.events import EventTag

pg.setConfigOption("background", "#1e1e2e")
pg.setConfigOption("foreground", "#cdd6f4")

CHART_HEIGHT = 150
MAX_POINTS = 300

COLORS = {
    "lr_cpu": "#89b4fa",       # blue
    "sys_cpu": "#a6e3a1",      # green
    "lr_ram": "#cba6f7",       # mauve
    "sys_ram": "#f38ba8",      # red
    "disk_read": "#94e2d5",    # teal
    "disk_write": "#fab387",   # peach
}


def _make_plot(title: str, y_label: str, y_max: float = 100):
    pw = pg.PlotWidget(title=title)
    pw.setFixedHeight(CHART_HEIGHT)
    pw.setLabel("left", y_label)
    pw.setLabel("bottom", "time (samples)")
    pw.showGrid(x=True, y=True, alpha=0.2)
    pw.setYRange(0, y_max)
    pw.getPlotItem().titleLabel.setText(
        f'<span style="color:#89b4fa;font-size:12pt;font-weight:bold">{title}</span>'
    )
    return pw


class ChartsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._data: dict[str, list] = {k: [] for k in COLORS}

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # CPU chart
        self.cpu_plot = _make_plot("CPU Usage", "%", y_max=105)
        self.lr_cpu_line = self.cpu_plot.plot(pen=pg.mkPen(COLORS["lr_cpu"], width=2),
                                               name="LR CPU")
        self.sys_cpu_line = self.cpu_plot.plot(pen=pg.mkPen(COLORS["sys_cpu"], width=2),
                                                name="System CPU")
        cpu_legend = self.cpu_plot.addLegend(offset=(10, 10))

        # RAM chart
        self.ram_plot = _make_plot("Memory Usage", "MB", y_max=16384)
        self.lr_ram_line = self.ram_plot.plot(pen=pg.mkPen(COLORS["lr_ram"], width=2),
                                               name="LR RAM (RSS)")
        self.sys_ram_line = self.ram_plot.plot(pen=pg.mkPen(COLORS["sys_ram"], width=2),
                                                name="System RAM Used")
        ram_legend = self.ram_plot.addLegend(offset=(10, 10))

        # Disk I/O chart
        self.disk_plot = _make_plot("Disk I/O", "MB/s", y_max=200)
        self.disk_read_line = self.disk_plot.plot(pen=pg.mkPen(COLORS["disk_read"], width=2),
                                                    name="Read")
        self.disk_write_line = self.disk_plot.plot(pen=pg.mkPen(COLORS["disk_write"], width=2),
                                                     name="Write")
        disk_legend = self.disk_plot.addLegend(offset=(10, 10))

        layout.addWidget(self.cpu_plot)
        layout.addWidget(self.ram_plot)
        layout.addWidget(self.disk_plot)

    def update_tags(self, tags: List[EventTag], total_samples: int = 0):
        """Draw vertical marker lines on all charts for each event tag."""
        for plot in [self.cpu_plot, self.ram_plot, self.disk_plot]:
            for item in list(plot.items):
                if getattr(item, "_is_event_tag", False):
                    plot.removeItem(item)

        # Chart x-axis starts at max(0, total_samples - MAX_POINTS)
        window_start = max(0, total_samples - MAX_POINTS)

        for tag in tags:
            if tag.snapshot_index is None:
                continue
            # Convert absolute snapshot index to chart-relative x position
            x = tag.snapshot_index - window_start
            if x < 0:
                continue  # Tag is outside the visible window
            color = tag.color
            for plot in [self.cpu_plot, self.ram_plot, self.disk_plot]:
                line = pg.InfiniteLine(
                    pos=x,
                    angle=90,
                    pen=pg.mkPen(color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine),
                    label=tag.operation.value,
                    labelOpts={
                        "position": 0.90,
                        "color": color,
                        "fill": "#1e1e2e",
                        "border": color,
                    }
                )
                line._is_event_tag = True
                plot.addItem(line)

    def update(self, history: List[CombinedSnapshot]):
        if not history:
            return

        # Rebuild rolling arrays (capped at MAX_POINTS)
        recent = history[-MAX_POINTS:]
        x = list(range(len(recent)))

        lr_cpu = [s.process.cpu_percent if s.process else 0 for s in recent]
        sys_cpu = [s.system.cpu_percent_total for s in recent]
        lr_ram = [s.process.memory_rss_mb if s.process else 0 for s in recent]
        sys_ram = [s.system.memory_used_mb for s in recent]
        disk_r = [s.disk.read_bytes_per_sec / 1e6 for s in recent]
        disk_w = [s.disk.write_bytes_per_sec / 1e6 for s in recent]

        self.lr_cpu_line.setData(x, lr_cpu)
        self.sys_cpu_line.setData(x, sys_cpu)
        self.lr_ram_line.setData(x, lr_ram)
        self.sys_ram_line.setData(x, sys_ram)
        self.disk_read_line.setData(x, disk_r)
        self.disk_write_line.setData(x, disk_w)

        # Auto-scale disk Y axis
        max_disk = max(max(disk_r + disk_w, default=1), 1)
        self.disk_plot.setYRange(0, max_disk * 1.2)

        # Auto-scale RAM Y axis
        max_ram = max(max(lr_ram + sys_ram, default=1000), 1000)
        self.ram_plot.setYRange(0, max_ram * 1.15)
