"""Chat column: message log, prompt input, Plot and New conversation controls."""

from __future__ import annotations

import html

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

DEFAULT_PLACEHOLDER = "e.g. plot sin(x) * x from -10 to 10"
ADD_PLACEHOLDER = "Describe the function to add to this plot…"

_BUBBLE_STYLES = {
    "user": "background-color:#2d3250; margin:4px 0px 4px 40px;",
    "assistant": "background-color:#24252f; margin:4px 40px 4px 0px;",
    "error": "background-color:#3b2330; color:#f7768e; margin:4px 40px 4px 0px;",
}


class ChatPanel(QWidget):
    prompt_submitted = Signal(str)
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.log = QTextBrowser()
        self.log.setOpenExternalLinks(False)
        self.log.setMinimumHeight(260)

        self.status = QLabel("Thinking…")
        self.status.setStyleSheet("color:#9aa5ce;")
        self.status.hide()

        self.input = QLineEdit()
        self.input.setPlaceholderText(DEFAULT_PLACEHOLDER)
        self.input.setClearButtonEnabled(True)
        self.input.returnPressed.connect(self._on_submit)
        self.plot_button = QPushButton("Plot")
        self.plot_button.clicked.connect(lambda _checked=False: self._on_submit())

        prompt_row = QHBoxLayout()
        prompt_row.addWidget(self.input, 1)
        prompt_row.addWidget(self.plot_button)

        self.reset_button = QPushButton("New conversation")
        self.reset_button.clicked.connect(self.reset_requested)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.log, 1)
        layout.addWidget(self.status)
        layout.addLayout(prompt_row)
        layout.addWidget(self.reset_button)

    # ------------------------------------------------------------ public API

    def add_message(self, role: str, text: str) -> None:
        style = _BUBBLE_STYLES.get(role, _BUBBLE_STYLES["assistant"])
        body = html.escape(text).replace("\n", "<br>")
        self.log.append(f'<div style="{style} padding:6px;">{body}</div>')
        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self) -> None:
        self.log.clear()

    def set_busy(self, busy: bool) -> None:
        self.input.setEnabled(not busy)
        self.plot_button.setEnabled(not busy)
        self.reset_button.setEnabled(not busy)
        self.status.setVisible(busy)

    def set_add_mode(self, on: bool) -> None:
        self.input.setPlaceholderText(ADD_PLACEHOLDER if on else DEFAULT_PLACEHOLDER)

    def focus_input(self) -> None:
        self.input.setFocus()

    # ------------------------------------------------------------ internals

    def _on_submit(self) -> None:
        prompt = self.input.text().strip()
        if not prompt:
            return
        self.input.clear()
        self.prompt_submitted.emit(prompt)
