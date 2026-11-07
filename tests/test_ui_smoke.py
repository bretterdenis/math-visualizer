"""Offscreen smoke test of the Qt window. Skipped automatically when PySide6/matplotlib are absent.

This only checks that the window builds and the plot/combine wiring runs without exceptions.
It does not verify visual layout or interactive behaviour.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

try:
    from PySide6.QtWidgets import QApplication

    from app.backend.session import Session
    from app.ui.main_window import MainWindow

    QT_AVAILABLE = True
    QT_IMPORT_ERROR = ""
except ImportError as exc:  # pragma: no cover - environment dependent
    QT_AVAILABLE = False
    QT_IMPORT_ERROR = str(exc)

SINE = {
    "kind": "2d",
    "title": "Sine",
    "subtitle": "f(x) = \\sin(x)",
    "description": "A sine wave.",
    "suggested_topic": "Trig",
    "variables": ["x"],
    "domain": {"xMin": -10, "xMax": 10},
    "traces": [{"expr": "sin(x)", "label": "sin"}],
}
COSINE = {**SINE, "title": "Cosine", "traces": [{"expr": "cos(x)", "label": "cos"}]}
SURFACE = {
    "kind": "3d",
    "title": "Paraboloid",
    "subtitle": "z = x^2 + y^2",
    "description": "",
    "suggested_topic": "Surfaces",
    "variables": ["x", "y"],
    "domain": {"xMin": -2, "xMax": 2, "yMin": -2, "yMax": 2},
    "traces": [{"expr": "x^2 + y^2", "label": "paraboloid"}],
}


@unittest.skipUnless(QT_AVAILABLE, f"Qt/matplotlib not importable: {QT_IMPORT_ERROR if not QT_AVAILABLE else ''}")
class MainWindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._dir = Path(tempfile.mkdtemp(prefix="mathviz-ui-"))
        session = Session(library_path=self._dir / "library.json", api_key="test-key")
        self.window = MainWindow(session)

    def tearDown(self):
        self.window.close()
        shutil.rmtree(self._dir, ignore_errors=True)

    def test_plot_2d_then_combine_same_kind(self):
        self.window._combining_pending = False
        self.window._on_ask_succeeded({"type": "plot", "data": SINE})
        self.assertEqual(self.window.current_spec["title"], "Sine")
        self.window._set_add_mode(True)
        self.window._combining_pending = True
        self.window._on_ask_succeeded({"type": "plot", "data": COSINE})
        self.assertEqual(self.window.current_spec["title"], "Sine + Cosine")
        self.assertTrue(self.window.current_spec["combined"])

    def test_combining_mismatched_kind_keeps_current_plot(self):
        self.window._on_ask_succeeded({"type": "plot", "data": SINE})
        self.window._combining_pending = True
        self.window._on_ask_succeeded({"type": "plot", "data": SURFACE})
        self.assertEqual(self.window.current_spec["title"], "Sine")

    def test_3d_plot_renders(self):
        self.window._on_ask_succeeded({"type": "plot", "data": SURFACE})
        self.assertEqual(self.window.current_spec["kind"], "3d")

    def test_save_and_library_refresh(self):
        self.window._on_ask_succeeded({"type": "plot", "data": SINE})
        self.window._on_save("Trig")
        topics = self.window.session.list_topics()
        self.assertEqual([t.name for t in topics], ["Trig"])
        self.assertEqual(len(topics[0].functions), 1)

    def test_reset_clears_plot_and_spec(self):
        self.window._on_ask_succeeded({"type": "plot", "data": SINE})
        self.window._on_reset()
        self.assertIsNone(self.window.current_spec)


if __name__ == "__main__":
    unittest.main()
