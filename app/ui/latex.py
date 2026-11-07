"""Renders LaTeX snippets to pixmaps with matplotlib's mathtext, falling back to plain text.

Only mathtext's supported subset of LaTeX is rendered. Anything it cannot parse (or a missing
backend) leaves the label showing the raw source as plain text.
"""

from __future__ import annotations

import io
from typing import Optional

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

# matplotlib's PNG output has an opaque white background, so the formula is drawn in dark ink
# and shows as a light formula card on the dark theme.
MATH_INK = "#1a1b26"
RENDER_DPI = 144


def render_latex_pixmap(source: str) -> Optional[QPixmap]:
    """Typesets ``source`` (LaTeX, without delimiters) as a PNG pixmap, or None on failure."""
    try:
        from matplotlib.mathtext import math_to_image

        text = source if "$" in source else f"${source}$"
        buffer = io.BytesIO()
        math_to_image(text, buffer, dpi=RENDER_DPI, format="png", color=MATH_INK)
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
