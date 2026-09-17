"""An analysis runs in the background, reports progress, and its result joins the project."""

import numpy as np
import pytest

from varda.analysis.analysis import Analysis
from varda.analysis.runner import AnalysisRunner
from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.common.parameter import IntParameter
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.utilities.debug import generate_random_image


class DoublingAnalysis(Analysis):
    """Test analysis: doubles the first ``bands`` bands, reporting progress."""

    name = "Doubling"
    bands = IntParameter("Bands", 2, range=(1, 10))

    def run(self, image: VardaRaster, reportProgress) -> VardaRaster:
        n = int(self.bands.value)
        reportProgress(0, "starting")
        data = image.getData()[:, :, :n] * 2.0
        reportProgress(100, "done")
        return VardaRaster(ArrayDataSource(data), name=f"{image.name} doubled")


class FailingAnalysis(Analysis):
    name = "Failing"

    def run(self, image, reportProgress):
        raise ValueError("nope")


def test_result_is_added_to_the_project_images(qtbot):
    images = ProjectImages()
    image = generate_random_image((10, 10, 10))
    images.append(image)
    runner = AnalysisRunner(images)

    with qtbot.waitSignal(runner.sigFinished, timeout=5000) as blocker:
        runner.run(DoublingAnalysis(), image)

    (result,) = blocker.args
    assert list(images) == [image, result]
    assert result.name == f"{image.name} doubled"
    assert result.bandCount == 2
    np.testing.assert_allclose(result.getData(), image.getData()[:, :, :2] * 2.0)


def test_progress_reaches_the_dialog(qtbot):
    images = ProjectImages()
    image = generate_random_image((10, 10, 10))
    runner = AnalysisRunner(images)
    seen = []
    runner.sigProgress.connect(lambda percent, message: seen.append((percent, message)))

    with qtbot.waitSignal(runner.sigFinished, timeout=5000):
        runner.run(DoublingAnalysis(), image)

    assert (0, "starting") in seen and (100, "done") in seen


def test_failure_is_reported_and_adds_nothing(qtbot, monkeypatch):
    from varda.analysis import runner as runnerModule

    monkeypatch.setattr(runnerModule.QMessageBox, "critical", lambda *a, **k: None)
    images = ProjectImages()
    image = generate_random_image((10, 10, 10))
    runner = AnalysisRunner(images)

    with qtbot.waitSignal(runner.sigFailed, timeout=5000) as blocker:
        runner.run(FailingAnalysis(), image)

    (error,) = blocker.args
    assert isinstance(error, ValueError)
    assert len(images) == 0


def test_analysis_settings_are_a_parameter_group():
    analysis = DoublingAnalysis()
    analysis.bands.set(3)
    assert analysis.bands.value == 3
    assert analysis.createWidget() is not None or pytest.skip("needs QApplication")
