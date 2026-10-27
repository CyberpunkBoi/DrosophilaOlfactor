from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_manifest_module():
    module_path = ROOT / "src" / "olfactoconnect" / "data" / "manifest.py"
    assert module_path.is_file(), "manifest module must exist"
    return importlib.import_module("olfactoconnect.data.manifest")


def sample_record(**overrides) -> dict[str, object]:
    record: dict[str, object] = {
        "dataset": "door-v2.0.1",
        "version": "2.0.1",
        "relative_path": "external/door-v2.0.1/door_response_matrix.csv",
        "source_url": "https://raw.githubusercontent.com/ropensci/DoOR.data/v2.0.1/data/door_response_matrix.csv",
        "retrieved_at_utc": "2026-10-27T12:00:00Z",
        "size_bytes": 296_409,
        "sha256": "a" * 64,
        "citation": "DoOR.data 2.0.1",
    }
    record.update(overrides)
    return record


def test_manifest_writes_versioned_provenance_atomically(tmp_path: Path) -> None:
    manifest = load_manifest_module()

    result_path = manifest.write_manifest(tmp_path, sample_record())

    assert result_path == tmp_path / ".metadata" / "download-manifest.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result == {"schema_version": 1, "files": [sample_record()]}
    assert not list(result_path.parent.glob("*.tmp"))


def test_manifest_replaces_record_for_same_relative_file(tmp_path: Path) -> None:
    manifest = load_manifest_module()
    first = sample_record()
    second = sample_record(retrieved_at_utc="2026-10-27T12:30:00Z")

    manifest.write_manifest(tmp_path, first)
    manifest.write_manifest(tmp_path, second)

    saved = json.loads(
        (tmp_path / ".metadata" / "download-manifest.json").read_text(encoding="utf-8")
    )
    assert saved["files"] == [second]


def test_manifest_rejects_token_fields_without_writing(tmp_path: Path) -> None:
    manifest = load_manifest_module()

    with pytest.raises(ValueError, match="credential"):
        manifest.write_manifest(tmp_path, sample_record(api_token="should-never-be-saved"))

    assert not (tmp_path / ".metadata" / "download-manifest.json").exists()


def test_manifest_rejects_embedded_credentials_and_invalid_digest(tmp_path: Path) -> None:
    manifest = load_manifest_module()

    with pytest.raises(ValueError, match="credentials"):
        manifest.write_manifest(
            tmp_path,
            sample_record(source_url="https://user:secret@example.org/file"),
        )
    with pytest.raises(ValueError, match="credentials"):
        manifest.write_manifest(
            tmp_path,
            sample_record(source_url="https://example.org/file?token=must-not-leak"),
        )
    with pytest.raises(ValueError, match="SHA-256"):
        manifest.write_manifest(tmp_path, sample_record(sha256="not-a-digest"))

    assert not (tmp_path / ".metadata" / "download-manifest.json").exists()
