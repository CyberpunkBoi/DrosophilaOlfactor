"""Command-line interface for listing and downloading explicit data sources."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

from olfactoconnect.data.downloader import download_dataset
from olfactoconnect.data.registry import get_dataset_files, list_datasets

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


def _validate_data_dir(data_dir: Path) -> Path:
    resolved = data_dir.resolve()
    repository_root = PROJECT_ROOT.resolve()
    repository_data = DEFAULT_DATA_DIR.resolve()
    if resolved.is_relative_to(repository_root) and not resolved.is_relative_to(repository_data):
        raise ValueError("data directory inside the repository must be inside the data/ directory")
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List or download project datasets")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--list", action="store_true", help="list static dataset releases")
    selection.add_argument("--dataset", help="explicit dataset identifier to download")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="local data directory (default: ./data)",
    )
    parser.add_argument("--force", action="store_true", help="replace existing files after verification")
    args = parser.parse_args(argv)

    if args.list:
        for name in list_datasets():
            files = get_dataset_files(name)
            print(f"{name}\t{files[0].version}\t{len(files)} files")
        return 0

    try:
        data_dir = _validate_data_dir(args.data_dir)
        paths = download_dataset(args.dataset, data_dir, force=args.force)
    except (ValueError, OSError, requests.RequestException) as error:
        print(f"Dataset download failed: {error}", file=sys.stderr)
        return 2

    for path in paths:
        print(path)
    return 0
