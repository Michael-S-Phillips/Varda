"""The PyTorch worker: the job it runs and its command-line protocol."""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import varda_torch_worker
from varda_torch_worker.protocol import readResult, writeJob

torch = pytest.importorskip("torch")

from varda_torch_worker.job import trainAndClassify  # noqa: E402

SPEC = {
    "model": "cnn",
    "patchSize": 3,
    "epochs": 30,
    "learningRate": 1e-2,
    "batchSize": 64,
    "modelParams": {"channels": 8, "convLayers": 1},
}


def _scene():
    rng = np.random.default_rng(0)
    cube = np.empty((12, 24, 5), dtype=np.float32)
    cube[:, :12] = 0.2 + 0.02 * rng.normal(size=(12, 12, 5))
    cube[:, 12:] = 0.6 + 0.02 * rng.normal(size=(12, 12, 5))
    valid = np.ones((12, 24), dtype=bool)
    valid[0, 0] = False
    rows = np.array([3, 4, 5, 6, 3, 4, 5, 6])
    cols = np.array([3, 4, 5, 6, 17, 18, 19, 20])
    labels = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    return cube, valid, rows, cols, labels


def test_the_job_classifies_every_valid_pixel_and_reports_progress():
    cube, valid, rows, cols, labels = _scene()
    seen = []
    probabilities, finalLoss = trainAndClassify(
        cube, valid, rows, cols, labels, 2, SPEC, lambda f, m: seen.append(f)
    )
    assert probabilities.shape == (int(valid.sum()), 2)
    np.testing.assert_allclose(probabilities.sum(axis=1), 1.0, atol=1e-5)
    classes = np.full(valid.shape, -1)
    classes[valid] = probabilities.argmax(axis=1)
    assert np.mean(classes[2:10, 2:10] == 0) > 0.9
    assert np.mean(classes[2:10, 14:22] == 1) > 0.9
    assert finalLoss >= 0
    assert seen == sorted(seen) and seen[-1] == pytest.approx(1.0)


def _runWorker(jobDir: Path) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(varda_torch_worker.__file__).parents[1]),
    }
    return subprocess.run(
        [sys.executable, "-m", "varda_torch_worker", str(jobDir)],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )


def test_the_command_line_worker_streams_progress_and_writes_the_result(tmp_path):
    cube, valid, rows, cols, labels = _scene()
    writeJob(tmp_path, cube, valid, rows, cols, labels, classes=2, spec=SPEC)
    completed = _runWorker(tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    messages = [json.loads(line) for line in completed.stdout.splitlines()]
    assert all("progress" in m for m in messages) and messages[-1]["progress"] == 1.0
    probabilities, info = readResult(tmp_path)
    assert probabilities.shape == (int(valid.sum()), 2)
    assert info["device"] in {"cpu", "cuda", "mps"}
    assert "finalLoss" in info


def test_a_failing_job_reports_its_error_and_exits_nonzero(tmp_path):
    cube, valid, rows, cols, labels = _scene()
    writeJob(
        tmp_path,
        cube,
        valid,
        rows,
        cols,
        labels,
        classes=2,
        spec={**SPEC, "model": "nope"},
    )
    completed = _runWorker(tmp_path)
    assert completed.returncode != 0
    last = json.loads(completed.stdout.splitlines()[-1])
    assert "nope" in last["error"]


def test_the_probe_reports_the_torch_version_and_device():
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(varda_torch_worker.__file__).parents[1]),
    }
    completed = subprocess.run(
        [sys.executable, "-m", "varda_torch_worker", "--probe"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    probe = json.loads(completed.stdout.strip().splitlines()[-1])
    assert probe["torch"] == torch.__version__
    assert probe["device"] in {"cpu", "cuda", "mps"}
