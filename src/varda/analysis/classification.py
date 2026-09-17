"""Classification: train a classifier on the workspace's ROIs, classify the image.

One class per ROI. Every classifier produces the same result image: a Class
band (0-based ROI index) plus one probability band per class, with the class
names in the metadata.
"""

from __future__ import annotations

from types import ModuleType
from typing import ClassVar

import numpy as np

from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.mlp import MlpClassifier
from varda.analysis.patches import extractPatches, iterPatchChunks
from varda.analysis.rasters import validPixels
from varda.common.entities import VardaRaster
from varda.common.parameter import FloatParameter, IntParameter
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.rois.roi_collection import ROICollection

torch_models: ModuleType | None
try:
    from varda.analysis import torch_models as _torchModels

    torch_models = _torchModels
    TORCH_AVAILABLE = True
except ImportError:  # the optional "ml" extra (PyTorch) is not installed
    torch_models = None
    TORCH_AVAILABLE = False

_PREDICT_CHUNK = 65_536
_PATCH_CHUNK = 4_096


def _trainingSet(
    rois: ROICollection, image: VardaRaster, valid: np.ndarray
) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray]:
    """Class names and the (rows, cols, labels) of valid pixels inside each ROI."""
    if len(rois) < 2:
        raise ValueError("Training needs at least two ROIs (one per class).")
    names, rows, cols, labels = [], [], [], []
    for label, fid in enumerate(rois.fids):
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


class MlpClassificationAnalysis(Analysis):
    analysisId = "mlp_classification"
    name = "Train MLP on ROIs"
    category = "Classification"
    description = (
        "Trains a multi-layer perceptron on the spectra inside each ROI of the "
        "current workspace (one class per ROI) and classifies every pixel. The "
        "result has a Class band (0-based ROI index) and one probability band "
        "per class."
    )
    needsRois = True

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
        cube = np.asarray(image.getData(), dtype=np.float64)
        valid = validPixels(cube, image.nodata)

        reportProgress(5, "collecting training spectra")
        names, rows, cols, y = _trainingSet(rois, image, valid)
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


class _PatchClassificationAnalysis(Analysis):
    """Shared plumbing for the PyTorch classifiers: patches around ROI pixels
    as training data, chunked whole-image prediction."""

    category = "Classification"
    needsRois = True
    requirement = "PyTorch"
    suffix: ClassVar[str] = ""
    # Declared here, supplied by each subclass (ParameterGroup only picks up
    # Parameters defined directly on the class).
    patchSize: IntParameter
    epochs: IntParameter
    learningRate: FloatParameter
    batchSize: IntParameter

    @classmethod
    def isAvailable(cls) -> bool:
        return TORCH_AVAILABLE

    def _buildModel(self, bands: int, classes: int, patchSize: int):
        raise NotImplementedError

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        if torch_models is None:
            raise ImportError("PyTorch is not installed; install Varda's 'ml' extra.")
        rois = _requireRois(self)
        size = int(self.patchSize.value) | 1  # odd
        epochs = int(self.epochs.value)
        batchSize = int(self.batchSize.value)

        reportProgress(0, "reading image")
        cube = np.asarray(image.getData(), dtype=np.float32)
        valid = validPixels(cube, image.nodata)
        # Patches may straddle invalid pixels: neutralise those with band means.
        bandMeans = cube[valid].mean(axis=0)
        cube[~valid] = bandMeans

        reportProgress(5, "collecting training patches")
        names, rows, cols, y = _trainingSet(rois, image, valid)
        training = extractPatches(cube, rows, cols, size)
        mean = training.reshape(-1, cube.shape[2]).mean(axis=0)
        std = training.reshape(-1, cube.shape[2]).std(axis=0)
        std = np.where(std > 0, std, 1.0)

        model = self._buildModel(cube.shape[2], len(names), size)
        losses = torch_models.trainClassifier(
            model,
            (training - mean) / std,
            y,
            epochs=epochs,
            learningRate=float(self.learningRate.value),
            batchSize=batchSize,
            onEpoch=lambda epoch, loss: reportProgress(
                5 + int(75 * epoch / epochs), f"epoch {epoch}/{epochs}, loss {loss:.4f}"
            ),
        )

        reportProgress(80, "classifying image")
        total = int(valid.sum())
        done = 0
        probabilities = []
        for _r, _c, patches in iterPatchChunks(cube, valid, size, _PATCH_CHUNK):
            probabilities.append(
                torch_models.predictProbabilities(model, (patches - mean) / std)
            )
            done += patches.shape[0]
            reportProgress(
                80 + int(20 * done / total), f"classified {done}/{total} pixels"
            )

        return _classificationRaster(
            image,
            valid,
            np.vstack(probabilities),
            names,
            suffix=self.suffix,
            metadata={"patchSize": size, "finalLoss": losses[-1]},
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

    patchSize = _patchSizeParameter()
    channels = IntParameter("Channels", 32, range=(4, 256))
    convLayers = IntParameter("Conv Layers", 2, range=(1, 4))
    epochs = _epochsParameter()
    learningRate = _learningRateParameter()
    batchSize = _batchSizeParameter()

    def _buildModel(self, bands, classes, patchSize):
        assert torch_models is not None
        return torch_models.PatchCnn(
            bands, classes, int(self.channels.value), int(self.convLayers.value)
        )


class VitClassificationAnalysis(_PatchClassificationAnalysis):
    analysisId = "vit_classification"
    name = "Train ViT on ROIs"
    description = (
        "Trains a small vision transformer whose tokens are the pixel spectra "
        "of the patch around each ROI pixel, and classifies every pixel from "
        "its neighbourhood."
    )
    suffix = "ViT classes"

    patchSize = _patchSizeParameter()
    embedDim = IntParameter("Embedding Size", 64, range=(8, 512))
    heads = IntParameter("Attention Heads", 4, range=(1, 16))
    layers = IntParameter("Transformer Layers", 2, range=(1, 8))
    epochs = _epochsParameter()
    learningRate = _learningRateParameter()
    batchSize = _batchSizeParameter()

    def _buildModel(self, bands, classes, patchSize):
        assert torch_models is not None
        return torch_models.PatchViT(
            bands,
            classes,
            patchSize,
            int(self.embedDim.value),
            int(self.heads.value),
            int(self.layers.value),
        )
