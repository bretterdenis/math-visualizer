"""Entry point. Run from the repository root with: python3 -m app.main"""

from __future__ import annotations

import os
import sys

# Must be set before matplotlib picks a Qt binding.
os.environ.setdefault("QT_API", "pyside6")


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.backend.config import load_dotenv
    from app.backend.session import Session
    from app.ui.main_window import MainWindow
    from app.ui.theme import DARK_STYLESHEET

    load_dotenv()
    session = Session()

    app = QApplication(sys.argv)
    app.setApplicationName("Math Visualizer")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)
    window = MainWindow(session)
    window.show()
    if not session.has_api_key():
        window.prompt_api_key()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
