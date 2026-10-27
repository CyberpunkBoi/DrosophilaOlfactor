from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_environment():
    try:
        return importlib.import_module("olfactoconnect.environment")
    except ModuleNotFoundError as error:
        return error


def test_run_setup_invokes_locked_sync_and_reports_no_compiler(
    monkeypatch, capsys
) -> None:
    environment = load_environment()
    assert not isinstance(environment, ModuleNotFoundError), "environment module must exist"
    observed: dict[str, object] = {}

    def fake_run(command, *, cwd, check):
        observed.update(command=command, cwd=cwd, check=check)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(environment.shutil, "which", lambda name: "C:/tools/uv.exe")
    monkeypatch.setattr(environment.subprocess, "run", fake_run)
    monkeypatch.setattr(environment, "find_cpp_compiler", lambda: None)

    result = environment.run_setup()

    assert result == 0
    assert observed == {
        "command": ["C:/tools/uv.exe", "sync", "--locked", "--all-groups"],
        "cwd": ROOT,
        "check": False,
    }
    compiler_notice = capsys.readouterr().err
    assert "C++ standalone" in compiler_notice
    assert "NumPy runtime" in compiler_notice


def test_run_setup_fails_helpfully_when_uv_is_missing(monkeypatch, capsys) -> None:
    environment = load_environment()
    assert not isinstance(environment, ModuleNotFoundError), "environment module must exist"

    def unexpected_run(*args, **kwargs):
        raise AssertionError("uv must not be invoked when it is not installed")

    monkeypatch.setattr(environment.shutil, "which", lambda name: None)
    monkeypatch.setattr(environment.subprocess, "run", unexpected_run)

    result = environment.run_setup()

    assert result == 2
    assert "https://docs.astral.sh/uv/getting-started/installation/" in capsys.readouterr().err


def test_run_setup_propagates_uv_failure(monkeypatch) -> None:
    environment = load_environment()
    assert not isinstance(environment, ModuleNotFoundError), "environment module must exist"
    monkeypatch.setattr(environment.shutil, "which", lambda name: "uv")
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 17),
    )

    assert environment.run_setup() == 17


def test_find_cpp_compiler_detects_linux_gxx(monkeypatch) -> None:
    environment = load_environment()
    assert not isinstance(environment, ModuleNotFoundError), "environment module must exist"
    monkeypatch.setattr(environment.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        environment.shutil,
        "which",
        lambda name: "/usr/bin/g++" if name == "g++" else None,
    )

    assert environment.find_cpp_compiler() == "/usr/bin/g++"
