"""Chat column: the History log, prompt input, Plot and New conversation controls."""

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

_MESSAGE_STYLES = {
    "user": "",
    "assistant": "",
    "error": "color:#f7768e;",
}
_MESSAGE_BLOCK = '<div style="margin:0px 0px 14px 0px;">{label}<div style="{style}">{body}</div></div>'
_USER_LABEL = '<div style="color:#7aa2f7; font-weight:600; font-size:12px; margin:0px 0px 2px 0px;">You</div>'


def format_message_html(role: str, text: str) -> str:
    """Returns one history entry: no background, the body escaped, a label only for the user."""
    label = _USER_LABEL if role == "user" else ""
    style = _MESSAGE_STYLES.get(role, _MESSAGE_STYLES["assistant"])
    body = html.escape(text).replace("\n", "<br>")
    return _MESSAGE_BLOCK.format(label=label, style=style, body=body)


class ChatPanel(QWidget):
    prompt_submitted = Signal(str)
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.history_label = QLabel("History")
        self.history_label.setStyleSheet("font-size:13px; font-weight:600; color:#9aa5ce;")

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
        layout.addWidget(self.history_label)
        layout.addWidget(self.log, 1)
        layout.addWidget(self.status)
        layout.addLayout(prompt_row)
        layout.addWidget(self.reset_button)

    # ------------------------------------------------------------ public API

    def add_message(self, role: str, text: str) -> None:
        self.log.append(format_message_html(role, text))
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
