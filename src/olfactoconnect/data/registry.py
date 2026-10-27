"""Static, versioned sources for project datasets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASET_CONFIG = PROJECT_ROOT / "config" / "datasets.yaml"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def validate_relative_path(relative_path: str) -> str:
    """Validate and return a normalized POSIX path beneath the data root."""
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("dataset path must be a non-empty relative path")
    if "\\" in relative_path or ":" in relative_path:
        raise ValueError("dataset path must be a safe relative path")

    parts = relative_path.split("/")
    if relative_path.startswith("/") or any(part in ("", ".", "..") for part in parts):
        raise ValueError("dataset path must be a safe relative path")
    return "/".join(parts)


def validate_source_url(url: str) -> None:
    if not isinstance(url, str):
        raise TypeError("dataset source URL must be a string")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("dataset source URL must use HTTP or HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("dataset source URL must not contain credentials")
    sensitive_names = ("token", "api_key", "apikey", "password", "secret", "authorization")
    if any(
        any(sensitive_name in key.casefold().replace("-", "_") for sensitive_name in sensitive_names)
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
    ):
        raise ValueError("dataset source URL must not contain credentials")


@dataclass(frozen=True, slots=True)
class DatasetFile:
    """A single static file in a versioned dataset release."""

    dataset: str
    version: str
    relative_path: str
    url: str
    citation: str
    expected_size: int | None = None
    expected_sha256: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("dataset", "version", "citation"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")

        validate_relative_path(self.relative_path)
        validate_source_url(self.url)

        if self.expected_size is not None and self.expected_size <= 0:
            raise ValueError("expected file size must be positive")
        if self.expected_sha256 is not None and not _SHA256_PATTERN.fullmatch(
            self.expected_sha256
        ):
            raise ValueError("expected SHA-256 must be 64 lowercase hexadecimal characters")


def _load_dataset_configuration() -> dict[str, object]:
    with DATASET_CONFIG.open("r", encoding="utf-8") as source_file:
        configuration = yaml.safe_load(source_file)

    datasets = configuration.get("datasets") if isinstance(configuration, dict) else None
    if not isinstance(datasets, dict):
        raise TypeError(f"invalid dataset registry: {DATASET_CONFIG}")
    return datasets


def list_datasets() -> tuple[str, ...]:
    """Return the supported static dataset identifiers without network access."""
    return tuple(sorted(_load_dataset_configuration()))


def get_dataset_files(name: str) -> tuple[DatasetFile, ...]:
    """Load the registered static files for one exact dataset identifier."""
    datasets = _load_dataset_configuration()

    if name not in datasets:
        available = ", ".join(sorted(datasets))
        raise ValueError(f"unknown dataset {name!r}; available datasets: {available}")

    definition = datasets[name]
    if not isinstance(definition, dict) or not isinstance(definition.get("files"), list):
        raise TypeError(f"invalid registry entry for dataset {name!r}")

    version = str(definition.get("version", ""))
    citation = str(definition.get("citation", ""))
    return tuple(
        DatasetFile(
            dataset=name,
            version=version,
            citation=citation,
            **file_definition,
        )
        for file_definition in definition["files"]
    )
