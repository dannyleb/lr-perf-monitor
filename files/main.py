"""
main.py
Application entry point for LR Perf Monitor.
"""

import sys
import os

# Ensure src/ is on the path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LR Perf Monitor")
    app.setOrganizationName("dannyleb")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
