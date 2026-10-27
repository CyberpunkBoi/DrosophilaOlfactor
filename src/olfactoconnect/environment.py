"""Recreate and inspect the project's single locked Python environment."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def find_cpp_compiler() -> str | None:
    """Return the first supported compiler found on PATH, if any."""
    candidates = {
        "Windows": ("cl.exe", "clang++.exe", "g++.exe"),
        "Darwin": ("clang++", "g++"),
        "Linux": ("g++", "clang++"),
    }.get(platform.system(), ("cl.exe", "g++", "clang++"))

    for candidate in candidates:
        compiler = shutil.which(candidate)
        if compiler is not None:
            return compiler
    return None


def run_setup(uv_executable: str | None = None) -> int:
    """Sync the project environment from the committed lockfile."""
    executable = uv_executable or shutil.which("uv")
    if executable is None:
        print(
            "uv was not found. Install it using the instructions at "
            "https://docs.astral.sh/uv/getting-started/installation/",
            file=sys.stderr,
        )
        return 2

    result = subprocess.run(
        [executable, "sync", "--locked", "--all-groups"],
        cwd=PROJECT_ROOT,
        check=False,
    )

    compiler = find_cpp_compiler()
    if compiler is None:
        print(
            "C++ compiler not found. Brian2's NumPy runtime is ready; install "
            "a compiler only if you use the C++ standalone backend.",
            file=sys.stderr,
        )
    else:
        print(f"C++ compiler detected: {compiler}")

    return result.returncode
