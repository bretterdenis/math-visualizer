#!/usr/bin/env bash
# Adds Math Visualizer to the desktop app menu (current user only) pointing at the built bundle.
# Run ./packaging/build.sh first. Remove with: ./packaging/install-desktop-entry.sh --uninstall
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps"
DESKTOP="$APPS/math-visualizer.desktop"

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -f "$DESKTOP" "$ICONS/math-visualizer.png"
    command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
    echo "Removed $DESKTOP"
    exit 0
fi

BIN="$ROOT/dist/math-visualizer/math-visualizer"
[[ -x "$BIN" ]] || { echo "Missing $BIN - run ./packaging/build.sh first." >&2; exit 1; }

mkdir -p "$APPS" "$ICONS"
if command -v convert >/dev/null; then
    convert "$ROOT/icon.png" -resize 512x512 "$ICONS/math-visualizer.png"
else
    cp "$ROOT/icon.png" "$ICONS/math-visualizer.png"
fi

cat > "$DESKTOP" <<DESK
[Desktop Entry]
Type=Application
Name=Math Visualizer
Comment=Plot math functions from natural-language prompts
Exec="$BIN"
Path=$ROOT/dist/math-visualizer
Icon=math-visualizer
Terminal=false
Categories=Education;Science;Math;
StartupWMClass=math-visualizer
DESK
chmod +x "$DESKTOP"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
echo "Installed $DESKTOP - look for 'Math Visualizer' in your app menu."
