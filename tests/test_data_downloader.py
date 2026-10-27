from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

import pytest
import requests


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = b"connectome-test-payload"


def load_downloader():
    module_path = ROOT / "src" / "olfactoconnect" / "data" / "downloader.py"
    assert module_path.is_file(), "dataset downloader module must exist"
    return importlib.import_module("olfactoconnect.data.downloader")


def load_registry():
    module_path = ROOT / "src" / "olfactoconnect" / "data" / "registry.py"
    assert module_path.is_file(), "dataset registry module must exist"
    return importlib.import_module("olfactoconnect.data.registry")


class FakeResponse:
    def __init__(
        self,
        content: bytes = b"",
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {"Content-Length": str(len(content))}
        self._chunks = chunks if chunks is not None else [content]
        self._error = error
        self.closed = False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield from self._chunks
        if self._error is not None:
            raise self._error

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, *, stream: bool, timeout, headers: dict[str, str]):
        self.calls.append({"url": url, "stream": stream, "timeout": timeout, "headers": headers})
        return self.responses.pop(0)


def asset_for(registry, *, content: bytes = PAYLOAD):
    return registry.DatasetFile(
        dataset="test-dataset",
        version="1.0",
        relative_path="raw/test-dataset/payload.bin",
        url="https://example.org/payload.bin",
        citation="test fixture",
        expected_size=len(content),
        expected_sha256=hashlib.sha256(content).hexdigest(),
    )


def test_download_writes_verified_file_and_manifest(tmp_path: Path) -> None:
    downloader = load_downloader()
    registry = load_registry()
    response = FakeResponse(
        PAYLOAD,
        headers={"Content-Length": str(len(PAYLOAD))},
    )
    session = FakeSession([response])

    path = downloader.download_file(asset_for(registry), tmp_path, session=session)

    assert path.read_bytes() == PAYLOAD
    assert response.closed
    assert session.calls[0]["url"] == "https://example.org/payload.bin"
    assert session.calls[0]["stream"] is True
    manifest_path = tmp_path / ".metadata" / "download-manifest.json"
    assert manifest_path.is_file()
    assert not path.with_name(path.name + ".part").exists()


def test_interrupted_transfer_keeps_partial_file_for_resume(tmp_path: Path) -> None:
    downloader = load_downloader()
    registry = load_registry()
    asset = asset_for(registry)
    response = FakeResponse(
        chunks=[PAYLOAD[:5]],
        headers={"Content-Length": str(len(PAYLOAD))},
        error=requests.ConnectionError("connection interrupted"),
    )

    with pytest.raises(requests.ConnectionError):
        downloader.download_file(asset, tmp_path, session=FakeSession([response]))

    final_path = tmp_path / asset.relative_path
    assert not final_path.exists()
    assert final_path.with_name(final_path.name + ".part").read_bytes() == PAYLOAD[:5]


def test_download_resumes_partial_file_using_content_range(tmp_path: Path) -> None:
    downloader = load_downloader()
    registry = load_registry()
    asset = asset_for(registry)
    partial_path = tmp_path / asset.relative_path
    partial_path.parent.mkdir(parents=True)
    partial_path.with_name(partial_path.name + ".part").write_bytes(PAYLOAD[:5])
    response = FakeResponse(
        PAYLOAD[5:],
        status_code=206,
        headers={
            "Content-Length": str(len(PAYLOAD) - 5),
            "Content-Range": f"bytes 5-{len(PAYLOAD) - 1}/{len(PAYLOAD)}",
        },
    )
    session = FakeSession([response])

    result = downloader.download_file(asset, tmp_path, session=session)

    assert result.read_bytes() == PAYLOAD
    assert session.calls[0]["headers"] == {"Range": "bytes=5-"}
    assert not result.with_name(result.name + ".part").exists()


def test_server_that_ignores_range_restarts_from_full_response(tmp_path: Path) -> None:
    downloader = load_downloader()
    registry = load_registry()
    asset = asset_for(registry)
    partial_path = tmp_path / asset.relative_path
    partial_path.parent.mkdir(parents=True)
    partial_path.with_name(partial_path.name + ".part").write_bytes(b"stale")
    response = FakeResponse(PAYLOAD)
    session = FakeSession([response])

    result = downloader.download_file(asset, tmp_path, session=session)

    assert result.read_bytes() == PAYLOAD
    assert session.calls[0]["headers"] == {"Range": "bytes=5-"}


def test_valid_existing_file_is_not_fetched_again(tmp_path: Path) -> None:
    downloader = load_downloader()
    registry = load_registry()
    asset = asset_for(registry)
    path = tmp_path / asset.relative_path
    path.parent.mkdir(parents=True)
    path.write_bytes(PAYLOAD)

    result = downloader.download_file(asset, tmp_path, session=FakeSession([]))

    assert result == path
    assert result.read_bytes() == PAYLOAD


def test_existing_invalid_file_requires_force(tmp_path: Path) -> None:
    downloader = load_downloader()
    registry = load_registry()
    asset = asset_for(registry)
    path = tmp_path / asset.relative_path
    path.parent.mkdir(parents=True)
    path.write_bytes(b"other payload")

    with pytest.raises(FileExistsError, match="--force"):
        downloader.download_file(asset, tmp_path, session=FakeSession([]))

    assert path.read_bytes() == b"other payload"


def test_force_replaces_existing_file_only_after_verification(tmp_path: Path) -> None:
    downloader = load_downloader()
    registry = load_registry()
    asset = asset_for(registry)
    path = tmp_path / asset.relative_path
    path.parent.mkdir(parents=True)
    path.write_bytes(b"old payload")

    result = downloader.download_file(
        asset,
        tmp_path,
        force=True,
        session=FakeSession([FakeResponse(PAYLOAD)]),
    )

    assert result.read_bytes() == PAYLOAD


@pytest.mark.parametrize("failure", ["size", "digest"])
def test_invalid_download_is_not_promoted_to_final_file(tmp_path: Path, failure: str) -> None:
    downloader = load_downloader()
    registry = load_registry()
    if failure == "size":
        asset = registry.DatasetFile(
            dataset="test-dataset",
            version="1.0",
            relative_path="raw/test-dataset/payload.bin",
            url="https://example.org/payload.bin",
            citation="test fixture",
            expected_size=len(PAYLOAD) + 1,
        )
    else:
        asset = registry.DatasetFile(
            dataset="test-dataset",
            version="1.0",
            relative_path="raw/test-dataset/payload.bin",
            url="https://example.org/payload.bin",
            citation="test fixture",
            expected_size=len(PAYLOAD),
            expected_sha256="0" * 64,
        )

    with pytest.raises(ValueError):
        downloader.download_file(asset, tmp_path, session=FakeSession([FakeResponse(PAYLOAD)]))

    final_path = tmp_path / asset.relative_path
    assert not final_path.exists()
    assert not final_path.with_name(final_path.name + ".part").exists()


def test_http_error_leaves_no_final_or_partial_file(tmp_path: Path) -> None:
    downloader = load_downloader()
    registry = load_registry()
    asset = asset_for(registry)

    with pytest.raises(requests.HTTPError):
        downloader.download_file(
            asset,
            tmp_path,
            session=FakeSession([FakeResponse(status_code=404)]),
        )

    final_path = tmp_path / asset.relative_path
    assert not final_path.exists()
    assert not final_path.with_name(final_path.name + ".part").exists()
