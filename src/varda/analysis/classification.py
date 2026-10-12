"""Classification: train a classifier on the workspace's ROIs, classify the image.

One class per ROI. Every classifier produces the same result image: a Class
band (0-based ROI index) plus one probability band per class, with the class
names in the metadata.
"""

from __future__ import annotations

from collections.abc import Sequence
from types import ModuleType
from typing import ClassVar

import numpy as np

from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.mlp import MlpClassifier
from varda.analysis.rasters import readCube
from varda.common.entities import VardaRaster
from varda.common.parameter import FloatParameter, IntParameter, MultiChoiceParameter
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.optional_features.torch_runtime import TorchRuntime, defaultRuntime
from varda.rois.roi_collection import ROICollection

# PyTorch runs in-process when Varda's own environment has it (the "ml"
# extra); otherwise in the environment that Processing > Optional Features
# installs.
torch_job: ModuleType | None
try:
    from varda_torch_worker import job as _torchJob

    torch_job = _torchJob
    TORCH_AVAILABLE = True
except ImportError:
    torch_job = None
    TORCH_AVAILABLE = False


def torchRuntime() -> TorchRuntime:
    return defaultRuntime()


_PREDICT_CHUNK = 65_536


def roiLabels(rois: ROICollection) -> list[tuple[int, str]]:
    """(fid, label) for every ROI; ROIs sharing a name are told apart by id."""
    names = [rois.getROI(fid).name for fid in rois.fids]
    return [
        (fid, f"{name} (ROI {fid})" if names.count(name) > 1 else name)
        for fid, name in zip(rois.fids, names)
    ]


def _trainingSet(
    rois: ROICollection, image: VardaRaster, valid: np.ndarray, fids: Sequence[int]
) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray]:
    """Class names and the (rows, cols, labels) of valid pixels inside each of
    the chosen ROIs."""
    if len(fids) < 2:
        raise ValueError("Training needs at least two ROIs (one per class).")
    names, rows, cols, labels = [], [], [], []
    for label, fid in enumerate(fids):
        names.append(rois.getROI(fid).name)
        mask = rois.getMask(fid, image) & valid
        r, c = np.nonzero(mask)
        rows.append(r)
        cols.append(c)
        labels.append(np.full(r.size, label))
    y = np.concatenate(labels)
    if len(np.unique(y)) < 2:
        raise ValueError("At least two ROIs must contain valid pixels.")
    return names, np.concatenate(rows), np.concatenate(cols), y


def _requireRois(analysis: Analysis) -> ROICollection:
    rois = analysis.context.rois
    if rois is None:
        raise ValueError(
            "Training needs the workspace's ROIs; open the image in a workspace "
            "and draw them."
        )
    return rois


def _roiChoiceParameter() -> MultiChoiceParameter:
    # Each analysis declares its own copy: ParameterGroup only picks up
    # Parameters defined directly on the class.
    return MultiChoiceParameter(
        "ROIs (one class each)",
        description="Which of the workspace's ROIs to train on; all of them by default.",
    )


class _RoiTrainingAnalysis(Analysis):
    """Shared plumbing for classifiers trained on the workspace's ROIs: the
    user ticks which ROIs become classes."""

    category = "Classification"
    needsRois = True
    rois: MultiChoiceParameter  # declared here, assigned by each subclass

    def prepareFor(self, image: VardaRaster) -> None:
        collection = self.context.rois
        labels = [label for _, label in roiLabels(collection)] if collection else []
        # Keep the user's selection when the same ROIs are offered again
        kept = [label for label in self.rois.get() if label in labels]
        self.rois.setChoices(labels, selected=kept if kept else None)

    def unavailableReason(self, image: VardaRaster) -> str:
        collection = self.context.rois
        if collection is None or len(collection) < 2:
            return ""  # the dialog already explains missing ROIs
        if self.rois.choices and len(self.rois.get()) < 2:
            return "Tick at least two ROIs (one class each)."
        return ""

    def _chosenFids(self, collection: ROICollection) -> list[int]:
        labels = roiLabels(collection)
        if not self.rois.choices:  # never prepared for an image: every ROI
            return [fid for fid, _ in labels]
        chosen = set(self.rois.get())
        return [fid for fid, label in labels if label in chosen]


def _classificationRaster(
    image: VardaRaster,
    valid: np.ndarray,
    probabilities: np.ndarray,
    names: list[str],
    *,
    suffix: str,
    metadata: dict,
) -> VardaRaster:
    bands = np.full(valid.shape + (1 + len(names),), np.nan, dtype=np.float32)
    bands[valid, 0] = np.argmax(probabilities, axis=1)
    bands[valid, 1:] = probabilities
    bandNames = ["Class", *[f"P({name})" for name in names]]
    source = ArrayDataSource(
        bands,
        wavelengths=np.array(bandNames),
        wavelengthUnits="classes",
        bandNames=bandNames,
        transform=image.transform,
        crs=image.crs,
        description=f"{suffix} of {image.name} trained on {len(names)} ROIs",
        extraMetadata={"classes": names, **metadata},
    )
    return VardaRaster(source, name=f"{image.name} {suffix}")


class MlpClassificationAnalysis(_RoiTrainingAnalysis):
    analysisId = "mlp_classification"
    name = "Train MLP on ROIs"
    description = (
        "Trains a multi-layer perceptron on the spectra inside the chosen ROIs "
        "of the current workspace (one class per ROI) and classifies every "
        "pixel. The result has a Class band (0-based class index) and one "
        "probability band per class."
    )

    rois = _roiChoiceParameter()
    hiddenLayers = IntParameter("Hidden Layers", 2, range=(1, 6))
    neuronsPerLayer = IntParameter("Neurons Per Layer", 32, range=(2, 512))
    epochs = IntParameter("Epochs", 200, range=(1, 5000))
    learningRate = FloatParameter(
        "Learning Rate",
        0.01,
        range=(1e-5, 1.0),
        step=0.001,
        decimals=5,
        showSlider=False,
    )

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        rois = _requireRois(self)
        reportProgress(0, "reading image")
        cube, valid = readCube(image)

        reportProgress(5, "collecting training spectra")
        names, rows, cols, y = _trainingSet(rois, image, valid, self._chosenFids(rois))
        X = cube[rows, cols]

        model = MlpClassifier(
            hiddenLayers=int(self.hiddenLayers.value),
            neuronsPerLayer=int(self.neuronsPerLayer.value),
        )
        epochs = int(self.epochs.value)
        losses = model.fit(
            X,
            y,
            epochs=epochs,
            learningRate=float(self.learningRate.value),
            onEpoch=lambda epoch, loss: reportProgress(
                5 + int(80 * epoch / epochs), f"epoch {epoch}/{epochs}, loss {loss:.4f}"
            ),
        )

        reportProgress(88, "classifying image")
        pixels = cube[valid]
        probabilities = np.vstack(
            [
                model.predictProbabilities(pixels[start : start + _PREDICT_CHUNK])
                for start in range(0, pixels.shape[0], _PREDICT_CHUNK)
            ]
        )
        return _classificationRaster(
            image,
            valid,
            probabilities,
            names,
            suffix="MLP classes",
            metadata={"layerSizes": model.layerSizes, "finalLoss": losses[-1]},
        )


def _patchSizeParameter() -> IntParameter:
    return IntParameter(
        "Patch Size",
        5,
        range=(1, 15),
        description="Square neighbourhood in pixels (odd)",
    )


def _epochsParameter() -> IntParameter:
    return IntParameter("Epochs", 50, range=(1, 2000))


def _learningRateParameter() -> FloatParameter:
    return FloatParameter(
        "Learning Rate",
        0.001,
        range=(1e-6, 0.1),
        step=0.0001,
        decimals=6,
        showSlider=False,
    )


def _batchSizeParameter() -> IntParameter:
    return IntParameter("Batch Size", 64, range=(4, 4096))


class _PatchClassificationAnalysis(_RoiTrainingAnalysis):
    """Shared plumbing for the PyTorch classifiers: patches around ROI pixels
    as training data, chunked whole-image prediction."""

    requirement = "PyTorch"
    installable = True
    suffix: ClassVar[str] = ""
    modelKey: ClassVar[str] = ""  # the worker's model: "cnn" or "vit"
    # Declared here, supplied by each subclass (ParameterGroup only picks up
    # Parameters defined directly on the class).
    patchSize: IntParameter
    epochs: IntParameter
    learningRate: FloatParameter
    batchSize: IntParameter

    @classmethod
    def isAvailable(cls) -> bool:
        return TORCH_AVAILABLE or torchRuntime().isInstalled()

    def _modelParams(self) -> dict[str, int]:
        raise NotImplementedError

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        rois = _requireRois(self)
        runtime = None if TORCH_AVAILABLE else torchRuntime()
        if runtime is not None and not runtime.isInstalled():
            raise ImportError(
                "PyTorch is not installed; install it from Processing > Optional Features."
            )
        spec = {
            "model": self.modelKey,
            "patchSize": int(self.patchSize.value) | 1,  # odd
            "epochs": int(self.epochs.value),
            "learningRate": float(self.learningRate.value),
            "batchSize": int(self.batchSize.value),
            "modelParams": self._modelParams(),
        }

        reportProgress(0, "reading image")
        cube, valid = readCube(image)
        cube = cube.astype(np.float32)
        # Patches may straddle invalid pixels: neutralise those with band means.
        cube[~valid] = cube[valid].mean(axis=0)

        reportProgress(5, "collecting training patches")
        names, rows, cols, y = _trainingSet(rois, image, valid, self._chosenFids(rois))

        def onProgress(fraction: float, message: str) -> None:
            reportProgress(5 + round(95 * fraction), message)

        if runtime is None:
            assert torch_job is not None
            probabilities, finalLoss = torch_job.trainAndClassify(
                cube, valid, rows, cols, y, len(names), spec, onProgress
            )
        else:
            probabilities, info = runtime.runJob(
                cube, valid, rows, cols, y,
                classes=len(names), spec=spec, progress=onProgress,
            )  # fmt: skip
            finalLoss = info["finalLoss"]

        return _classificationRaster(
            image,
            valid,
            probabilities,
            names,
            suffix=self.suffix,
            metadata={"patchSize": spec["patchSize"], "finalLoss": finalLoss},
        )


class CnnClassificationAnalysis(_PatchClassificationAnalysis):
    analysisId = "cnn_classification"
    name = "Train CNN on ROIs"
    description = (
        "Trains a small convolutional network on spatial-spectral patches "
        "around the pixels of each ROI (bands as channels) and classifies "
        "every pixel from its neighbourhood."
    )
    suffix = "CNN classes"

    rois = _roiChoiceParameter()
    patchSize = _patchSizeParameter()
    channels = IntParameter("Channels", 32, range=(4, 256))
    convLayers = IntParameter("Conv Layers", 2, range=(1, 4))
    epochs = _epochsParameter()
    learningRate = _learningRateParameter()
    batchSize = _batchSizeParameter()

    modelKey = "cnn"

    def _modelParams(self) -> dict[str, int]:
        return {
            "channels": int(self.channels.value),
            "convLayers": int(self.convLayers.value),
        }


class VitClassificationAnalysis(_PatchClassificationAnalysis):
    analysisId = "vit_classification"
    name = "Train ViT on ROIs"
    description = (
        "Trains a small vision transformer whose tokens are the pixel spectra "
        "of the patch around each ROI pixel, and classifies every pixel from "
        "its neighbourhood."
    )
    suffix = "ViT classes"

    rois = _roiChoiceParameter()
    patchSize = _patchSizeParameter()
    embedDim = IntParameter("Embedding Size", 64, range=(8, 512))
    heads = IntParameter("Attention Heads", 4, range=(1, 16))
    layers = IntParameter("Transformer Layers", 2, range=(1, 8))
    epochs = _epochsParameter()
    learningRate = _learningRateParameter()
    batchSize = _batchSizeParameter()

    modelKey = "vit"

    def _modelParams(self) -> dict[str, int]:
        return {
            "embedDim": int(self.embedDim.value),
            "heads": int(self.heads.value),
            "layers": int(self.layers.value),
        }
