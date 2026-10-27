#!/usr/bin/env python3
"""Create/update the project's .venv from the committed uv lockfile."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from olfactoconnect.environment import run_setup

if __name__ == "__main__":
    raise SystemExit(run_setup())
