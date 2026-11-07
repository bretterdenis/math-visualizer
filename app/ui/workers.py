"""Background thread for Claude API calls so the window stays responsive."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.backend.session import Session


class AskThread(QThread):
    succeeded = Signal(object)  # dict: {"type": "plot"|"text", "data": ...}
    failed = Signal(str)

    def __init__(self, session: Session, prompt: str, parent=None) -> None:
        super().__init__(parent)
        self._session = session
        self._prompt = prompt

    def run(self) -> None:
        try:
            result = self._session.ask(self._prompt)
        except Exception as exc:  # ClaudeError and anything unexpected
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)
