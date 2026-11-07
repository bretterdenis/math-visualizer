"""Configuration: .env loading, the config directory, and the stored API key.

File formats match the former Tauri/Rust app so existing installs keep working:
- ``<config dir>/math-visualizer/config.json`` holds ``{"api_key": "..."}``.
- ``ANTHROPIC_API_KEY`` (env var, or the repo-root ``.env``) takes precedence over the file.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

APP_DIR_NAME = "math-visualizer"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class ConfigError(Exception):
    """Raised when configuration cannot be read or written."""


def config_dir() -> Optional[Path]:
    """Per-user config folder for the app, mirroring Rust's ``dirs::config_dir``."""
    if sys.platform == "darwin":
        base: Optional[Path] = Path.home() / "Library" / "Application Support"
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else None
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg and os.path.isabs(xdg) else Path.home() / ".config"
    return None if base is None else base / APP_DIR_NAME


def config_file() -> Optional[Path]:
    folder = config_dir()
    return None if folder is None else folder / "config.json"


def parse_dotenv(text: str) -> dict[str, str]:
    """Parses KEY=VALUE lines. Comments, blank lines and an optional ``export`` are skipped."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key:
            values[key] = value
    return values


def load_dotenv(path: Path = ENV_FILE) -> None:
    """Loads ``.env`` into the process environment without overriding existing variables."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for key, value in parse_dotenv(text).items():
        if key not in os.environ:
            os.environ[key] = value


def load_api_key() -> Optional[str]:
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key and env_key.strip():
        return env_key
    path = config_file()
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    key = data.get("api_key")
    return key if isinstance(key, str) else None


def save_api_key(key: str) -> None:
    path = config_file()
    if path is None:
        raise ConfigError("Could not resolve config directory")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"api_key": key}, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except OSError as exc:
        raise ConfigError(str(exc)) from exc
