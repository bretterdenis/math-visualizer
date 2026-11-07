"""Dark theme matching the palette of the former Tauri app (style.css)."""

DARK_STYLESHEET = """
QWidget {
    background-color: #1a1b26;
    color: #e6e6e6;
}
QScrollArea {
    background-color: #16161e;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background-color: #16161e;
}
QTextBrowser, QLineEdit {
    background-color: #16161e;
    border: 1px solid #2a2b3a;
    border-radius: 6px;
    padding: 4px;
    color: #e6e6e6;
}
QTextBrowser {
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 14px;
    padding: 8px;
}
QPushButton {
    background-color: #24253a;
    border: 1px solid #2a2b3a;
    border-radius: 6px;
    padding: 5px 10px;
}
QPushButton:hover {
    background-color: #2d3250;
}
QPushButton:checked {
    background-color: #3d59a1;
}
QPushButton:disabled {
    color: #6b7089;
}
QPushButton#flatButton {
    background: transparent;
    border: none;
    padding: 2px 4px;
    text-align: left;
}
QPushButton#flatButton:hover {
    color: #7aa2f7;
}
QLabel {
    background: transparent;
}
QFrame[frameShape="4"] {
    color: #2a2b3a;
}
QToolBar {
    background-color: #c0caf5;
    border: none;
}
QToolBar QToolButton {
    background: transparent;
    border: none;
}
QMessageBox {
    background-color: #1a1b26;
}
"""
