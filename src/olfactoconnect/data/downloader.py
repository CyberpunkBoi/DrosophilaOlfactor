"""Explicit, integrity-checked downloads for registered public data files."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import requests

from olfactoconnect.data.manifest import MANIFEST_RELATIVE_PATH, write_manifest
from olfactoconnect.data.registry import DatasetFile, get_dataset_files

_CONTENT_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+|\*)$")
_CHUNK_SIZE = 1024 * 1024


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_sha256(data_dir: Path, relative_path: str) -> tuple[int, str] | None:
    manifest_path = data_dir / MANIFEST_RELATIVE_PATH
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        return None
    for record in manifest["files"]:
        if isinstance(record, dict) and record.get("relative_path") == relative_path:
            size_bytes = record.get("size_bytes")
            sha256 = record.get("sha256")
            if isinstance(size_bytes, int) and isinstance(sha256, str):
                return size_bytes, sha256
    return None


def _record_file(asset: DatasetFile, path: Path, data_dir: Path) -> None:
    write_manifest(
        data_dir,
        {
            "dataset": asset.dataset,
            "version": asset.version,
            "relative_path": asset.relative_path,
            "source_url": asset.url,
            "retrieved_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace(
                "+00:00", "Z"
            ),
            "size_bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
            "citation": asset.citation,
        },
    )


def _matches_integrity(asset: DatasetFile, path: Path, data_dir: Path) -> bool:
    size_bytes = path.stat().st_size
    if asset.expected_size is not None and size_bytes != asset.expected_size:
        return False

    digest = _file_sha256(path)
    if asset.expected_sha256 is not None:
        return digest == asset.expected_sha256

    recorded = _manifest_sha256(data_dir, asset.relative_path)
    return recorded == (size_bytes, digest)


def _parse_content_range(value: str | None, offset: int) -> tuple[int, int | None]:
    match = _CONTENT_RANGE.fullmatch(value or "")
    if match is None:
        raise ValueError("server returned an invalid Content-Range for a resumed download")
    start, end = int(match.group(1)), int(match.group(2))
    total = None if match.group(3) == "*" else int(match.group(3))
    if start != offset or end < start or (total is not None and end >= total):
        raise ValueError("server returned an inconsistent Content-Range for a resumed download")
    return end - start + 1, total


def _safe_destination(data_dir: Path, asset: DatasetFile) -> Path:
    root = data_dir.resolve()
    destination = (root / Path(asset.relative_path)).resolve()
    if not destination.is_relative_to(root):
        raise ValueError("dataset destination escapes the data directory")
    return destination


def _download_with_session(
    asset: DatasetFile,
    data_dir: Path,
    *,
    force: bool,
    session: requests.Session,
) -> Path:
    destination = _safe_destination(data_dir, asset)
    partial_path = destination.with_name(destination.name + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not force:
        if _matches_integrity(asset, destination, data_dir):
            _record_file(asset, destination, data_dir)
            return destination
        raise FileExistsError(
            f"{destination} exists but fails integrity checks; pass --force to replace it"
        )

    offset = partial_path.stat().st_size if partial_path.exists() else 0
    if asset.expected_size is not None and offset >= asset.expected_size:
        if offset == asset.expected_size and _matches_integrity(asset, partial_path, data_dir):
            os.replace(partial_path, destination)
            _record_file(asset, destination, data_dir)
            return destination
        partial_path.unlink()
        offset = 0

    headers = {"Range": f"bytes={offset}-"} if offset else {}
    response = session.get(
        asset.url,
        stream=True,
        timeout=(10, 120),
        headers=headers,
    )
    mode = "wb"
    response_bytes: int | None = None
    response_total: int | None = None
    try:
        response.raise_for_status()
        if offset and response.status_code == 206:
            response_bytes, response_total = _parse_content_range(
                response.headers.get("Content-Range"), offset
            )
            if asset.expected_size is not None and response_total not in (None, asset.expected_size):
                raise ValueError("server Content-Range size does not match the registered file size")
            mode = "ab"
        elif response.status_code != 200:
            raise ValueError(f"unexpected HTTP status {response.status_code}")

        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                response_bytes = int(content_length)
            except ValueError as error:
                raise ValueError("server returned an invalid Content-Length") from error

        with partial_path.open(mode) as output:
            received = 0
            for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                if chunk:
                    output.write(chunk)
                    received += len(chunk)
            output.flush()
            os.fsync(output.fileno())

        if response_bytes is not None and received != response_bytes:
            raise ValueError("download byte count does not match the HTTP response")
        if asset.expected_size is not None and partial_path.stat().st_size != asset.expected_size:
            raise ValueError("download size does not match the registered file size")
        if response_total is not None and partial_path.stat().st_size != response_total:
            raise ValueError("resumed download size does not match Content-Range")
        if asset.expected_sha256 is not None and _file_sha256(partial_path) != asset.expected_sha256:
            raise ValueError("download SHA-256 does not match the registered checksum")
    except ValueError:
        partial_path.unlink(missing_ok=True)
        raise
    finally:
        response.close()

    os.replace(partial_path, destination)
    _record_file(asset, destination, data_dir)
    return destination


def download_file(
    asset: DatasetFile,
    data_dir: Path,
    *,
    force: bool = False,
    session: requests.Session | None = None,
) -> Path:
    """Download one file, resuming partial transfers and validating before promotion."""
    if session is not None:
        return _download_with_session(asset, data_dir, force=force, session=session)

    with requests.Session() as owned_session:
        return _download_with_session(asset, data_dir, force=force, session=owned_session)


def download_dataset(
    name: str,
    data_dir: Path,
    *,
    force: bool = False,
    session: requests.Session | None = None,
) -> list[Path]:
    """Download every registered file for exactly one selected dataset."""
    assets = get_dataset_files(name)

    def download_all(active_session: requests.Session) -> list[Path]:
        return [
            download_file(asset, data_dir, force=force, session=active_session)
            for asset in assets
        ]

    if session is not None:
        return download_all(session)
    with requests.Session() as owned_session:
        return download_all(owned_session)
