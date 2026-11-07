"""Modal dialog asking for the Anthropic API key on first run."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.backend.session import Session


class ApiKeyDialog(QDialog):
    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self.setWindowTitle("Anthropic API Key")
        self.setModal(True)

        layout = QVBoxLayout(self)
        heading = QLabel("<b>Anthropic API Key</b>")
        info = QLabel(
            "Enter your Anthropic API key. It's stored locally in your user config folder, "
            "never sent anywhere except api.anthropic.com."
        )
        info.setWordWrap(True)

        self._input = QLineEdit()
        self._input.setEchoMode(QLineEdit.EchoMode.Password)
        self._input.setPlaceholderText("sk-ant-...")
        self._input.returnPressed.connect(self._save)

        self._error = QLabel()
        self._error.setStyleSheet("color: #f7768e;")
        self._error.setWordWrap(True)
        self._error.hide()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save = QPushButton("Save")
        save.clicked.connect(self._save)
        buttons.addWidget(save)

        layout.addWidget(heading)
        layout.addWidget(info)
        layout.addWidget(self._input)
        layout.addWidget(self._error)
        layout.addLayout(buttons)
        self.resize(460, 0)

    def _save(self) -> None:
        key = self._input.text().strip()
        if not key:
            return
        try:
            self._session.set_api_key(key)
        except Exception as exc:  # ConfigError, ValueError
            self._error.setText(str(exc))
            self._error.show()
            return
        self.accept()
