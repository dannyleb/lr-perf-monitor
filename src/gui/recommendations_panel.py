"""
recommendations_panel.py
Live recommendations panel. Displays active issues + session log.
Auto-updates from the DiagnosticsEngine.
"""

import time
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QPushButton, QSizePolicy,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ..data.diagnostics import Recommendation, Severity


# ── Colour palette (matches app dark theme) ──────────────────────────────── #
COLOURS = {
    Severity.OK:       {"bg": "#1e3a2a", "border": "#a6e3a1", "icon": "✅", "label": "OK"},
    Severity.WARNING:  {"bg": "#3a2e1e", "border": "#f9e2af", "icon": "⚠️", "label": "WARNING"},
    Severity.CRITICAL: {"bg": "#3a1e1e", "border": "#f38ba8", "icon": "🔴", "label": "CRITICAL"},
}

STATUS_IDLE    = {"bg": "#1e1e2e", "text": "#6c7086", "msg": "Start monitoring to see recommendations."}
STATUS_HEALTHY = {"bg": "#1e3a2a", "text": "#a6e3a1", "msg": "✅  All systems healthy — no issues detected."}


def _ts(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%-I:%M:%S %p")


class RecommendationCard(QFrame):
    def __init__(self, rec: Recommendation, parent=None):
        super().__init__(parent)
        c = COLOURS[rec.severity]
        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet(f"""
            RecommendationCard {{
                background-color: {c['bg']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 4px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header row: icon + title + timestamp
        header = QHBoxLayout()
        icon_lbl = QLabel(c["icon"])
        icon_lbl.setFixedWidth(24)
        title_lbl = QLabel(rec.title)
        title_lbl.setStyleSheet(f"color: {c['border']}; font-weight: bold; font-size: 12px; border: none; background: transparent;")
        title_lbl.setWordWrap(True)
        time_lbl = QLabel(_ts(rec.timestamp))
        time_lbl.setStyleSheet("color: #6c7086; font-size: 10px; border: none; background: transparent;")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(icon_lbl)
        header.addWidget(title_lbl, 1)
        header.addWidget(time_lbl)
        layout.addLayout(header)

        # Detail
        detail_lbl = QLabel(rec.detail)
        detail_lbl.setWordWrap(True)
        detail_lbl.setStyleSheet("color: #cdd6f4; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(detail_lbl)

        # Action
        action_header = QLabel("What to do:")
        action_header.setStyleSheet(f"color: {c['border']}; font-size: 10px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(action_header)

        action_lbl = QLabel(rec.action)
        action_lbl.setWordWrap(True)
        action_lbl.setStyleSheet("color: #a6adc8; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(action_lbl)


class RecommendationsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._monitoring = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── Header ────────────────────────────────────────────────────── #
        hdr = QHBoxLayout()
        title = QLabel("Live Recommendations")
        title.setStyleSheet("color: #89b4fa; font-size: 14px; font-weight: bold;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._clear_btn = QPushButton("Clear Log")
        self._clear_btn.setFixedHeight(26)
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px;
                padding: 0 10px; font-size: 11px;
            }
            QPushButton:hover { background: #45475a; }
        """)
        self._clear_btn.clicked.connect(self._on_clear)
        hdr.addWidget(self._clear_btn)
        root.addLayout(hdr)

        # ── Status banner ─────────────────────────────────────────────── #
        self._status_banner = QLabel(STATUS_IDLE["msg"])
        self._status_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_banner.setFixedHeight(36)
        self._status_banner.setStyleSheet(
            f"background: {STATUS_IDLE['bg']}; color: {STATUS_IDLE['text']}; "
            f"border-radius: 4px; font-size: 12px; font-weight: bold;"
        )
        root.addWidget(self._status_banner)

        # ── Active issues section ──────────────────────────────────────── #
        active_lbl = QLabel("Active Issues")
        active_lbl.setStyleSheet("color: #6c7086; font-size: 11px; font-weight: bold;")
        root.addWidget(active_lbl)

        self._active_scroll = QScrollArea()
        self._active_scroll.setWidgetResizable(True)
        self._active_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._active_scroll.setStyleSheet("background: transparent;")
        self._active_scroll.setMinimumHeight(160)
        self._active_scroll.setMaximumHeight(320)

        self._active_container = QWidget()
        self._active_layout = QVBoxLayout(self._active_container)
        self._active_layout.setContentsMargins(0, 0, 0, 0)
        self._active_layout.setSpacing(6)
        self._active_layout.addStretch()
        self._active_scroll.setWidget(self._active_container)
        root.addWidget(self._active_scroll)

        # ── Session log section ────────────────────────────────────────── #
        log_lbl = QLabel("Session Log")
        log_lbl.setStyleSheet("color: #6c7086; font-size: 11px; font-weight: bold;")
        root.addWidget(log_lbl)

        self._log_scroll = QScrollArea()
        self._log_scroll.setWidgetResizable(True)
        self._log_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._log_scroll.setStyleSheet("background: transparent;")

        self._log_container = QWidget()
        self._log_layout = QVBoxLayout(self._log_container)
        self._log_layout.setContentsMargins(0, 0, 0, 0)
        self._log_layout.setSpacing(4)
        self._log_layout.addStretch()
        self._log_scroll.setWidget(self._log_container)
        root.addWidget(self._log_scroll, 1)

        # Internal state
        self._log_entries: list[Recommendation] = []

    # ── Public API ────────────────────────────────────────────────────── #

    def set_monitoring(self, active: bool):
        self._monitoring = active
        if not active:
            self._set_banner(STATUS_IDLE)

    def update_active(self, active: list[Recommendation]):
        """Called every refresh tick with current active recommendations."""
        # Clear existing cards
        while self._active_layout.count() > 1:
            item = self._active_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._monitoring:
            self._set_banner(STATUS_IDLE)
            return

        if not active:
            self._set_banner(STATUS_HEALTHY)
        else:
            # Show worst severity in banner
            worst = max(active, key=lambda r: [Severity.OK, Severity.WARNING, Severity.CRITICAL].index(r.severity))
            c = COLOURS[worst.severity]
            self._status_banner.setText(f"{c['icon']}  {len(active)} issue(s) detected")
            self._status_banner.setStyleSheet(
                f"background: {c['bg']}; color: {c['border']}; "
                f"border-radius: 4px; font-size: 12px; font-weight: bold;"
            )
            for rec in active:
                card = RecommendationCard(rec)
                self._active_layout.insertWidget(self._active_layout.count() - 1, card)

    def add_log_entries(self, new_entries: list[Recommendation]):
        """Append new recommendations to the session log."""
        for rec in new_entries:
            if rec in self._log_entries:
                continue
            self._log_entries.append(rec)
            card = RecommendationCard(rec)
            self._log_layout.insertWidget(self._log_layout.count() - 1, card)

    # ── Internals ─────────────────────────────────────────────────────── #

    def _set_banner(self, style: dict):
        self._status_banner.setText(style["msg"])
        self._status_banner.setStyleSheet(
            f"background: {style['bg']}; color: {style['text']}; "
            f"border-radius: 4px; font-size: 12px; font-weight: bold;"
        )

    def _on_clear(self):
        self._log_entries.clear()
        while self._log_layout.count() > 1:
            item = self._log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
