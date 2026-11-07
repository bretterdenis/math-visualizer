"""Library file format and operations (ports of the former Rust library.rs and library_roundtrip tests)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.backend.library import (
    FunctionEntry,
    Library,
    LibraryError,
    delete_function,
    list_combined,
    list_topics,
    load_library,
    move_function,
    rename_topic,
    save_function,
)

# Exactly what the Rust version wrote (serde_json pretty output, combined key present).
RUST_WRITTEN_LIBRARY = """{
  "topics": [
    {
      "name": "Trig",
      "functions": [
        {
          "id": "1700000000000-123456",
          "title": "Sine",
          "subtitle": "f(x) = \\\\sin(x)",
          "description": "A sine wave.",
          "kind": "2d",
          "variables": [
            "x"
          ],
          "domain": {
            "xMin": -10,
            "xMax": 10
          },
          "traces": [
            {
              "expr": "sin(x)",
              "label": "sin"
            }
          ],
          "created_at": "2026-01-01T10:00:00Z",
          "combined": false
        }
      ]
    }
  ],
  "combined": [
    {
      "id": "1700000000001-7",
      "title": "Sine + Cosine",
      "subtitle": "",
      "description": "",
      "kind": "2d",
      "variables": [
        "x"
      ],
      "domain": {},
      "traces": [],
      "created_at": "2026-01-02T10:00:00Z",
      "combined": true
    }
  ]
}"""

# Written by an even older build: no "combined" keys at all.
LEGACY_NO_COMBINED_KEYS = (
    '{"topics": [{"name": "A", "functions": [{"id": "a1", "title": "One", "subtitle": "", '
    '"description": "", "kind": "2d", "variables": ["x"], "domain": {}, "traces": [], '
    '"created_at": ""}]}]}'
)


def entry(entry_id, title="T", combined=False, kind="2d"):
    return FunctionEntry(
        id=entry_id,
        title=title,
        subtitle="",
        description="",
        kind=kind,
        variables=["x"],
        domain={"xMin": -10, "xMax": 10},
        traces=[{"expr": "x"}],
        created_at="",
        combined=combined,
    )


class LibraryTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = Path(tempfile.mkdtemp(prefix="mathviz-test-"))
        self.path = self._dir / "nested" / "library.json"

    def tearDown(self):
        shutil.rmtree(self._dir, ignore_errors=True)


class FileFormatTests(LibraryTestCase):
    def test_loads_file_written_by_rust_version(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(RUST_WRITTEN_LIBRARY, encoding="utf-8")
        lib = load_library(self.path)
        self.assertEqual(len(lib.topics), 1)
        self.assertEqual(lib.topics[0].name, "Trig")
        self.assertEqual(lib.topics[0].functions[0].subtitle, "f(x) = \\sin(x)")
        self.assertFalse(lib.topics[0].functions[0].combined)
        self.assertEqual(len(lib.combined), 1)
        self.assertTrue(lib.combined[0].combined)

    def test_rewriting_rust_written_file_keeps_entries(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(RUST_WRITTEN_LIBRARY, encoding="utf-8")
        save_library_via_op(self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["combined"][0]["id"], "1700000000001-7")
        self.assertEqual(data["topics"][0]["functions"][0]["title"], "Sine")
        self.assertEqual(data["topics"][0]["functions"][-1]["id"], "extra")

    def test_missing_combined_key_loads_as_empty(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(LEGACY_NO_COMBINED_KEYS, encoding="utf-8")
        lib = load_library(self.path)
        self.assertEqual(len(lib.topics), 1)
        self.assertEqual(lib.combined, [])
        self.assertFalse(lib.topics[0].functions[0].combined)

    def test_missing_file_returns_empty(self):
        lib = load_library(self.path)
        self.assertEqual(lib.topics, [])

    def test_corrupt_file_returns_empty(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("not valid json", encoding="utf-8")
        self.assertEqual(load_library(self.path).topics, [])

    def test_saved_file_has_same_keys_as_rust_version(self):
        lib = Library()
        save_function(lib, "A", entry("a1"), self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(list(data.keys()), ["topics", "combined"])
        self.assertEqual(
            list(data["topics"][0]["functions"][0].keys()),
            ["id", "title", "subtitle", "description", "kind", "variables", "domain", "traces", "created_at", "combined"],
        )


class OperationTests(LibraryTestCase):
    def test_save_creates_topic_and_fills_blank_fields(self):
        lib = Library()
        save_function(lib, "Polynomials", entry(""), self.path)
        self.assertEqual(lib.topics[0].name, "Polynomials")
        saved = lib.topics[0].functions[0]
        self.assertTrue(saved.id.strip())
        self.assertTrue(saved.created_at.endswith("Z"))
        reloaded = load_library(self.path)
        self.assertEqual(reloaded.topics[0].functions[0].id, saved.id)

    def test_save_appends_to_existing_topic(self):
        lib = Library()
        save_function(lib, "Trig", entry("a"), self.path)
        save_function(lib, "Trig", entry("b"), self.path)
        self.assertEqual(len(lib.topics), 1)
        self.assertEqual(len(lib.topics[0].functions), 2)

    def test_combined_entry_goes_to_combined_group_regardless_of_topic(self):
        lib = Library()
        save_function(lib, "", entry("c1", combined=True), self.path)
        save_function(lib, "A", entry("t1"), self.path)
        reloaded = load_library(self.path)
        self.assertEqual([f.id for f in reloaded.combined], ["c1"])
        self.assertTrue(reloaded.combined[0].combined)
        self.assertEqual(len(reloaded.topics), 1)
        self.assertFalse(reloaded.topics[0].functions[0].combined)

    def test_list_topics_excludes_combined_and_list_combined_returns_them(self):
        lib = Library()
        save_function(lib, "A", entry("t1"), self.path)
        save_function(lib, "A", entry("c1", combined=True), self.path)
        topics = list_topics(lib)
        self.assertEqual([f.id for f in topics[0].functions], ["t1"])
        self.assertEqual([f.id for f in list_combined(lib)], ["c1"])

    def test_move_between_topics(self):
        lib = Library()
        save_function(lib, "A", entry("x1"), self.path)
        move_function(lib, "x1", "B", self.path)
        a = next(t for t in lib.topics if t.name == "A")
        b = next(t for t in lib.topics if t.name == "B")
        self.assertEqual(a.functions, [])
        self.assertEqual([f.id for f in b.functions], ["x1"])

    def test_move_missing_id_errors(self):
        with self.assertRaisesRegex(LibraryError, "nope"):
            move_function(Library(), "nope", "B", self.path)

    def test_delete_removes_from_topic_and_combined(self):
        lib = Library()
        save_function(lib, "A", entry("x1"), self.path)
        save_function(lib, "A", entry("x2"), self.path)
        save_function(lib, "", entry("c1", combined=True), self.path)
        delete_function(lib, "x1", self.path)
        delete_function(lib, "c1", self.path)
        self.assertEqual([f.id for f in lib.topics[0].functions], ["x2"])
        self.assertEqual(lib.combined, [])
        reloaded = load_library(self.path)
        self.assertEqual(reloaded.combined, [])

    def test_delete_missing_id_errors(self):
        with self.assertRaisesRegex(LibraryError, "nope"):
            delete_function(Library(), "nope", self.path)

    def test_rename_topic_persists(self):
        lib = Library()
        save_function(lib, "Old", entry("x1"), self.path)
        rename_topic(lib, "Old", "New", self.path)
        self.assertEqual(load_library(self.path).topics[0].name, "New")

    def test_rename_missing_topic_errors(self):
        with self.assertRaisesRegex(LibraryError, "Ghost"):
            rename_topic(Library(), "Ghost", "New", self.path)

    def test_full_session_sequence_with_reload(self):
        """Port of the Rust library_roundtrip integration test: several actions, then reload."""
        lib = Library()
        save_function(lib, "Polynomials", entry("p1", title="Cubic"), self.path)
        save_function(lib, "", entry("c1", title="Combo", combined=True), self.path)
        move_function(lib, "p1", "Algebra", self.path)
        rename_topic(lib, "Algebra", "Algebra II", self.path)
        delete_function(lib, "c1", self.path)

        reloaded = load_library(self.path)
        self.assertEqual([t.name for t in reloaded.topics], ["Polynomials", "Algebra II"])
        self.assertEqual([f.id for f in reloaded.topics[1].functions], ["p1"])
        self.assertEqual(reloaded.topics[0].functions, [])
        self.assertEqual(reloaded.combined, [])


def save_library_via_op(path):
    """Re-saves a loaded library through an operation, to check the on-disk output still parses."""
    lib = load_library(path)
    save_function(lib, "Trig", entry("extra"), path)


if __name__ == "__main__":
    unittest.main()
