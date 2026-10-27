from __future__ import annotations

import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_project_declares_one_python_312_research_environment() -> None:
    pyproject = ROOT / "pyproject.toml"
    assert pyproject.is_file(), "pyproject.toml must define the project environment"

    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = config["project"]

    assert project["requires-python"] == ">=3.12,<3.13"
    dependencies = [dependency.lower() for dependency in project["dependencies"]]
    package_names = {
        re.split(r"\s*(?:\[|;|@|<|>|=|!)", dependency, maxsplit=1)[0].strip()
        for dependency in dependencies
    }
    required = {
        "brian2",
        "caveclient",
        "flygym",
        "igraph",
        "matplotlib",
        "neuprint-python",
        "numpy",
        "pandas",
        "polars",
        "pyarrow",
        "python-dotenv",
        "requests",
        "scipy",
        "seaborn",
        "torch",
    }
    assert required <= package_names
    pandas_specifier = next(dep for dep in dependencies if dep.startswith("pandas"))
    assert "<3" in pandas_specifier

    dev_dependencies = config["dependency-groups"]["dev"]
    dev_package_names = {
        re.split(r"\s*(?:\[|;|@|<|>|=|!)", item, maxsplit=1)[0].strip().lower()
        for item in dev_dependencies
    }
    assert dev_package_names >= {"pytest", "ruff"}
    assert (ROOT / "uv.lock").is_file(), "uv.lock must pin the resolved environment"
    assert not (ROOT / "Dockerfile").exists(), "the approved setup is local uv, not Docker"


def test_project_builds_a_wheel_with_its_git_dependency(tmp_path: Path) -> None:
    uv = os.environ.get("UV_EXECUTABLE") or shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required; setup and CI install it before running tests")

    result = subprocess.run(
        [uv, "build", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert list(tmp_path.glob("olfactoconnect-*.whl"))


def test_gitignore_excludes_local_environment_secrets_and_downloads(tmp_path: Path) -> None:
    gitignore = ROOT / ".gitignore"
    assert gitignore.is_file(), ".gitignore must protect local data and credentials"

    (tmp_path / ".gitignore").write_bytes(gitignore.read_bytes())
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)

    ignored_paths = [
        ".venv/Lib/site-packages/example.py",
        ".env",
        "data/raw/connectome.feather",
        "artifacts/run/result.csv",
    ]
    for relative_path in ignored_paths:
        result = subprocess.run(
            ["git", "-C", str(tmp_path), "check-ignore", "-q", "--", relative_path],
            check=False,
        )
        assert result.returncode == 0, f"expected {relative_path} to be ignored"

    tracked_readme = subprocess.run(
        ["git", "-C", str(tmp_path), "check-ignore", "-q", "--", "data/README.md"],
        check=False,
    )
    assert tracked_readme.returncode == 1, "data/README.md should remain trackable"
