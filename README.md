# Math Visualizer

Native Linux desktop app (Tauri + Rust) for prompting a mathematical function in natural
language and getting a live 2D/3D plot back.

## How it works

- You type a prompt (e.g. "plot sin(x)*x from -10 to 10", "now overlay cos(x)", "show a 3D
  surface of sin(sqrt(x^2+y^2))").
- The Rust backend sends the conversation to the Anthropic API (model `claude-sonnet-5-5`)
  with a forced tool schema (`render_plot`) describing the function(s), domain, and whether
  it's 2D or 3D.
- The frontend evaluates the returned expression(s) client-side with `mathjs` and renders them
  with `Plotly.js`.
- Conversation history is kept in memory (per app session) so follow-up prompts like "zoom out"
  or "add another curve" work in context. "New conversation" clears it.

## Setup

1. **Rust + Tauri prerequisites** (not installed on this machine yet — install yourself):
   ```sh
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   # Linux system deps for Tauri (Debian/Ubuntu example):
   sudo apt install -y libwebkit2gtk-4.1-dev build-essential curl wget file \
     libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
   ```
2. **Node deps**:
   ```sh
   npm install
   ```
3. **API key** — either set the environment variable before launching:
   ```sh
   export ANTHROPIC_API_KEY=sk-ant-...
   ```
   or just run the app and paste it into the one-time setup dialog; it's saved to
   `~/.config/math-visualizer/config.json` and reused on future launches. It is only ever sent
   to `api.anthropic.com`.

## Run (dev)

```sh
npm run tauri dev
```

## Build a native package

```sh
npm run tauri build
```

Produces a `.deb` and an AppImage under `src-tauri/target/release/bundle/`.

## Notes / next steps

- No app icon is set up yet; `npm run tauri icon <path-to-1024px-png>` generates one from an
  image if you want a custom icon before building a release bundle.
- Conversation history resets on app restart (only persisted for the running session).
- Expressions are evaluated with `mathjs`'s default (sandboxed) evaluator — no filesystem/network
  access from expressions, only arithmetic/math functions.
