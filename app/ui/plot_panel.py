"""Plot panel: compact header (title, formula, buttons), topic/save bar, and the interactive plot.

The matplotlib canvas is embedded with FigureCanvasQTAgg, so 2D zoom/pan and 3D rotation come
from matplotlib directly. The navigation toolbar is hidden until the Toolbar button shows it, so
the plot takes the remaining space. The panel itself does not scroll; only the canvas is sized to
the available space.
"""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.backend.plot_eval import compute_2d, compute_3d, variable_names
from app.ui.latex import set_latex_or_text

BG = "#1a1b26"
BG_PANEL = "#16161e"
BORDER = "#2a2b3a"
TEXT = "#e6e6e6"


class PlotPanel(QWidget):
    add_function_toggled = Signal(bool)
    save_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.title_label.setWordWrap(True)
        self.subtitle_label = QLabel()
        self.subtitle_label.setWordWrap(True)

        self.add_button = QPushButton("+ Add function")
        self.add_button.setCheckable(True)
        self.add_button.setToolTip("Add another function to this plot")
        self.add_button.toggled.connect(self.add_function_toggled)

        self.description_button = QPushButton("Description ▸")
        self.description_button.clicked.connect(self._toggle_description)
        self._description_text = ""

        self.toolbar_button = QPushButton("Toolbar")
        self.toolbar_button.setCheckable(True)
        self.toolbar_button.setToolTip("Show zoom, pan and save controls")

        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.hide()

        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)

        header = QHBoxLayout()
        header.addLayout(titles, 1)
        header.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(self.description_button, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(self.toolbar_button, 0, Qt.AlignmentFlag.AlignTop)

        self.topic_label = QLabel("Topic:")
        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("Topic name")
        self.save_button = QPushButton("Save to library")
        self.save_button.clicked.connect(self._on_save_clicked)
        self.topic_bar = QWidget()
        topic_row = QHBoxLayout(self.topic_bar)
        topic_row.setContentsMargins(0, 0, 0, 0)
        topic_row.addWidget(self.topic_label)
        topic_row.addWidget(self.topic_input, 1)
        topic_row.addWidget(self.save_button)

        self.figure = Figure(figsize=(6, 5))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.hide()
        self.toolbar_button.toggled.connect(self.toolbar.setVisible)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self.description_label)
        layout.addWidget(self.topic_bar)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)

        self.clear()

    # ------------------------------------------------------------ public API

    def clear(self) -> None:
        self.title_label.setText("")
        self.subtitle_label.clear()
        self._description_text = ""
        self.description_label.clear()
        self.description_label.hide()
        self.description_button.hide()
        self.add_button.hide()
        self.add_button.setChecked(False)
        self.topic_bar.hide()
        self.figure.clear()
        self.canvas.draw_idle()

    def show_spec(self, spec: dict) -> None:
        self.title_label.setText(spec.get("title") or "")
        set_latex_or_text(self.subtitle_label, spec.get("subtitle") or "")

        self._description_text = spec.get("description") or ""
        self.description_label.hide()
        self.description_label.setText(self._description_text)
        self.description_button.setText("Description ▸")
        self.description_button.setVisible(bool(self._description_text))

        self.add_button.show()
        self.add_button.setChecked(False)

        combined = spec.get("combined") is True
        self.topic_label.setVisible(not combined)
        self.topic_input.setVisible(not combined)
        self.topic_input.setText(spec.get("suggested_topic") or "")
        self.topic_bar.show()

        self._draw(spec)

    def set_add_mode(self, on: bool) -> None:
        self.add_button.blockSignals(True)
        self.add_button.setChecked(on)
        self.add_button.blockSignals(False)

    # ------------------------------------------------------------ internals

    def _toggle_description(self) -> None:
        showing = self.description_label.isHidden()
        self.description_label.setVisible(showing)
        self.description_button.setText("Description ▾" if showing else "Description ▸")

    def _on_save_clicked(self) -> None:
        self.save_requested.emit(self.topic_input.text().strip())

    def _draw(self, spec: dict) -> None:
        self.figure.clear()
        self.figure.set_facecolor(BG)
        # Constrained layout keeps tick labels inside the canvas while letting the axes
        # use nearly all of it.
        self.figure.set_layout_engine("constrained")
        self.figure.get_layout_engine().set(w_pad=0.02, h_pad=0.02)
        x_name, y_name = variable_names(spec)
        if spec.get("kind") == "3d":
            self._draw_3d(spec, x_name, y_name)
        else:
            self._draw_2d(spec, x_name)
        self.canvas.draw_idle()

    def _draw_2d(self, spec: dict, x_name: str) -> None:
        data = compute_2d(spec)
        ax = self.figure.add_subplot(111)
        for curve in data.curves:
            ax.plot(data.xs, curve.ys, label=curve.label or None)
        ax.set_xlabel(x_name)
        ax.set_ylabel("y")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True, alpha=0.3)
        _style_axes(ax)
        if data.curves:
            _style_legend(ax.legend(loc="best"))

    def _draw_3d(self, spec: dict, x_name: str, y_name: str) -> None:
        data = compute_3d(spec)
        ax = self.figure.add_subplot(111, projection="3d")
        handles = []
        for surface in data.surfaces:
            zs = np.ma.masked_invalid(surface.zs)
            ax.plot_surface(data.X, data.Y, zs, color=surface.color, linewidth=0, antialiased=True)
            handles.append(Patch(color=surface.color, label=surface.label))
        ax.set_xlabel(x_name)
        ax.set_ylabel(y_name)
        ax.set_zlabel("z")
        ax.set_box_aspect((1, 1, 0.85))
        _style_axes(ax)
        if handles:
            _style_legend(ax.legend(handles=handles, loc="upper left"))


def _style_axes(ax) -> None:
    ax.set_facecolor(BG_PANEL)
    ax.tick_params(colors=TEXT)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    if hasattr(ax, "zaxis"):
        ax.zaxis.label.set_color(TEXT)
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.pane.set_facecolor(BG_PANEL)
    for spine in ax.spines.values():
        spine.set_color(BORDER)


def _style_legend(legend) -> None:
    legend.get_frame().set_facecolor(BG_PANEL)
    legend.get_frame().set_edgecolor(BORDER)
    for text in legend.get_texts():
        text.set_color(TEXT)
