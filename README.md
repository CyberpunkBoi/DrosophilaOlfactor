# OlfactoConnect

Reproducible environment and data-acquisition tools for a planned model of
the *Drosophila* olfactory antennal lobe based on MaleCNS, DoOR, and
independent physiological validation data.

The agreed research plan focuses on the ORN→PN transformation (R1) and
cross-connectome/sex comparison (R2). Kenyon-cell and embodied experiments
(R3) are extensions. This repository currently prepares the software and
data-acquisition scaffolding only: it does not build connectome graphs, run
the DM2/DC2 pilot, evaluate G1, or implement a neural model.

## Requirements

- Windows 10/11, macOS, or 64-bit Linux
- Python 3.12 (the project is locked to `>=3.12,<3.13`)
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Git
- Internet access for installing packages and explicitly requested data
- A C++ compiler only if you choose Brian2's C++ standalone backend. The
  default smoke test uses Brian2's NumPy runtime and does not need a compiler.

## Create the environment

Install `uv` once using the [official instructions](https://docs.astral.sh/uv/getting-started/installation/), then run this from the repository root:

```powershell
python scripts/setup_environment.py
```

The wrapper checks that `uv` is installed, then runs the project's locked
sync and reports whether a C++ compiler is available. It does not install
system tools or download scientific data. The equivalent commands are:

```powershell
uv lock --check
uv sync --locked --all-groups
```

On macOS/Linux, the same commands work in a terminal. If using Brian2's C++
standalone backend, install a compiler separately: MSVC Build Tools on
Windows, Xcode Command Line Tools on macOS, or `g++` on Linux. No compiler is
required for the NumPy runtime used by the environment smoke test.

Run commands in the project environment without activating it:

```powershell
uv run --locked pytest -q
uv run --locked ruff check .
```

`pyproject.toml` declares direct dependencies; `uv.lock` pins the resolved
dependency graph for Windows and Linux CI. Do not edit `uv.lock` by hand.
The environment uses CPU-only PyTorch and `pandas < 3` for compatibility
with the connectome data clients. FlyGym is installed without its optional
`examples` extra. FlyVis is not required for the olfactory-system project.

## Download data (only when requested)

List supported static releases without accessing the network:

```powershell
uv run --locked python scripts/download_data.py --list
```

Download a selected release:

```powershell
uv run --locked python scripts/download_data.py --dataset door-v2.0.1
uv run --locked python scripts/download_data.py --dataset male-cns-v1.0-core
```

The downloader stores files under `data/`, resumes interrupted transfers
when the source supports HTTP range requests, validates available size and
checksum information, and writes local provenance metadata. Downloads are
never part of environment setup, tests, or CI. Raw data and generated
manifests are ignored by Git; see [`data/README.md`](data/README.md).

Hemibrain v1.2.1 and FlyWire v783 use the neuPrint and CAVE APIs. The Python
clients are installed in the same environment, but exporting those data is
deferred until the biological cell-type/ROI query is specified. Do not put
tokens in the repository. When API queries are added, use environment
variables or a local ignored `.env` file based on `.env.example`.

## Tests and CI

All tests are in `tests/`. Unit tests use small fixtures and mocked network
responses; they need no real connectome files or service credentials.
GitHub Actions runs the same lock, lint, and test checks on Python 3.12 for
Windows and Ubuntu.

## Project plan and license

[`PLAN.md`](PLAN.md) summarizes the agreed stages and gates. The current
scope is repository/environment preparation, not the biological analysis.
`LICENSE` is intentionally a placeholder and is not a license grant. Choose
an appropriate license before publishing the repository publicly.
