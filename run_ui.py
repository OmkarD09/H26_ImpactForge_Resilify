#!/usr/bin/env python3
"""Resilify Developer Workstation — Launcher Script.

Usage:
    python run_ui.py [--port 8000] [--host 127.0.0.1]
"""

import sys
from pathlib import Path

# Ensure root repository directory is on sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from resilify.ui.server import main

if __name__ == "__main__":
    main()
