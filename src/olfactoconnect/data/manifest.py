"""Atomic local provenance manifests for downloaded data files."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile
from olfactoconnect.data.registry import validate_relative_path, validate_source_url


MANIFEST_RELATIVE_PATH = Path(".metadata") / "download-manifest.json"
_REQUIRED_FIELDS = {
    "dataset",
    "version",
    "relative_path",
    "source_url",
    "retrieved_at_utc",
    "size_bytes",
    "sha256",
    "citation",
}
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _validate_file_record(file_record: dict[str, object]) -> dict[str, object]:
    if not isinstance(file_record, dict):
        raise ValueError("manifest file record must be an object")

    credential_fields = [
        key
        for key in file_record
        if any(term in key.casefold() for term in ("token", "password", "secret", "authorization"))
    ]
    if credential_fields:
        raise ValueError("manifest may not contain credential fields")

    unknown = set(file_record) - _REQUIRED_FIELDS
    missing = _REQUIRED_FIELDS - set(file_record)
    if unknown or missing:
        raise ValueError(
            f"invalid manifest fields; missing={sorted(missing)}, unknown={sorted(unknown)}"
        )

    record = dict(file_record)
    for field_name in ("dataset", "version", "citation"):
        value = record[field_name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"manifest {field_name} must be a non-empty string")

    record["relative_path"] = validate_relative_path(record["relative_path"])
    source_url = record["source_url"]
    if not isinstance(source_url, str):
        raise ValueError("manifest source_url must be a string")
    validate_source_url(source_url)

    timestamp = record["retrieved_at_utc"]
    if not isinstance(timestamp, str):
        raise ValueError("manifest retrieved_at_utc must be a string")
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("manifest retrieved_at_utc must be an ISO-8601 timestamp") from error
    if parsed_timestamp.utcoffset() is None or parsed_timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("manifest retrieved_at_utc must be UTC")

    size_bytes = record["size_bytes"]
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        raise ValueError("manifest size_bytes must be a non-negative integer")

    digest = record["sha256"]
    if not isinstance(digest, str) or not _SHA256_PATTERN.fullmatch(digest):
        raise ValueError("manifest SHA-256 must be 64 lowercase hexadecimal characters")

    return record


def write_manifest(data_dir: Path, file_record: dict[str, object]) -> Path:
    """Add or replace one provenance entry using an atomic file replacement."""
    record = _validate_file_record(file_record)
    manifest_path = data_dir / MANIFEST_RELATIVE_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"existing download manifest is unreadable: {manifest_path}") from error
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema_version") != 1
            or not isinstance(manifest.get("files"), list)
        ):
            raise ValueError(f"existing download manifest has an unsupported schema: {manifest_path}")
        files = manifest["files"]
    else:
        files = []

    files = [
        existing
        for existing in files
        if existing.get("relative_path") != record["relative_path"]
    ]
    files.append(record)
    files.sort(key=lambda existing: existing["relative_path"])
    manifest = {"schema_version": 1, "files": files}

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=manifest_path.parent,
            prefix=".manifest-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(manifest, temporary_file, ensure_ascii=False, indent=2, sort_keys=True)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, manifest_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return manifest_path
