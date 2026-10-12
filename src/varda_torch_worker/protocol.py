"""The files a worker job reads and writes, and its stdout messages.

A job directory holds ``job.json`` (the model spec and class count) and the
arrays ``cube.npy`` (rows, cols, bands; float32, invalid pixels already
filled), ``valid.npy``, ``rows.npy``, ``cols.npy`` and ``labels.npy``. The
worker prints one JSON object per line: ``{"progress": 0..1, "message": ...}``
while it runs and ``{"error": ..., "traceback": ...}`` if it fails. On success
it writes ``probabilities.npy`` (valid pixels in row-major order, by class)
and ``result.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

JOB_FILE = "job.json"
RESULT_FILE = "result.json"
PROBABILITIES_FILE = "probabilities.npy"
ARRAYS = ("cube", "valid", "rows", "cols", "labels")


def writeJob(
    jobDir: Path | str,
    cube: np.ndarray,
    valid: np.ndarray,
    rows: np.ndarray,
    cols: np.ndarray,
    labels: np.ndarray,
    *,
    classes: int,
    spec: dict,
) -> None:
    jobDir = Path(jobDir)
    for name, array in zip(ARRAYS, (cube, valid, rows, cols, labels)):
        np.save(jobDir / f"{name}.npy", array)
    (jobDir / JOB_FILE).write_text(json.dumps({"classes": classes, "spec": spec}))


def readJob(jobDir: Path | str) -> tuple[dict[str, np.ndarray], int, dict]:
    jobDir = Path(jobDir)
    arrays = {name: np.load(jobDir / f"{name}.npy") for name in ARRAYS}
    job = json.loads((jobDir / JOB_FILE).read_text())
    return arrays, job["classes"], job["spec"]


def writeResult(jobDir: Path | str, probabilities: np.ndarray, info: dict) -> None:
    np.save(Path(jobDir) / PROBABILITIES_FILE, probabilities)
    (Path(jobDir) / RESULT_FILE).write_text(json.dumps(info))


def readResult(jobDir: Path | str) -> tuple[np.ndarray, dict]:
    jobDir = Path(jobDir)
    info = json.loads((jobDir / RESULT_FILE).read_text())
    return np.load(jobDir / PROBABILITIES_FILE), info
