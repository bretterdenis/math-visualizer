"""Claude API request building and reply parsing, with the HTTP call mocked (port of claude.rs tests)."""

import json
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.backend import claude
from app.backend.claude import ClaudeError, PlotReply, TextReply, ask, parse_reply

HISTORY = [{"role": "user", "content": "plot sin(x)"}]


def fake_transport(status, payload, seen=None):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")

    def send(url, headers, body):
        if seen is not None:
            seen.update(url=url, headers=headers, body=json.loads(body.decode("utf-8")))
        return status, raw

    return send


SINE_PLOT = {
    "kind": "2d",
    "title": "Sine",
    "subtitle": "f(x) = \\sin(x)",
    "description": "A sine wave.",
    "suggested_topic": "Trigonometric functions",
    "variables": ["x"],
    "domain": {"xMin": -10, "xMax": 10},
    "traces": [{"expr": "sin(x)"}],
}


class ParseTests(unittest.TestCase):
    def test_tool_use_block_becomes_plot(self):
        payload = {"content": [{"type": "tool_use", "id": "t1", "name": "render_plot", "input": SINE_PLOT}]}
        reply = parse_reply(payload)
        self.assertIsInstance(reply, PlotReply)
        self.assertEqual(reply.data["title"], "Sine")
        self.assertEqual(reply.data["suggested_topic"], "Trigonometric functions")

    def test_text_block_becomes_text(self):
        reply = parse_reply({"content": [{"type": "text", "text": "What function would you like to plot?"}]})
        self.assertEqual(reply, TextReply("What function would you like to plot?"))

    def test_multiple_text_blocks_are_joined(self):
        reply = parse_reply({"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]})
        self.assertEqual(reply.text, "a\nb")

    def test_empty_content_falls_back_to_placeholder(self):
        self.assertEqual(parse_reply({"content": []}), TextReply("(no response)"))

    def test_missing_content_array_is_error(self):
        with self.assertRaisesRegex(ClaudeError, "no content array"):
            parse_reply({"foo": 1})

    def test_tool_use_wins_over_text(self):
        payload = {
            "content": [
                {"type": "text", "text": "Here you go"},
                {"type": "tool_use", "name": "render_plot", "input": SINE_PLOT},
            ]
        }
        self.assertIsInstance(parse_reply(payload), PlotReply)


class AskTests(unittest.TestCase):
    def test_request_has_model_tool_system_prompt_and_headers(self):
        seen = {}
        reply = ask("test-key", HISTORY, transport=fake_transport(200, {"content": []}, seen))
        self.assertEqual(reply, TextReply("(no response)"))
        self.assertEqual(seen["url"], "https://api.anthropic.com/v1/messages")
        self.assertEqual(seen["headers"]["x-api-key"], "test-key")
        self.assertEqual(seen["headers"]["anthropic-version"], "2023-06-01")
        body = seen["body"]
        self.assertEqual(body["model"], "claude-sonnet-5-5")
        self.assertEqual(body["max_tokens"], 1024)
        self.assertEqual(body["messages"], HISTORY)
        self.assertEqual(body["system"], claude.SYSTEM_PROMPT)
        self.assertEqual([t["name"] for t in body["tools"]], ["render_plot"])
        self.assertEqual(
            body["tools"][0]["input_schema"]["required"],
            ["kind", "title", "subtitle", "description", "suggested_topic", "variables", "domain", "traces"],
        )

    def test_plot_reply_through_transport(self):
        reply = ask("k", HISTORY, transport=fake_transport(200, {"content": [{"type": "tool_use", "name": "render_plot", "input": SINE_PLOT}]}))
        self.assertIsInstance(reply, PlotReply)

    def test_api_error_message_is_propagated(self):
        payload = {"error": {"message": "overloaded_error: try again later"}}
        with self.assertRaises(ClaudeError) as ctx:
            ask("k", HISTORY, transport=fake_transport(529, payload))
        self.assertIn("overloaded_error", str(ctx.exception))
        self.assertIn("529", str(ctx.exception))

    def test_api_error_without_message_says_unknown(self):
        with self.assertRaisesRegex(ClaudeError, "unknown error"):
            ask("k", HISTORY, transport=fake_transport(500, {"error": {}}))

    def test_unparseable_body_is_reported(self):
        with self.assertRaisesRegex(ClaudeError, "Could not parse Claude API response"):
            ask("k", HISTORY, transport=fake_transport(502, b"<html>bad gateway</html>"))


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        self.rfile.read(length)
        body = json.dumps({"content": [{"type": "text", "text": "pong"}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class LocalHttpTests(unittest.TestCase):
    """Exercises the real urllib transport against a local stand-in for the API."""

    def test_round_trip_over_real_http(self):
        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/v1/messages"
            self.assertEqual(ask("k", HISTORY, url=url), TextReply("pong"))
        finally:
            server.shutdown()
            server.server_close()

    def test_connection_failure_is_reported(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        with self.assertRaisesRegex(ClaudeError, "Request to Claude API failed"):
            ask("k", HISTORY, url=f"http://127.0.0.1:{port}/v1/messages")


if __name__ == "__main__":
    unittest.main()
