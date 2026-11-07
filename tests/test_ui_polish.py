"""Offscreen checks for the UI polish: history HTML, transparent formulas, and plot layout.

Skipped automatically when PySide6/matplotlib are absent.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

try:
    from PySide6.QtWidgets import QApplication, QLabel

    from app.ui.chat_panel import format_message_html
    from app.ui.latex import render_latex_pixmap, set_latex_or_text
    from app.ui.plot_panel import PlotPanel

    QT_AVAILABLE = True
    QT_IMPORT_ERROR = ""
except ImportError as exc:  # pragma: no cover - environment dependent
    QT_AVAILABLE = False
    QT_IMPORT_ERROR = str(exc)

SINE = {
    "kind": "2d",
    "title": "Sine",
    "subtitle": "f(x) = \\sin(x)",
    "description": "",
    "suggested_topic": "Trig",
    "variables": ["x"],
    "domain": {"xMin": -10, "xMax": 10},
    "traces": [{"expr": "sin(x)", "label": "sin"}],
}


class HistoryHtmlTests(unittest.TestCase):
    @unittest.skipUnless(QT_AVAILABLE, f"Qt/matplotlib not importable: {QT_IMPORT_ERROR}")
    def test_messages_have_no_background(self):
        for role in ("user", "assistant", "error"):
            with self.subTest(role=role):
                self.assertNotIn("background", format_message_html(role, "hello"))

    @unittest.skipUnless(QT_AVAILABLE, f"Qt/matplotlib not importable: {QT_IMPORT_ERROR}")
    def test_message_content_is_escaped(self):
        html = format_message_html("assistant", "<script>x</script> & y\nz")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;x&lt;/script&gt; &amp; y<br>z", html)

    @unittest.skipUnless(QT_AVAILABLE, f"Qt/matplotlib not importable: {QT_IMPORT_ERROR}")
    def test_user_messages_are_labelled_you(self):
        self.assertIn(">You</div>", format_message_html("user", "plot sin"))
        self.assertNotIn(">You</div>", format_message_html("assistant", "hi"))


@unittest.skipUnless(QT_AVAILABLE, f"Qt/matplotlib not importable: {QT_IMPORT_ERROR if not QT_AVAILABLE else ''}")
class FormulaRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_formula_pixmap_has_transparent_background(self):
        pixmap = render_latex_pixmap("f(x) = \\sin(x)")
        self.assertIsNotNone(pixmap)
        image = pixmap.toImage()
        self.assertTrue(image.hasAlphaChannel())
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)

    def test_invalid_latex_falls_back_to_plain_text(self):
        self.assertIsNone(render_latex_pixmap("\\notacommand{"))
        label = QLabel()
        set_latex_or_text(label, "\\notacommand{")
        self.assertEqual(label.text(), "\\notacommand{")


@unittest.skipUnless(QT_AVAILABLE, f"Qt/matplotlib not importable: {QT_IMPORT_ERROR if not QT_AVAILABLE else ''}")
class PlotLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = PlotPanel()
        self.panel.resize(900, 700)
        self.panel.show()
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()

    def test_toolbar_hidden_by_default_and_toggleable(self):
        self.assertTrue(self.panel.toolbar.isHidden())
        self.panel.toolbar_button.click()
        self.assertFalse(self.panel.toolbar.isHidden())

    def test_2d_axes_fill_canvas(self):
        self.panel.show_spec(SINE)
        self.panel.canvas.draw()
        x0, y0, width, height = self.panel.figure.axes[0].get_position().bounds
        self.assertLessEqual(x0, 0.15)
        self.assertLessEqual(y0, 0.15)
        self.assertGreaterEqual(x0 + width, 0.9)
        self.assertGreaterEqual(y0 + height, 0.9)


if __name__ == "__main__":
    unittest.main()
