"""Session: conversation history and library wiring, with the Claude transport faked."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.backend.claude import ClaudeError
from app.backend.library import FunctionEntry
from app.backend.session import Session

PLOT = {
    "kind": "2d",
    "title": "Sine",
    "subtitle": "f(x) = \\sin(x)",
    "description": "",
    "suggested_topic": "Trig",
    "variables": ["x"],
    "domain": {"xMin": -10, "xMax": 10},
    "traces": [{"expr": "sin(x)"}],
}


def transport_returning(status, payload):
    raw = json.dumps(payload).encode("utf-8")
    return lambda url, headers, body: (status, raw)


def plot_payload():
    return {"content": [{"type": "tool_use", "id": "t", "name": "render_plot", "input": PLOT}]}


class SessionTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = Path(tempfile.mkdtemp(prefix="mathviz-session-"))
        self.library_path = self._dir / "library.json"

    def tearDown(self):
        shutil.rmtree(self._dir, ignore_errors=True)

    def session(self, transport=None, api_key="test-key"):
        return Session(library_path=self.library_path, api_key=api_key, transport=transport)


class ChatTests(SessionTestCase):
    def test_no_key_raises_without_touching_history(self):
        s = self.session(api_key="")
        with self.assertRaisesRegex(ClaudeError, "No API key set"):
            s.ask("plot x")
        self.assertEqual(s.history, [])

    def test_plot_reply_records_tool_use_and_result(self):
        s = self.session(transport_returning(200, plot_payload()))
        result = s.ask("plot sin(x)")
        self.assertEqual(result, {"type": "plot", "data": PLOT})
        self.assertEqual(len(s.history), 3)
        self.assertEqual(s.history[0], {"role": "user", "content": "plot sin(x)"})
        self.assertEqual(s.history[1]["content"][0]["type"], "tool_use")
        self.assertEqual(s.history[1]["content"][0]["id"], "render_plot_call_1")
        self.assertEqual(s.history[2]["content"][0]["tool_use_id"], "render_plot_call_1")

    def test_text_reply_is_recorded_as_assistant_message(self):
        s = self.session(transport_returning(200, {"content": [{"type": "text", "text": "Which function?"}]}))
        self.assertEqual(s.ask("hmm"), {"type": "text", "data": "Which function?"})
        self.assertEqual(s.history[-1], {"role": "assistant", "content": "Which function?"})

    def test_failed_request_removes_user_message_and_propagates_error(self):
        s = self.session(transport_returning(529, {"error": {"message": "overloaded_error"}}))
        with self.assertRaisesRegex(ClaudeError, "overloaded_error"):
            s.ask("plot x")
        self.assertEqual(s.history, [])

    def test_reset_clears_history(self):
        s = self.session(transport_returning(200, plot_payload()))
        s.ask("plot")
        s.reset_conversation()
        self.assertEqual(s.history, [])

    def test_set_api_key_rejects_blank(self):
        s = self.session(api_key="")
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            s.set_api_key("   ")


class LibraryWiringTests(SessionTestCase):
    def test_save_list_and_delete_through_session(self):
        s = self.session()
        s.save_function("Trig", FunctionEntry.from_plot_spec(PLOT, combined=False))
        s.save_function("", FunctionEntry.from_plot_spec({**PLOT, "combined": True}, combined=True))
        self.assertEqual([t.name for t in s.list_topics()], ["Trig"])
        combined = s.list_combined()
        self.assertEqual(len(combined), 1)

        reloaded = Session(library_path=self.library_path, api_key="x")
        self.assertEqual(len(reloaded.list_combined()), 1)
        reloaded.delete_function(combined[0].id)
        self.assertEqual(Session(library_path=self.library_path, api_key="x").list_combined(), [])


if __name__ == "__main__":
    unittest.main()
