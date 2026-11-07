# Changelog

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
