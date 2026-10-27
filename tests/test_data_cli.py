from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_cli():
    module_path = ROOT / "src" / "olfactoconnect" / "cli.py"
    assert module_path.is_file(), "data CLI module must exist"
    return importlib.import_module("olfactoconnect.cli")


def test_list_prints_available_datasets_without_calling_downloader(monkeypatch, capsys) -> None:
    cli = load_cli()

    def unexpected_download(*args, **kwargs):
        raise AssertionError("--list must not download data")

    monkeypatch.setattr(cli, "download_dataset", unexpected_download)

    assert cli.main(["--list"]) == 0
    output = capsys.readouterr().out
    assert "door-v2.0.1" in output
    assert "male-cns-v1.0-core" in output


def test_explicit_dataset_passes_only_selected_name_and_force(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    cli = load_cli()
    observed: dict[str, object] = {}

    def fake_download(name, data_dir, *, force=False):
        observed.update(name=name, data_dir=data_dir, force=force)
        return [Path("data/example.feather")]

    monkeypatch.setattr(cli, "download_dataset", fake_download)

    result = cli.main(
        ["--dataset", "male-cns-v1.0-core", "--data-dir", str(tmp_path), "--force"]
    )

    assert result == 0
    assert observed == {
        "name": "male-cns-v1.0-core",
        "data_dir": tmp_path,
        "force": True,
    }
    displayed_path = Path(capsys.readouterr().out.strip()).as_posix()
    assert displayed_path == "data/example.feather"


def test_unknown_dataset_returns_error_without_downloading(capsys) -> None:
    cli = load_cli()

    assert cli.main(["--dataset", "not-a-dataset"]) == 2
    assert "door-v2.0.1" in capsys.readouterr().err
