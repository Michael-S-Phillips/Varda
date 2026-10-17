"""CNN and ViT classifiers trained on ROI patches (optional PyTorch extra)."""

import numpy as np
import pytest
from shapely.geometry import box

import sys
from pathlib import Path

import varda_torch_worker
from varda.analysis import classification
from varda.analysis.analysis import AnalysisContext
from varda.analysis.classification import (
    CnnClassificationAnalysis,
    VitClassificationAnalysis,
)
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.optional_features.torch_runtime import TorchRuntime
from varda.rois.roi_collection import ROICollection

RED = Color(1.0, 0.0, 0.0, 0.5)
BLUE = Color(0.0, 0.0, 1.0, 0.5)


def _twoRegionImage(seed=0) -> VardaRaster:
    rng = np.random.default_rng(seed)
    cube = np.empty((20, 40, 8))
    cube[:, :20, :] = 0.2 + 0.02 * rng.normal(size=(20, 20, 8))
    cube[:, 20:, :] = 0.6 + 0.02 * rng.normal(size=(20, 20, 8))
    cube[0, 0, :] = -1.0
    return VardaRaster(ArrayDataSource(cube, nodata=-1.0), name="scene")


def _rois() -> ROICollection:
    rois = ROICollection()
    rois.addROI(box(2, 2, 8, 8), "dark", RED, ROIMode.RECTANGLE)
    rois.addROI(box(30, 10, 36, 16), "bright", BLUE, ROIMode.RECTANGLE)
    return rois


def test_torch_classifiers_are_filed_under_classification_and_need_rois():
    for analysis in (CnnClassificationAnalysis, VitClassificationAnalysis):
        assert analysis.category == "Classification"
        assert analysis.needsRois
        assert analysis.requirement == "PyTorch"


class _Runtime:
    """Stands in for the app-managed environment: runs jobs in a real worker
    process with this interpreter."""

    def __init__(self, installed: bool):
        self.installed = installed
        self.jobs = 0

    def isInstalled(self) -> bool:
        return self.installed

    def runJob(self, *args, **kwargs):
        self.jobs += 1
        runtime = TorchRuntime(
            root=Path("/unused"),
            uv=[],
            workerDir=Path(varda_torch_worker.__file__).parents[1],
            lockDir=Path("/unused"),
        )
        runtime.pythonPath = lambda: Path(sys.executable)  # ty: ignore[invalid-assignment]
        return runtime.runJob(*args, **kwargs)


def test_unavailable_without_torch_or_the_installed_environment(monkeypatch):
    monkeypatch.setattr(classification, "TORCH_AVAILABLE", False)
    monkeypatch.setattr(classification, "torchRuntime", lambda: _Runtime(False))
    assert not CnnClassificationAnalysis.isAvailable()
    assert not VitClassificationAnalysis.isAvailable()
    assert (
        CnnClassificationAnalysis.installable and VitClassificationAnalysis.installable
    )


def test_available_once_the_environment_is_installed(monkeypatch):
    monkeypatch.setattr(classification, "TORCH_AVAILABLE", False)
    monkeypatch.setattr(classification, "torchRuntime", lambda: _Runtime(True))
    assert CnnClassificationAnalysis.isAvailable()


def test_without_torch_in_process_the_job_runs_in_the_environment(monkeypatch):
    pytest.importorskip("torch")  # the stand-in worker uses this interpreter
    runtime = _Runtime(True)
    monkeypatch.setattr(classification, "TORCH_AVAILABLE", False)
    monkeypatch.setattr(classification, "torchRuntime", lambda: runtime)
    analysis = VitClassificationAnalysis()
    analysis.epochs.set(30)
    analysis.patchSize.set(3)
    analysis.setContext(AnalysisContext(rois=_rois()))
    progress = []
    result = analysis.run(_twoRegionImage(), lambda p, m: progress.append(p))
    assert runtime.jobs == 1
    classes = result.getData()[:, :, 0]
    assert np.mean(classes[3:17, 2:18] == 0) > 0.95
    assert np.mean(classes[3:17, 22:38] == 1) > 0.95
    assert progress == sorted(progress) and progress[-1] == 100


@pytest.mark.parametrize(
    "analysisClass, suffix",
    [
        (CnnClassificationAnalysis, "CNN classes"),
        (VitClassificationAnalysis, "ViT classes"),
    ],
)
def test_classifies_the_two_regions_from_roi_patches(analysisClass, suffix):
    pytest.importorskip("torch")
    image = _twoRegionImage()
    analysis = analysisClass()
    analysis.epochs.set(40)
    analysis.patchSize.set(3)
    analysis.setContext(AnalysisContext(rois=_rois()))

    result = analysis.run(image, lambda p, m: None)

    assert result.name == f"scene {suffix}"
    assert result.bandNames == ["Class", "P(dark)", "P(bright)"]
    classes = result.getData()[:, :, 0]
    assert np.mean(classes[3:17, 2:18] == 0) > 0.95
    assert np.mean(classes[3:17, 22:38] == 1) > 0.95
    assert np.isnan(classes[0, 0])
    assert result.extraMetadata["classes"] == ["dark", "bright"]
    metadata = result.extraMetadata
    assert metadata["seed"] == 0 and metadata["device"] in {"cpu", "cuda", "mps"}
    assert metadata["torchVersion"]
    description = result.dataSource.description
    assert "seed 0" in description and metadata["device"] in description


@pytest.mark.parametrize(
    "analysisClass", [CnnClassificationAnalysis, VitClassificationAnalysis]
)
def test_patch_classifiers_offer_a_seed_that_reaches_the_job(
    monkeypatch, analysisClass
):
    """The seed goes into the job spec (both paths run the same job), and the
    job's device and PyTorch version reach the result."""
    specs = []

    class _Job:
        @staticmethod
        def trainAndClassify(cube, valid, rows, cols, labels, classes, spec, progress):
            specs.append(spec)
            probabilities = np.tile([0.75, 0.25], (int(valid.sum()), 1))
            return probabilities, {"finalLoss": 0.1, "device": "cpu", "torch": "9.9"}

    monkeypatch.setattr(classification, "TORCH_AVAILABLE", True)
    monkeypatch.setattr(classification, "torch_job", _Job)
    analysis = analysisClass()
    assert analysis.seed.value == 0
    analysis.seed.set(11)
    analysis.setContext(AnalysisContext(rois=_rois()))
    result = analysis.run(_twoRegionImage(), lambda p, m: None)
    assert specs[-1]["seed"] == 11
    assert result.extraMetadata["device"] == "cpu"
    assert result.extraMetadata["torchVersion"] == "9.9"
    assert "seed 11" in result.dataSource.description
    assert "cpu" in result.dataSource.description
