from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_runtime_imports_are_available_and_cpu_torch_works() -> None:
    assert sys.version_info[:2] == (3, 12)

    modules = [
        "caveclient",
        "flygym",
        "igraph",
        "matplotlib",
        "neuprint",
        "numpy",
        "pandas",
        "polars",
        "pyarrow",
        "requests",
        "scipy",
        "seaborn",
        "torch",
    ]
    imported = {name: importlib.import_module(name) for name in modules}

    assert imported["pandas"].__version__.split(".", maxsplit=1)[0] == "2"
    tensor = imported["torch"].ones(1)
    assert tensor.device.type == "cpu"
    assert tensor.tolist() == [1.0]


def test_brian2_numpy_runtime_updates_a_neuron(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    brian2 = importlib.import_module("brian2")
    original_target = brian2.prefs.codegen.target
    brian2.prefs.codegen.target = "numpy"
    try:
        neuron = brian2.NeuronGroup(
            1,
            "dv/dt = -v / (10*ms) : 1",
            method="euler",
        )
        neuron.v = 1
        network = brian2.Network(neuron)
        network.run(1 * brian2.ms)

        assert 0 < float(neuron.v[0]) < 1
    finally:
        brian2.prefs.codegen.target = original_target
