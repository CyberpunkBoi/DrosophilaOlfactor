from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_data_list_script_runs_without_creating_a_manifest() -> None:
    manifest_path = ROOT / "data" / ".metadata" / "download-manifest.json"
    manifest_existed_before = manifest_path.exists()

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "download_data.py"), "--list"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "door-v2.0.1" in result.stdout
    assert "male-cns-v1.0-core" in result.stdout
    assert manifest_path.exists() == manifest_existed_before


def test_ci_matrix_and_commands_cover_local_verification() -> None:
    workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow_path.is_file(), "GitHub Actions workflow must exist"
    workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert workflow["permissions"]["contents"] == "read"
    assert len(workflow["jobs"]) == 1
    job = next(iter(workflow["jobs"].values()))
    assert set(job["strategy"]["matrix"]["os"]) == {"windows-2022", "ubuntu-24.04"}
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "uv lock --check" in commands
    assert "uv sync --locked --all-groups" in commands
    assert "uv run --locked ruff check ." in commands
    assert "uv run --locked pytest -q" in commands
    assert "download_data.py --dataset" not in commands


def test_license_is_a_nonbinding_placeholder() -> None:
    license_path = ROOT / "LICENSE"
    assert license_path.is_file()
    assert license_path.read_text(encoding="utf-8").startswith(
        "LICENSE TEMPLATE — NOT A LICENSE"
    )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert "license" not in project


def test_git_tracks_data_instructions_but_ignores_payloads_and_secrets() -> None:
    def ignored(path: str) -> bool:
        return subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "-q", "--", path],
            check=False,
        ).returncode == 0

    assert ignored(".venv/Lib/site-packages/example.py")
    assert ignored(".env")
    assert not ignored(".env.example")
    assert ignored("data/raw/male-cns.feather")
    assert not ignored("data/README.md")
