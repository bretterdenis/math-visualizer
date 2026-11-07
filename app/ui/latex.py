"""Renders LaTeX snippets to pixmaps with matplotlib's mathtext, falling back to plain text.

Only mathtext's supported subset of LaTeX is rendered. Anything it cannot parse (or a missing
backend) leaves the label showing the raw source as plain text.
"""

from __future__ import annotations

import io
from typing import Optional

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

# Light ink matching the UI text colour. The PNG has a transparent background (not matplotlib's
# default white), so the formula sits directly on the dark theme.
MATH_INK = "#e6e6e6"
RENDER_DPI = 144


def render_latex_pixmap(source: str) -> Optional[QPixmap]:
    """Typesets ``source`` (LaTeX, without delimiters) as a transparent PNG pixmap, or None."""
    try:
        from matplotlib.figure import Figure

        text = source if "$" in source else f"${source}$"
        figure = Figure(figsize=(1, 1), dpi=RENDER_DPI, facecolor="none")
        figure.text(0, 0, text, color=MATH_INK, fontsize=13)
        buffer = io.BytesIO()
        figure.savefig(
            buffer,
            format="png",
            dpi=RENDER_DPI,
            transparent=True,
            bbox_inches="tight",
            pad_inches=0.02,
        )
        pixmap = QPixmap()
        if not pixmap.loadFromData(buffer.getvalue(), "PNG"):
            return None
        return pixmap
    except Exception:  # unsupported LaTeX, missing backend, etc.
        return None


def set_latex_or_text(label: QLabel, source: str) -> None:
    """Shows ``source`` as typeset math when possible, otherwise as plain text."""
    label.clear()
    if not source:
        return
    pixmap = render_latex_pixmap(source)
    if pixmap is not None and not pixmap.isNull():
        label.setPixmap(pixmap)
    else:
        label.setText(source)
