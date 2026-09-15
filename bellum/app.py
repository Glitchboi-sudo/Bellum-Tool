"""Arranque de la aplicación Qt."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Bellum Tool")
    app.setApplicationDisplayName("Bellum Tool")
    app.setOrganizationName("bellum")
    app.setDesktopFileName("bellum-tool")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
