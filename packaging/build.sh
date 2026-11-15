#!/usr/bin/env bash
# Builds the standalone desktop app into dist/math-visualizer/.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
"$PY" -m pip install -q -r requirements-build.txt
"$PY" -m PyInstaller packaging/math-visualizer.spec --noconfirm --clean \
    --distpath dist --workpath build
echo "Built: $(pwd)/dist/math-visualizer/math-visualizer"
