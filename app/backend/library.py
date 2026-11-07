"""Function library: data model, JSON file I/O, and the library operations.

File format is identical to the former Rust version (``library.json`` in the config folder):
``{"topics": [{"name", "functions": [entry...]}], "combined": [entry...]}`` where an entry has
id, title, subtitle, description, kind, variables, domain, traces, created_at and combined.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.backend.config import config_dir


class LibraryError(Exception):
    """A library operation failed (message is shown to the user)."""


@dataclass
class FunctionEntry:
    id: str
    title: str
    subtitle: str
    description: str
    kind: str
    variables: list
    domain: Any
    traces: Any
    created_at: str
    combined: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "kind": self.kind,
            "variables": self.variables,
            "domain": self.domain,
            "traces": self.traces,
            "created_at": self.created_at,
            "combined": self.combined,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FunctionEntry":
        return cls(
            id=data["id"],
            title=data["title"],
            subtitle=data["subtitle"],
            description=data["description"],
            kind=data["kind"],
            variables=data["variables"],
            domain=data["domain"],
            traces=data["traces"],
            created_at=data["created_at"],
            combined=bool(data.get("combined", False)),
        )

    def to_plot_spec(self) -> dict:
        """The plot-spec shape the UI renders (no suggested_topic, so no topic is prefilled)."""
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "kind": self.kind,
            "variables": self.variables,
            "domain": self.domain,
            "traces": self.traces,
            "combined": self.combined,
        }

    @classmethod
    def from_plot_spec(cls, spec: dict, combined: bool) -> "FunctionEntry":
        """Builds an entry (with blank id/created_at, filled in on save) from a plot spec."""
        return cls(
            id="",
            title=spec.get("title") or "",
            subtitle=spec.get("subtitle") or "",
            description=spec.get("description") or "",
            kind=spec.get("kind") or "2d",
            variables=spec.get("variables") or ["x"],
            domain=spec.get("domain") or {},
            traces=spec.get("traces") or [],
            created_at="",
            combined=combined,
        )


@dataclass
class Topic:
    name: str
    functions: list[FunctionEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "functions": [f.to_dict() for f in self.functions]}

    @classmethod
    def from_dict(cls, data: dict) -> "Topic":
        return cls(
            name=data["name"],
            functions=[FunctionEntry.from_dict(f) for f in data["functions"]],
        )


@dataclass
class Library:
    topics: list[Topic] = field(default_factory=list)
    combined: list[FunctionEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "topics": [t.to_dict() for t in self.topics],
            "combined": [f.to_dict() for f in self.combined],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Library":
        return cls(
            topics=[Topic.from_dict(t) for t in data["topics"]],
            combined=[FunctionEntry.from_dict(f) for f in data.get("combined", [])],
        )


def default_library_path() -> Optional[Path]:
    folder = config_dir()
    return None if folder is None else folder / "library.json"


def load_library(path: Path) -> Library:
    """Loads the library. Missing, empty or corrupt files yield an empty Library."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return Library()
    try:
        return Library.from_dict(json.loads(text))
    except (ValueError, KeyError, TypeError, AttributeError):
        return Library()


def save_library(library: Library, path: Path) -> None:
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(library.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        raise LibraryError(str(exc)) from exc


def generate_id() -> str:
    return f"{int(time.time() * 1000)}-{random.randrange(1_000_000)}"


def now_iso8601() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_topic(library: Library, name: str) -> Optional[Topic]:
    return next((t for t in library.topics if t.name == name), None)


def _add_to_topic(library: Library, name: str, entry: FunctionEntry) -> None:
    topic = _find_topic(library, name)
    if topic is None:
        library.topics.append(Topic(name=name, functions=[entry]))
    else:
        topic.functions.append(entry)


def save_function(library: Library, topic: str, entry: FunctionEntry, path: Path) -> None:
    if not entry.id.strip():
        entry.id = generate_id()
    if not entry.created_at.strip():
        entry.created_at = now_iso8601()
    if entry.combined:
        library.combined.append(entry)
    else:
        _add_to_topic(library, topic, entry)
    save_library(library, path)


def move_function(library: Library, entry_id: str, new_topic: str, path: Path) -> None:
    found: Optional[FunctionEntry] = None
    for topic in library.topics:
        for index, item in enumerate(topic.functions):
            if item.id == entry_id:
                found = topic.functions.pop(index)
                break
        if found is not None:
            break
    if found is None:
        raise LibraryError(f"Function '{entry_id}' not found")
    _add_to_topic(library, new_topic, found)
    save_library(library, path)


def delete_function(library: Library, entry_id: str, path: Path) -> None:
    removed = False
    for topic in library.topics:
        before = len(topic.functions)
        topic.functions = [f for f in topic.functions if f.id != entry_id]
        removed = removed or len(topic.functions) != before
    before = len(library.combined)
    library.combined = [f for f in library.combined if f.id != entry_id]
    removed = removed or len(library.combined) != before
    if not removed:
        raise LibraryError(f"Function '{entry_id}' not found")
    save_library(library, path)


def rename_topic(library: Library, old_name: str, new_name: str, path: Path) -> None:
    topic = _find_topic(library, old_name)
    if topic is None:
        raise LibraryError(f"Topic '{old_name}' not found")
    topic.name = new_name
    save_library(library, path)


def list_topics(library: Library) -> list[Topic]:
    """Topics with combined entries filtered out (combined entries live in their own group)."""
    return [
        Topic(name=t.name, functions=[f for f in t.functions if not f.combined])
        for t in library.topics
    ]


def list_combined(library: Library) -> list[FunctionEntry]:
    return list(library.combined)
