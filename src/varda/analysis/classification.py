"""Classification: train a classifier on the workspace's ROIs, classify the image."""

from __future__ import annotations

import numpy as np

from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.mlp import MlpClassifier
from varda.analysis.rasters import validPixels
from varda.common.entities import VardaRaster
from varda.common.parameter import FloatParameter, IntParameter
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

_PREDICT_CHUNK = 65_536


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
        rois = self.context.rois
        if rois is None:
            raise ValueError(
                "Training needs the workspace's ROIs; open the image in a workspace and draw them."
            )
        fids = rois.fids
        if len(fids) < 2:
            raise ValueError("Training needs at least two ROIs (one per class).")

        reportProgress(0, "reading image")
        cube = np.asarray(image.getData(), dtype=np.float64)
        valid = validPixels(cube, image.nodata)
        names = [rois.getROI(fid).name for fid in fids]

        reportProgress(5, "collecting training spectra")
        samples, labels = [], []
        for label, fid in enumerate(fids):
            mask = rois.getMask(fid, image) & valid
            samples.append(cube[mask])
            labels.append(np.full(int(mask.sum()), label))
        X, y = np.vstack(samples), np.concatenate(labels)
        if len(np.unique(y)) < 2:
            raise ValueError("At least two ROIs must contain valid pixels.")

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
        classes = np.argmax(probabilities, axis=1).astype(np.float64)

        bands = np.full(valid.shape + (1 + len(names),), np.nan, dtype=np.float32)
        bands[valid, 0] = classes
        bands[valid, 1:] = probabilities
        bandNames = ["Class", *[f"P({name})" for name in names]]
        source = ArrayDataSource(
            bands,
            wavelengths=np.array(bandNames),
            wavelengthUnits="classes",
            bandNames=bandNames,
            transform=image.transform,
            crs=image.crs,
            description=f"MLP classification of {image.name} trained on {len(names)} ROIs",
            extraMetadata={
                "classes": names,
                "layerSizes": model.layerSizes,
                "finalLoss": losses[-1],
            },
        )
        return VardaRaster(source, name=f"{image.name} MLP classes")
