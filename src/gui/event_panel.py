"""
event_panel.py
UI panel for logging Lightroom operation events during a monitoring session.
Sits as a tab in the main window.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QGroupBox, QSizePolicy, QFrame,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ..data.events import LROperation, EventTag, OPERATION_ICONS, OPERATION_COLORS

PANEL_STYLE = """
QPushButton.opBtn {
    border-radius: 8px;
    padding: 10px 8px;
    font-size: 13px;
    font-weight: bold;
    border: none;
    text-align: center;
}
QListWidget {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    color: #cdd6f4;
    font-size: 12px;
}
QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #2a2a3e;
}
QListWidget::item:selected {
    background: #313244;
}
QLineEdit {
    background: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}
"""

OP_BUTTON_TEMPLATE = """
    QPushButton {{
        background-color: {bg};
        color: #1e1e2e;
        border-radius: 8px;
        padding: 10px 6px;
        font-size: 12px;
        font-weight: bold;
        border: none;
    }}
    QPushButton:hover {{
        background-color: {hover};
    }}
    QPushButton:disabled {{
        background-color: #313244;
        color: #585b70;
    }}
"""


def _lighten(hex_color: str, amount: int = 20) -> str:
    """Simple hex color lightener for hover states."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = min(255, r + amount)
    g = min(255, g + amount)
    b = min(255, b + amount)
    return f"#{r:02x}{g:02x}{b:02x}"


class EventPanel(QWidget):
    """Panel for tagging LR operations during a live session."""

    tag_added = pyqtSignal(EventTag)
    tag_deleted = pyqtSignal(int)  # tag id

    def __init__(self):
        super().__init__()
        self._event_store = None
        self._snapshot_count_ref = None  # callable that returns current snapshot count
        self._tags: list[EventTag] = []
        self._op_buttons: dict[LROperation, QPushButton] = {}
        self._build_ui()
        self.set_active(False)

    def set_event_store(self, store, snapshot_count_fn):
        self._event_store = store
        self._snapshot_count_ref = snapshot_count_fn
        self._tags.clear()
        self.tag_list.clear()

    def set_active(self, active: bool):
        for btn in self._op_buttons.values():
            btn.setEnabled(active)
        self.note_input.setEnabled(active)
        if not active:
            self.status_label.setText("Start monitoring to enable event tagging.")
        else:
            self.status_label.setText("Click an operation button when you start it in Lightroom.")

    def _build_ui(self):
        self.setStyleSheet(PANEL_STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # --- Status ---
        self.status_label = QLabel("Start monitoring to enable event tagging.")
        self.status_label.setStyleSheet("color: #6c7086; font-size: 12px; padding: 4px;")
        root.addWidget(self.status_label)

        # --- Operation buttons ---
        ops_box = QGroupBox("Tag a Lightroom Operation")
        ops_layout = QGridLayout(ops_box)
        ops_layout.setSpacing(8)

        ops = list(LROperation)
        for i, op in enumerate(ops):
            icon = OPERATION_ICONS[op]
            color = OPERATION_COLORS[op]
            btn = QPushButton(f"{icon}\n{op.value}")
            btn.setFixedHeight(65)
            btn.setStyleSheet(OP_BUTTON_TEMPLATE.format(
                bg=color, hover=_lighten(color)
            ))
            btn.clicked.connect(lambda checked, o=op: self._tag_operation(o))
            self._op_buttons[op] = btn
            ops_layout.addWidget(btn, i // 3, i % 3)

        root.addWidget(ops_box)

        # --- Note input ---
        note_box = QGroupBox("Optional Note")
        note_layout = QHBoxLayout(note_box)
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText(
            "e.g. '200 RAW files', 'catalog 45GB', 'full 1:1 previews'..."
        )
        self.note_input.returnPressed.connect(
            lambda: self._tag_operation(LROperation.CUSTOM)
        )
        note_layout.addWidget(self.note_input)
        root.addWidget(note_box)

        # --- Event log ---
        log_box = QGroupBox("Session Event Log")
        log_layout = QVBoxLayout(log_box)

        self.tag_list = QListWidget()
        self.tag_list.setMinimumHeight(200)

        delete_btn = QPushButton("Remove Selected Tag")
        delete_btn.setFixedWidth(180)
        delete_btn.clicked.connect(self._delete_selected)

        log_layout.addWidget(self.tag_list)
        log_layout.addWidget(delete_btn, alignment=Qt.AlignmentFlag.AlignRight)
        root.addWidget(log_box)
        root.addStretch()

    def _tag_operation(self, operation: LROperation):
        if not self._event_store:
            return

        note = self.note_input.text().strip()
        snapshot_idx = self._snapshot_count_ref() if self._snapshot_count_ref else None

        tag = self._event_store.add_tag(operation, note=note, snapshot_index=snapshot_idx)
        self._tags.append(tag)
        self.note_input.clear()

        # Add to list widget
        item = QListWidgetItem(f"  {tag.time_str}   {tag.label}")
        item.setData(Qt.ItemDataRole.UserRole, tag.id)
        item.setForeground(QColor(tag.color))
        self.tag_list.insertItem(0, item)  # newest on top

        self.tag_added.emit(tag)

    def _delete_selected(self):
        selected = self.tag_list.selectedItems()
        if not selected:
            return
        item = selected[0]
        tag_id = item.data(Qt.ItemDataRole.UserRole)
        if self._event_store:
            self._event_store.delete_tag(tag_id)
        self.tag_list.takeItem(self.tag_list.row(item))
        self._tags = [t for t in self._tags if t.id != tag_id]
        self.tag_deleted.emit(tag_id)

    def get_tags(self) -> list[EventTag]:
        return list(self._tags)
