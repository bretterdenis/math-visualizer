# Math Visualizer

Native desktop app (Python + PySide6) for prompting a mathematical function in natural
language and getting an interactive 2D/3D plot back.

## How it works

- You type a prompt (e.g. "plot sin(x)*x from -10 to 10", "now overlay cos(x)", "show a 3D
  surface of sin(sqrt(x^2+y^2))").
- The backend sends the conversation to the Anthropic API (model `claude-sonnet-5-5`) with a
  forced tool schema (`render_plot`) describing the function(s), domain, and whether it's 2D or 3D.
- Expressions are evaluated with numpy on a sampling grid and drawn with matplotlib, embedded in
  the window. 2D plots support zoom and pan; 3D surfaces can be rotated with the mouse.
- Conversation history is kept in memory (per app session) so follow-up prompts like "zoom out"
  or "add another curve" work in context. "New conversation" clears it.
- "+ Add function" appends the next requested function to the current plot (2D with 2D, 3D with 3D).
- Saved functions live in a library in the sidebar, grouped by topic, plus a "Combined" group.

## Setup

Requires Python 3.10+.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

API key: either set `ANTHROPIC_API_KEY` (environment or a repo-root `.env` file), or run the app
and paste it into the one-time dialog. It is saved to `~/.config/math-visualizer/config.json`
(same format as the earlier Tauri version) and is only ever sent to `api.anthropic.com`.

The library is stored in `~/.config/math-visualizer/library.json` (also the same format as before).

## Run

```sh
python3 -m app.main
```

## Tests

```sh
python3 -m pytest              # or: python3 -m unittest discover -s tests -t .
```

The Qt smoke test runs offscreen (`QT_QPA_PLATFORM=offscreen`) and is skipped when PySide6 or
matplotlib are not installed.

## Notes

- Subtitles are typeset with matplotlib's mathtext (a subset of LaTeX); unsupported commands show
  as plain text. Descriptions are shown as plain text (no LaTeX typesetting yet).
- Expressions are never passed to Python's `eval`: they are translated from mathjs syntax and
  evaluated by a small whitelisted evaluator (arithmetic, common math functions and constants).
