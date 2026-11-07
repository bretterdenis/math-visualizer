"""Application state shared by the UI: API key, conversation history and the library.

This is the Python equivalent of the Rust ``AppState`` + Tauri command handlers, without any
Qt dependency so it can be unit-tested directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.backend import claude, config, library
from app.backend.claude import ClaudeError, PlotReply, TextReply, Transport
from app.backend.library import FunctionEntry, Library, LibraryError, Topic


class Session:
    def __init__(
        self,
        library_path: Optional[Path] = None,
        api_key: Optional[str] = None,
        transport: Optional[Transport] = None,
    ) -> None:
        self.api_key: Optional[str] = api_key if api_key is not None else config.load_api_key()
        self.history: list[dict] = []
        self.transport = transport
        self.library_path: Optional[Path] = library_path or library.default_library_path()
        self.library: Library = (
            library.load_library(self.library_path) if self.library_path else Library()
        )

    # ----------------------------------------------------------- API key

    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def set_api_key(self, key: str) -> None:
        key = key.strip()
        if not key:
            raise ValueError("API key cannot be empty")
        config.save_api_key(key)
        self.api_key = key

    # ----------------------------------------------------------- chat

    def reset_conversation(self) -> None:
        self.history.clear()

    def ask(self, prompt: str) -> dict:
        """Sends a prompt. Returns ``{"type": "plot", "data": spec}`` or ``{"type": "text", ...}``.

        On failure the user message is removed from the history and ClaudeError is raised.
        """
        if not self.api_key:
            raise ClaudeError("No API key set")

        self.history.append({"role": "user", "content": prompt})
        snapshot = list(self.history)
        try:
            reply = claude.ask(self.api_key, snapshot, transport=self.transport)
        except Exception:
            self.history.pop()
            raise

        if isinstance(reply, PlotReply):
            tool_id = f"render_plot_call_{len(self.history)}"
            self.history.append({
                "role": "assistant",
                "content": [{"type": "tool_use", "id": tool_id, "name": "render_plot", "input": reply.data}],
            })
            self.history.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": "Plot rendered."}],
            })
            return {"type": "plot", "data": reply.data}

        assert isinstance(reply, TextReply)
        self.history.append({"role": "assistant", "content": reply.text})
        return {"type": "text", "data": reply.text}

    # ----------------------------------------------------------- library

    def _require_path(self) -> Path:
        if self.library_path is None:
            raise LibraryError("Could not resolve config directory")
        return self.library_path

    def list_topics(self) -> list[Topic]:
        return library.list_topics(self.library)

    def list_combined(self) -> list[FunctionEntry]:
        return library.list_combined(self.library)

    def save_function(self, topic: str, entry: FunctionEntry) -> None:
        library.save_function(self.library, topic, entry, self._require_path())

    def move_function(self, entry_id: str, new_topic: str) -> None:
        library.move_function(self.library, entry_id, new_topic, self._require_path())

    def delete_function(self, entry_id: str) -> None:
        library.delete_function(self.library, entry_id, self._require_path())

    def rename_topic(self, old_name: str, new_name: str) -> None:
        library.rename_topic(self.library, old_name, new_name, self._require_path())
