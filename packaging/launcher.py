"""PyInstaller entry point: runs the app the same way ``python3 -m app.main`` does."""

import sys

from app.main import main

if __name__ == "__main__":
    sys.exit(main())
