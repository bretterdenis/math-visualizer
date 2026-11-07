"""Main window: sidebar (chat + library, scrolls on its own) and the plot panel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.backend.combine import can_combine, combine_specs
from app.backend.library import FunctionEntry
from app.backend.session import Session
from app.ui.chat_panel import ChatPanel
from app.ui.library_panel import LibraryPanel
from app.ui.api_key_dialog import ApiKeyDialog
from app.ui.plot_panel import PlotPanel
from app.ui.workers import AskThread

ICON_PATH = Path(__file__).resolve().parents[2] / "icon.png"
SIDEBAR_WIDTH = 360


def describe_spec(spec: dict) -> str:
    return spec.get("title") or ", ".join(t.get("expr", "") for t in spec.get("traces") or [])


class MainWindow(QMainWindow):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session
        self.current_spec: dict | None = None
        self.adding = False
        self._combining_pending = False
        self._worker: AskThread | None = None

        self.setWindowTitle("Math Visualizer")
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(1280, 800)

        self.chat = ChatPanel()
        self.library = LibraryPanel()
        self.plot = PlotPanel()

        sidebar_content = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_content)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        heading = QLabel("<b>Math Visualizer</b>")
        heading.setStyleSheet("font-size: 16px;")
        sidebar_layout.addWidget(heading)
        sidebar_layout.addWidget(self.chat, 1)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        sidebar_layout.addWidget(separator)
        sidebar_layout.addWidget(self.library)
        sidebar_layout.addStretch(0)

        sidebar = QScrollArea()
        sidebar.setWidget(sidebar_content)
        sidebar.setWidgetResizable(True)
        sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar.setFrameShape(QFrame.Shape.NoFrame)

        plot_holder = QWidget()
        plot_layout = QHBoxLayout(plot_holder)
        plot_layout.setContentsMargins(16, 16, 16, 16)
        plot_layout.addWidget(self.plot)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(plot_holder, 1)
        self.setCentralWidget(root)

        self.chat.prompt_submitted.connect(self._on_prompt)
        self.chat.reset_requested.connect(self._on_reset)
        self.plot.add_function_toggled.connect(self._on_add_toggled)
        self.plot.save_requested.connect(self._on_save)
        self.library.entry_selected.connect(self._on_library_selected)
        self.library.delete_confirmed.connect(self._on_delete)

        self.plot.clear()
        self.refresh_library()

    # ------------------------------------------------------------ startup

    def prompt_api_key(self) -> None:
        ApiKeyDialog(self.session, self).exec()

    # ------------------------------------------------------------ chat flow

    def _set_add_mode(self, on: bool) -> None:
        self.adding = on
        self.plot.set_add_mode(on)
        self.chat.set_add_mode(on)

    def _on_add_toggled(self, on: bool) -> None:
        self._set_add_mode(on)
        if on:
            self.chat.focus_input()

    def _on_prompt(self, prompt: str) -> None:
        self._combining_pending = self.adding and self.current_spec is not None
        self._set_add_mode(False)
        self.chat.add_message("user", prompt)
        self.chat.set_busy(True)
        self._worker = AskThread(self.session, prompt, self)
        self._worker.succeeded.connect(self._on_ask_succeeded)
        self._worker.failed.connect(self._on_ask_failed)
        self._worker.finished.connect(self._on_ask_finished)
        self._worker.start()

    def _on_ask_finished(self) -> None:
        self.chat.set_busy(False)
        self.chat.focus_input()

    def _on_ask_failed(self, message: str) -> None:
        self.chat.add_message("error", message)

    def _on_ask_succeeded(self, result: dict) -> None:
        data = result["data"]
        if result["type"] != "plot":
            self.chat.add_message("assistant", data)
            return

        if not self._combining_pending:
            self.chat.add_message("assistant", f"Plotted: {describe_spec(data)}")
            self._show_spec(data)
            return

        if not can_combine(self.current_spec, data):
            message = (
                "A 3D function can only be added to a 3D plot."
                if data.get("kind") == "3d"
                else "A 2D function can only be added to a 2D plot."
            )
            self.chat.add_message("error", message)
            return

        combined = combine_specs(self.current_spec, data)
        if combined is self.current_spec:
            self.chat.add_message("assistant", "The response did not contain a function to add.")
            return
        self.chat.add_message("assistant", f"Added: {describe_spec(data)}")
        self._show_spec(combined)

    def _on_reset(self) -> None:
        self.session.reset_conversation()
        self.chat.clear_log()
        self.current_spec = None
        self._set_add_mode(False)
        self.plot.clear()

    # ------------------------------------------------------------ plot / library

    def _show_spec(self, spec: dict) -> None:
        self.current_spec = spec
        self.plot.show_spec(spec)

    def _on_save(self, topic: str) -> None:
        if self.current_spec is None:
            return
        combined = self.current_spec.get("combined") is True
        if not topic and not combined:
            return
        entry = FunctionEntry.from_plot_spec(self.current_spec, combined)
        try:
            self.session.save_function(topic, entry)
        except Exception as exc:
            self.chat.add_message("error", str(exc))
            return
        self.refresh_library()

    def _on_library_selected(self, entry: FunctionEntry) -> None:
        self._show_spec(entry.to_plot_spec())

    def _on_delete(self, entry_id: str) -> None:
        try:
            self.session.delete_function(entry_id)
        except Exception as exc:
            self.chat.add_message("error", str(exc))
            return
        self.refresh_library()

    def refresh_library(self) -> None:
        self.library.set_library(self.session.list_topics(), self.session.list_combined())
