# Changelog

## Unreleased

### Changed

- Replaced the Tauri/JavaScript frontend with a PySide6 (Qt) desktop app. Plots are interactive
  matplotlib figures (2D zoom/pan, 3D rotation) and expressions are evaluated with numpy.
- The backend is ported from Rust to Python. Existing `config.json` and `library.json` files keep
  working unchanged. Plotly and mathjs are no longer used.

### Features

- Function library: every plot now comes with a Title, a LaTeX-rendered Subtitle, and a
  click-to-reveal Description (which itself may contain inline LaTeX). Both are typeset with
  KaTeX.
- Topic-grouped persistence: Claude suggests a topic for each plotted function; the suggestion is
  shown in an editable field under the plot, and nothing is saved until the user clicks "Save to
  library" (hybrid suggest-then-confirm flow — no silent auto-save).
- Sidebar Library panel: lists saved functions grouped by topic, with each entry showing its
  Title and rendered Subtitle. Clicking a saved function re-renders its plot entirely client-side
  from its stored spec, with no API round-trip. Functions can be deleted from the library.
- Library storage is a JSON file at `~/.config/math-visualizer/library.json`, loaded once at
  startup and written back on every change.

### Testing

- Rust unit tests for `library.rs` (save/move/delete/rename, load/save round-trip, missing and
  corrupt file handling) and for `claude::ask`'s response parsing, the latter against a mocked
  Anthropic API via `wiremock` (new dev-dependency) instead of the real network.
- `load_library`/`save_library` now take a path parameter (`load_library_from`/
  `save_library_to`), with `default_library_path()` + `load_library()`/`save_library()` as thin
  wrappers around the real config path, so library logic is unit-testable without touching the
  user's real `library.json`.
- A Rust integration test (`src-tauri/tests/library_roundtrip.rs`) exercises a full save/move/
  rename/delete/reload sequence against a real temp-file-backed library.
- `src/plot-math.js` extracts the pure `linspace`/`safeEval` helpers out of `main.js` into a
  real ES module, loaded by `index.html` via `<script type="module">`; `tests/unit/plot-math.test.js`
  covers them with Node's built-in test runner (`npm run test:unit`).

## v0.1.0 — First release

Initial version of Math Visualizer: a native Linux desktop app (Tauri + Rust) that turns a
natural-language prompt into a mathematical function plot.

### Features

- Prompt-driven plotting: describe a function in plain language (e.g. "plot sin(x)*x from -10
  to 10") and get a rendered graph.
- 2D and 3D support: line plots for `y = f(x)`, surface plots for `z = f(x, y)`.
- Multi-trace overlays: ask to add another curve to an existing plot (e.g. "add cos(x) too").
- Conversational follow-ups: the app keeps conversation history per session, so requests like
  "zoom out" or "make it steeper" refine the existing plot instead of starting over.
- Correct geometry: 2D axes are scale-locked (equal units on x and y) by default, so shapes like
  circles and ellipses render without distortion. Implicit/multi-valued curves (e.g. the unit
  circle) are automatically split into the right branches.
- Client-side evaluation: expressions are evaluated in the browser with `mathjs` and rendered
  with `Plotly.js` — no extra network round-trip needed to resample or redraw.
- Bring-your-own API key: uses the Anthropic API directly (model `claude-sonnet-5-5`). Key can
  be set via `ANTHROPIC_API_KEY`, a local `.env` file, or a one-time in-app setup dialog (saved
  to `~/.config/math-visualizer/config.json`).
- Custom app icon.

### Known limitations

- Conversation history is in-memory only and resets on app restart.
- No persistence/export of plots yet (e.g. saving as an image or sharing a prompt history).
- Single window, single conversation at a time.
