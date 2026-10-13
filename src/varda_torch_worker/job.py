"""Train a patch classifier on labeled pixels, then classify every valid pixel."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from torch import nn

from varda_torch_worker.models import (
    PatchCnn,
    PatchViT,
    predictProbabilities,
    trainClassifier,
)
from varda_torch_worker.patches import extractPatches, iterPatchChunks

# (progress fraction 0..1, message)
Progress = Callable[[float, str], None]
PATCH_CHUNK = 4_096
TRAINING_SHARE = 0.8  # of the progress range; the rest is classifying


def buildModel(spec: dict, bands: int, classes: int) -> nn.Module:
    params = spec["modelParams"]
    if spec["model"] == "cnn":
        return PatchCnn(bands, classes, params["channels"], params["convLayers"])
    if spec["model"] == "vit":
        return PatchViT(
            bands,
            classes,
            spec["patchSize"],
            params["embedDim"],
            params["heads"],
            params["layers"],
        )
    raise ValueError(f"Unknown model {spec['model']!r}")


def trainAndClassify(
    cube: np.ndarray,
    valid: np.ndarray,
    rows: np.ndarray,
    cols: np.ndarray,
    labels: np.ndarray,
    classes: int,
    spec: dict,
    progress: Progress,
) -> tuple[np.ndarray, float]:
    """(valid pixels x classes) probabilities and the final training loss.

    ``cube`` is (rows, cols, bands) float32 with invalid pixels already filled;
    ``rows``/``cols``/``labels`` are the training pixels.
    """
    size = int(spec["patchSize"])
    epochs = int(spec["epochs"])
    bands = cube.shape[2]
    training = extractPatches(cube, rows, cols, size)
    mean = training.reshape(-1, bands).mean(axis=0)
    std = training.reshape(-1, bands).std(axis=0)
    std = np.where(std > 0, std, 1.0)

    model = buildModel(spec, bands, classes)
    losses = trainClassifier(
        model,
        (training - mean) / std,
        labels,
        epochs=epochs,
        learningRate=float(spec["learningRate"]),
        batchSize=int(spec["batchSize"]),
        onEpoch=lambda epoch, loss: progress(
            TRAINING_SHARE * epoch / epochs, f"epoch {epoch}/{epochs}, loss {loss:.4f}"
        ),
    )

    total = int(valid.sum())
    done = 0
    probabilities = []
    for _r, _c, patches in iterPatchChunks(cube, valid, size, PATCH_CHUNK):
        probabilities.append(predictProbabilities(model, (patches - mean) / std))
        done += patches.shape[0]
        progress(
            TRAINING_SHARE + (1 - TRAINING_SHARE) * done / total,
            f"classified {done}/{total} pixels",
        )
    return np.vstack(probabilities), losses[-1]
