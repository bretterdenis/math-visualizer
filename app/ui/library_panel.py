"""Sidebar library: a collapsible list with a "Combined" group followed by topic groups."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.backend.library import FunctionEntry, Topic
from app.ui.latex import set_latex_or_text


class LibraryPanel(QWidget):
    entry_selected = Signal(object)  # FunctionEntry
    delete_confirmed = Signal(str)  # entry id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._toggle = QPushButton("Library ▸")
        self._toggle.setStyleSheet("text-align: left; font-weight: 600;")
        self._toggle.clicked.connect(self._on_toggle)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toggle)
        layout.addWidget(self._body)

    def _on_toggle(self) -> None:
        showing = self._body.isHidden()
        self._body.setVisible(showing)
        self._toggle.setText("Library ▾" if showing else "Library ▸")

    def set_library(self, topics: list[Topic], combined: list[FunctionEntry]) -> None:
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        if not topics and not combined:
            empty = QLabel("No saved functions yet.")
            self._body_layout.addWidget(empty)
            return
        if combined:
            self._body_layout.addWidget(self._group("Combined", combined))
        for topic in topics:
            self._body_layout.addWidget(self._group(topic.name, topic.functions))

    # ------------------------------------------------------------ builders

    def _group(self, name: str, functions: list[FunctionEntry]) -> QWidget:
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)

        listing = QWidget()
        listing_layout = QVBoxLayout(listing)
        listing_layout.setContentsMargins(12, 0, 0, 0)
        listing.hide()

        def label(open_: bool) -> str:
            return f"{name} ({len(functions)}) {'▾' if open_ else '▸'}"

        header = QPushButton(label(False))
        header.setStyleSheet("text-align: left;")

        def toggle() -> None:
            showing = listing.isHidden()
            listing.setVisible(showing)
            header.setText(label(showing))

        header.clicked.connect(toggle)

        for fn in functions:
            listing_layout.addWidget(self._entry(fn))

        layout.addWidget(header)
        layout.addWidget(listing)
        return group

    def _entry(self, fn: FunctionEntry) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)

        text_column = QVBoxLayout()
        title = QPushButton(fn.title or "(untitled)")
        title.setObjectName("flatButton")
        title.setStyleSheet("font-weight: 600;")
        title.clicked.connect(lambda _checked=False, entry=fn: self.entry_selected.emit(entry))
        subtitle = QLabel()
        set_latex_or_text(subtitle, fn.subtitle or "")
        text_column.addWidget(title)
        text_column.addWidget(subtitle)

        delete = QPushButton("✕")
        delete.setObjectName("flatButton")
        delete.setToolTip("Delete from library")
        delete.clicked.connect(lambda _checked=False, entry=fn: self._confirm_delete(entry))

        row_layout.addLayout(text_column, 1)
        row_layout.addWidget(delete)
        return row

    def _confirm_delete(self, fn: FunctionEntry) -> None:
        answer = QMessageBox.question(
            self,
            "Delete entry",
            f'Delete "{fn.title or fn.id}" from the library?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_confirmed.emit(fn.id)
