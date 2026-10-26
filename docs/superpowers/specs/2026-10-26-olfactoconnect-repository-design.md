# OlfactoConnect Repository Design

## Intent

Create a small, GitHub-ready local repository that lets two collaborators reproduce one Python environment, obtain explicitly selected project datasets, and verify the setup without beginning the biological analysis. It should implement the environment and data-provenance groundwork from Stage 0 of `Olf_coop (1).docx` and leave the existing visual-motor prototype untouched.

## Goals

- Create a new Git repository at `E:\OlfactoConnect`; do not copy, modify, or remove files from the existing prototype.
- Provide a single Python 3.12 environment managed by `uv`, declared in `pyproject.toml` and locked in `uv.lock`.
- Provide a small setup wrapper that delegates environment creation and installation to `uv sync --locked` rather than maintaining a second package-install list.
- Provide a separate, explicit data-download command. Setup and CI must not download datasets or require service credentials.
- Download only a requested dataset, resume interrupted HTTP downloads where the source supports byte ranges, verify known checksums and file sizes, write a provenance manifest, keep raw data outside Git, and never silently replace a valid local file.
- Include root `tests/`, a working GitHub Actions workflow, README, Stage 0 project plan, and a clearly marked, non-binding LICENSE placeholder.

## Agreed research-plan scope

- The scientific core is R1 (ORN→PN transformation: normalization/decorrelation) and R2 (replication across MaleCNS, hemibrain, and FlyWire, including sex-related differences). R3 (Kenyon cells/odor valence and possible embodied exploration) remains an extension.
- Stage 0 establishes the repository/environment, literature notes, and a reproducible DM2/DC2 pilot. Stage 1 obtains and versions data, graph/mapping tables, DoOR parsing, validation data, and coverage reports; G1 proposes at least 70% glomerular coverage and at least one usable PN dataset. Stage 2 implements Brian2 LIF, a PyTorch rate model, baselines, predeclared metrics, calibration, sensitivity, and inhibition ablation; G2 requires qualitative effects and performance beyond baselines. Stage 3 runs the common pipeline on the three datasets and analyzes sex; G3 requires robustness or explained differences. Stage 4 extensions are optional and allowed only after G2/G3; Stage 5 prepares release, DOI, paper material, and full reproducibility.
- This repository task implements only the environment/repository/download tooling. It does not run the pilot, calculate G1 coverage, query graph data, or implement scientific models.

## Non-goals

- Do not build or use Docker.
- Do not run G1, inspect cell-type/ROI coverage, query connectome graphs, construct mappings, or begin R1/R2 model work.
- Do not download real datasets while creating or testing the repository.
- Do not include datasets, tokens, `.venv`, generated results, or large binaries in Git.
- Do not create a GitHub remote or publish the repository.
- Do not carry the old visual-motor implementation or FlyVis source into the new repository.

## Decisions

### Repository and environment

- Target: `E:\OlfactoConnect`; if it unexpectedly exists at execution time, inspect it and do not overwrite user content.
- Initialize a local Git repository only after the new project files are ready.
- Pin the interpreter line to Python 3.12 (`.python-version` and `requires-python = ">=3.12,<3.13"`).
- Use one `uv` project and one lockfile for the project. `uv.lock` is generated and checked in; it is never edited by hand. The setup wrapper invokes `uv sync --locked` and reports a clear error if `uv` is unavailable.
- Keep `pandas < 3` because the existing project investigation found CAVEclient/Pandas 3 compatibility unverified. Install FlyGym 2.1's base package without the `examples` extra, which requests Pandas 3; do not install FlyVis, which is for the visual system.
- Declare only libraries needed by the planned workflows: Brian2; NumPy/SciPy; pandas; PyArrow/Polars; igraph; Matplotlib/Seaborn; CPU-only PyTorch; neuprint-python; CAVEclient; requests/python-dotenv; and FlyGym 2.1 base without its `examples` extra. Keep pytest/Ruff available in the same `.venv` for development and CI. Do not add DVC/MLflow/RDKit merely because they were in the prototype.
- Report whether a C++ compiler is available and document the OS prerequisite for Brian2 C++ standalone; the setup must not silently install system-wide compilers or require administrator rights. A basic environment smoke test should exercise Brian2's NumPy runtime mode, which does not require that compiler.

### Data and credentials

- Use explicit dataset selection; never download datasets as a side effect of environment setup.
- Initial static sources are DoOR 2.0.1 (`door_response_matrix.csv`, `door_mappings.csv`) from the tagged `ropensci/DoOR.data` release and the minimal MaleCNS v1.0 tables needed by the plan (annotations, neurotransmitter predictions, and aggregated connection weights). Pin the known DoOR SHA-256 values and the published MaleCNS byte counts; calculate and record MaleCNS SHA-256 on download. Do not fetch synapse-point/partner or t-bar tables by default.
- Install neuPrint and CAVE clients and document their use for hemibrain v1.2.1 and FlyWire v783. Do not perform broad API exports or invent olfactory filters before the biological mapping/ROI decisions in the research plan exist.
- Keep downloaded raw data under ignored `data/`; record dataset/release, source URL, retrieval time, byte count, and SHA-256 in a local manifest. Hard-code expected hashes where verified; otherwise compute and record the observed hash and validate the published size when available.
- Keep the small dataset registry/configuration in a tracked code/config path, not inside an ignored data payload directory. Track only `data/README.md`; ignore downloaded files and generated manifests.
- Read API tokens from environment variables or an ignored `.env`; provide `.env.example` with names only. Never print token values, place them in URLs, or write them to manifests/logs.

### Tests, CI, and documentation

- Put all tests under root `tests/`. Unit tests use temporary directories and mocked HTTP/API responses; no test requires a real token, live neuPrint/CAVE service, or large dataset.
- CI runs on Python 3.12, checks the lockfile, installs the same locked environment, runs Ruff and pytest, and does not fetch data.
- `README.md` documents Windows-first setup, the equivalent `uv` commands, optional compiler prerequisites, explicit data-download commands, credential handling, dataset sources, and the fact that setup does not start scientific analysis.
- `PLAN.md` records the stages and gates from the agreed DOCX, marking the current scope as environment/repository preparation only.
- `LICENSE` is a placeholder that explicitly says licensing is pending and grants no rights until the collaborators select and replace it.

## Success criteria

- A fresh clone can recreate the Python 3.12 environment from `pyproject.toml` and `uv.lock` without Docker.
- Setup succeeds or fails with an actionable message and does not download datasets.
- The data command lists known datasets and downloads only the selected source; tests prove checksum/size errors cannot leave a corrupt final file and existing data is not overwritten without an explicit force option.
- CI can run without API secrets or scientific data and passes the same lint/test commands documented in the README.
- The repository contains no actual dataset payloads or credentials.
