"""Anthropic Messages API client: request building and reply parsing (stdlib urllib only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional, Union

MODEL = "claude-sonnet-5-5"
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
TIMEOUT_SECONDS = 120

# transport(url, headers, body_bytes) -> (http_status, response_bytes)
Transport = Callable[[str, dict, bytes], tuple[int, bytes]]


class ClaudeError(Exception):
    """Any failure talking to the Claude API. The message is shown to the user."""


@dataclass
class PlotReply:
    data: dict


@dataclass
class TextReply:
    text: str


Reply = Union[PlotReply, TextReply]

PLOT_TOOL: dict = {
    "name": "render_plot",
    "description": "Render a mathematical function visualization. Call this whenever the user describes, asks for, or modifies a function to plot.",
    "input_schema": {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["2d", "3d"],
                "description": "2d for y = f(x), 3d for z = f(x, y) surfaces",
            },
            "title": {
                "type": "string",
                "description": "Short label for what the function is or resembles, e.g. 'Cubic function'",
            },
            "subtitle": {
                "type": "string",
                "description": "The function written as valid LaTeX, e.g. 'f(x) = x^3 - 3x'",
            },
            "description": {
                "type": "string",
                "description": "Longer explanatory text about the function; may contain inline LaTeX using \\(...\\) or $...$ delimiters",
            },
            "suggested_topic": {
                "type": "string",
                "description": "Best-guess category name for organizing this function in the user's library, e.g. 'Polynomial functions'. This is only a suggestion the user can override.",
            },
            "variables": {
                "type": "array",
                "items": {"type": "string"},
                "description": "['x'] for 2d, ['x', 'y'] for 3d",
            },
            "domain": {
                "type": "object",
                "properties": {
                    "xMin": {"type": "number"},
                    "xMax": {"type": "number"},
                    "yMin": {"type": "number"},
                    "yMax": {"type": "number"},
                },
                "required": ["xMin", "xMax"],
                "description": "yMin/yMax only required for kind=3d (range of the second variable)",
            },
            "traces": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "expr": {
                            "type": "string",
                            "description": "mathjs-compatible expression using the declared variables, e.g. 'sin(x)*exp(-x/10)' or 'sin(sqrt(x^2+y^2))'",
                        },
                        "label": {"type": "string"},
                    },
                    "required": ["expr"],
                },
                "description": "One or more functions to overlay (2d) or a single surface (3d)",
            },
        },
        "required": ["kind", "title", "subtitle", "description", "suggested_topic", "variables", "domain", "traces"],
    },
}

SYSTEM_PROMPT = (
    "You are a math visualization assistant embedded in a desktop app. "
    "When the user describes, requests, or modifies a mathematical function, call the "
    "render_plot tool with a valid specification. Use mathjs-compatible syntax in expressions "
    "(^ for power, standard function names like sin, cos, exp, log, sqrt, abs). Pick a sensible "
    "default domain (e.g. -10 to 10) unless the user specifies one or the function implies a "
    "natural range. For follow-up requests like 'zoom out' or 'add cos(x) too', adjust the "
    "previous plot accordingly rather than starting over, using the conversation history. "
    "If the request is ambiguous or not about plotting a function, ask a brief clarifying "
    "question in plain text instead of calling the tool. "
    "The 2d plot can only show one y value per x, so implicit or multi-valued relations "
    "(e.g. a circle x^2+y^2=r^2, or an ellipse) must be split into separate traces for each "
    "branch (e.g. 'sqrt(r^2-x^2)' and '-sqrt(r^2-x^2)' with the domain limited to [-r, r]) so "
    "the full curve is covered. The x and y axes are rendered with equal scale by default, so "
    "shapes like circles will appear geometrically correct. "
    "Every render_plot call must also include: title (a short label for what the function is or "
    "resembles), subtitle (the function written as valid LaTeX), description (longer explanatory "
    "text, which may use inline LaTeX with \\(...\\) or $...$ delimiters), and suggested_topic "
    "(your best-guess category name for organizing this function, e.g. 'Polynomial functions'). "
    "The user can edit or override suggested_topic before saving it to their library, so treat it "
    "as a helpful guess rather than a final answer."
)


def default_transport(url: str, headers: dict, body: bytes) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError) as exc:
        raise ClaudeError(f"Request to Claude API failed: {getattr(exc, 'reason', exc)}") from exc


def build_request_body(history: list[dict]) -> dict:
    return {
        "model": MODEL,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "tools": [PLOT_TOOL],
        "messages": history,
    }


def parse_reply(payload: object) -> Reply:
    """Turns a successful Messages API response payload into a PlotReply or TextReply."""
    if not isinstance(payload, dict):
        raise ClaudeError("Claude API response had no content array")
    content = payload.get("content")
    if not isinstance(content, list):
        raise ClaudeError("Claude API response had no content array")

    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "render_plot":
            data = block.get("input")
            return PlotReply(data if data is not None else {})

    text = "\n".join(
        block["text"]
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    )
    return TextReply(text if text else "(no response)")


def ask(
    api_key: str,
    history: list[dict],
    *,
    url: str = API_URL,
    transport: Optional[Transport] = None,
) -> Reply:
    """Sends the conversation to Claude and returns the parsed reply. Raises ClaudeError."""
    send = transport or default_transport
    headers = {
        "x-api-key": api_key,
        "anthropic-version": API_VERSION,
        "content-type": "application/json",
    }
    body = json.dumps(build_request_body(history), ensure_ascii=False).encode("utf-8")
    status, raw = send(url, headers, body)

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ClaudeError(f"Could not parse Claude API response: {exc}") from exc

    if not 200 <= status < 300:
        message = "unknown error"
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            candidate = payload["error"].get("message")
            if isinstance(candidate, str):
                message = candidate
        raise ClaudeError(f"Claude API error ({status}): {message}")

    return parse_reply(payload)
