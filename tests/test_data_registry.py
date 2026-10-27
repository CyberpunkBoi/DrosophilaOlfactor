from __future__ import annotations

import importlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_registry():
    module_path = ROOT / "src" / "olfactoconnect" / "data" / "registry.py"
    assert module_path.is_file(), "dataset registry module must exist"
    return importlib.import_module("olfactoconnect.data.registry")


def test_door_registry_pins_release_files_and_checksums() -> None:
    registry = load_registry()

    files = registry.get_dataset_files("door-v2.0.1")

    assert [asset.relative_path for asset in files] == [
        "external/door-v2.0.1/door_response_matrix.csv",
        "external/door-v2.0.1/door_mappings.csv",
    ]
    assert files[0].url == (
        "https://raw.githubusercontent.com/ropensci/DoOR.data/v2.0.1/"
        "data/door_response_matrix.csv"
    )
    assert files[0].expected_size == 296_409
    assert files[0].expected_sha256 == (
        "5035dcbed5ffdb3b42c1df0c01d0526f7ed3fa0f8928eabfcd2279ea80ddb348"
    )
    assert files[1].expected_size == 12_824
    assert files[1].expected_sha256 == (
        "1197c492e769b1b587c907c5b750ffa2507d7e6c9fe9dfcb2ee8603871e00912"
    )


def test_male_cns_core_registers_only_required_static_tables() -> None:
    registry = load_registry()

    files = registry.get_dataset_files("male-cns-v1.0-core")

    assert [Path(asset.relative_path).name for asset in files] == [
        "body-annotations-male-cns-v1.0-minconf-0.5.feather",
        "body-neurotransmitters-male-cns-v1.0.feather",
        "connectome-weights-male-cns-v1.0-minconf-0.5.feather",
    ]
    assert [asset.expected_size for asset in files] == [
        14_483_314,
        43_282_834,
        1_051_241_946,
    ]
    assert all(asset.expected_sha256 is None for asset in files)
    assert all(asset.version == "v1.0" for asset in files)


def test_unknown_dataset_names_available_releases() -> None:
    registry = load_registry()

    with pytest.raises(ValueError, match="door-v2.0.1") as error:
        registry.get_dataset_files("latest")

    assert "male-cns-v1.0-core" in str(error.value)


@pytest.mark.parametrize(
    "relative_path",
    ["../outside.feather", "raw/../../outside.feather", "/outside.feather", "C:\\outside.feather"],
)
def test_dataset_file_rejects_paths_outside_data_root(relative_path: str) -> None:
    registry = load_registry()

    with pytest.raises(ValueError, match="relative path"):
        registry.DatasetFile(
            dataset="test",
            version="1",
            relative_path=relative_path,
            url="https://example.org/file",
            citation="test fixture",
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@example.org/file",
        "https://example.org/file?token=should-not-be-embedded",
        "https://example.org/file?api_key=should-not-be-embedded",
    ],
)
def test_dataset_file_rejects_credentials_embedded_in_source_url(url: str) -> None:
    registry = load_registry()

    with pytest.raises(ValueError, match="credentials"):
        registry.DatasetFile(
            dataset="test",
            version="1",
            relative_path="raw/file.feather",
            url=url,
            citation="test fixture",
        )
