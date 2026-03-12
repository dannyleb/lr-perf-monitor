"""
main_window.py
Main application window. Dark-themed dashboard for LR Classic performance monitoring.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStatusBar, QTabWidget,
    QGroupBox, QGridLayout, QComboBox, QFileDialog,
    QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QPalette

from .dashboard import DashboardWidget
from .charts import ChartsWidget
from .event_panel import EventPanel
from ..monitor.session import MonitorSession, CombinedSnapshot
from ..data.logger import SessionLogger
from ..data.exporter import export_csv, export_pdf

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background: #1e1e2e;
}
QTabBar::tab {
    background: #181825;
    color: #a6adc8;
    padding: 8px 20px;
    border: none;
    font-size: 13px;
}
QTabBar::tab:selected {
    background: #313244;
    color: #cdd6f4;
    border-bottom: 2px solid #89b4fa;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #45475a;
}
QPushButton:disabled {
    color: #585b70;
}
QPushButton#startBtn {
    background-color: #a6e3a1;
    color: #1e1e2e;
    font-weight: bold;
}
QPushButton#startBtn:hover {
    background-color: #94e2d5;
}
QPushButton#stopBtn {
    background-color: #f38ba8;
    color: #1e1e2e;
    font-weight: bold;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 12px;
    padding: 8px;
    font-weight: bold;
    color: #89b4fa;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QStatusBar {
    background: #181825;
    color: #6c7086;
    font-size: 12px;
}
QLabel#lrStatus {
    font-size: 14px;
    font-weight: bold;
    padding: 4px 10px;
    border-radius: 5px;
}
QComboBox {
    background: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LR Perf Monitor — Lightroom Classic Performance")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(DARK_STYLE)

        self._session: MonitorSession | None = None
        self._logger: SessionLogger | None = None
        self._snapshot_count = 0

        self._build_ui()
        self._setup_timer()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        # --- Top bar ---
        top = QHBoxLayout()

        title = QLabel("LR Perf Monitor")
        title.setFont(QFont("SF Pro Display", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #89b4fa;")

        self.lr_status = QLabel("● Lightroom: Not Detected")
        self.lr_status.setObjectName("lrStatus")
        self.lr_status.setStyleSheet("color: #f38ba8; background: #2a1a1f;")

        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["1s", "2s", "5s", "10s"])
        self.interval_combo.setCurrentIndex(1)
        self.interval_combo.setFixedWidth(80)
        interval_label = QLabel("Interval:")
        interval_label.setStyleSheet("color: #a6adc8;")

        self.start_btn = QPushButton("▶  Start Monitoring")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setFixedWidth(170)
        self.start_btn.clicked.connect(self.start_monitoring)

        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setFixedWidth(100)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_monitoring)

        self.export_btn = QPushButton("⬇  Export Report")
        self.export_btn.setFixedWidth(140)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_report)

        top.addWidget(title)
        top.addSpacing(20)
        top.addWidget(self.lr_status)
        top.addStretch()
        top.addWidget(interval_label)
        top.addWidget(self.interval_combo)
        top.addSpacing(10)
        top.addWidget(self.start_btn)
        top.addWidget(self.stop_btn)
        top.addWidget(self.export_btn)
        root.addLayout(top)

        # --- Tabs ---
        self.tabs = QTabWidget()
        self.dashboard = DashboardWidget()
        self.charts = ChartsWidget()
        self.event_panel = EventPanel()
        self.event_panel.tag_added.connect(self._on_tag_added)
        self.tabs.addTab(self.dashboard, "📊  Live Dashboard")
        self.tabs.addTab(self.charts, "📈  Charts")
        self.tabs.addTab(self.event_panel, "🏷  Event Tags")
        root.addWidget(self.tabs)

        # --- Status bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Click Start to begin monitoring.")

        self.sample_label = QLabel("Samples: 0")
        self.sample_label.setStyleSheet("color: #6c7086; padding-right: 10px;")
        self.status_bar.addPermanentWidget(self.sample_label)

    def _setup_timer(self):
        # Poll for UI updates at 1Hz regardless of sample interval
        self._ui_timer = QTimer()
        self._ui_timer.setInterval(1000)
        self._ui_timer.timeout.connect(self._refresh_ui)

    def _get_interval(self) -> float:
        mapping = {"1s": 1.0, "2s": 2.0, "5s": 5.0, "10s": 10.0}
        return mapping.get(self.interval_combo.currentText(), 2.0)

    def start_monitoring(self):
        interval = self._get_interval()
        self._logger = SessionLogger()
        self._session = MonitorSession(
            interval_sec=interval,
            on_snapshot=self._on_snapshot,
        )
        self._session.start()
        self._ui_timer.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.interval_combo.setEnabled(False)
        self.export_btn.setEnabled(False)
        self._snapshot_count = 0
        self.event_panel.set_event_store(
            self._logger.event_store,
            lambda: self._snapshot_count
        )
        self.event_panel.set_active(True)
        self.status_bar.showMessage(f"Monitoring active — {interval}s interval")

    def stop_monitoring(self):
        if self._session:
            self._session.stop()
        if self._logger:
            self._logger.close()
        self._ui_timer.stop()
        self.event_panel.set_active(False)

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.interval_combo.setEnabled(True)
        self.export_btn.setEnabled(self._snapshot_count > 0)
        self.status_bar.showMessage(
            f"Stopped. {self._snapshot_count} samples collected. "
            f"Log: {self._logger.db_path if self._logger else 'N/A'}"
        )

    def _on_snapshot(self, snap: CombinedSnapshot):
        """Called from monitor thread — do NOT touch Qt widgets here."""
        self._snapshot_count += 1
        if self._logger:
            self._logger.log(snap)

    def _refresh_ui(self):
        if not self._session:
            return
        history = self._session.get_history()
        if not history:
            return

        latest = history[-1]

        # Update LR status indicator
        if latest.lr_running:
            self.lr_status.setText(
                f"● Lightroom: Running  PID {latest.process.pid}"
            )
            self.lr_status.setStyleSheet("color: #a6e3a1; background: #1a2e1a;")
        else:
            self.lr_status.setText("● Lightroom: Not Detected")
            self.lr_status.setStyleSheet("color: #f38ba8; background: #2a1a1f;")

        self.sample_label.setText(f"Samples: {self._snapshot_count}")
        self.dashboard.update(latest)
        self.charts.update(history)
        self.charts.update_tags(self.event_panel.get_tags())

    def _on_tag_added(self, tag):
        self.charts.update_tags(self.event_panel.get_tags())

    def export_report(self):
        if not self._logger:
            return
        rows = self._logger.get_all()
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilters(["PDF Report (*.pdf)", "CSV Data (*.csv)"])
        dialog.setDefaultSuffix("pdf")
        if dialog.exec():
            chosen = dialog.selectedFiles()[0]
            selected_filter = dialog.selectedNameFilter()
            session_name = self._logger.session_name
            if "CSV" in selected_filter:
                path = export_csv(rows, filename=chosen.split("/")[-1])
            else:
                path = export_pdf(rows, session_name=session_name,
                                  filename=chosen.split("/")[-1])
            QMessageBox.information(self, "Export Complete", f"Saved to:\n{path}")

    def closeEvent(self, event):
        self.stop_monitoring()
        super().closeEvent(event)
