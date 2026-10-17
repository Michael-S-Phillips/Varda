"""The runner writes the result to disk when the dialog asked for a file."""

import numpy as np

from varda.analysis.analysis import Analysis
from varda.analysis.runner import AnalysisRunner
from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_loading.image_loading_service import openDataSource
from varda.utilities.debug import generate_random_image


class _FirstBand(Analysis):
    analysisId = "first_band"
    name = "First Band"
    category = "Test"
    description = "copies the first band"

    def run(self, image, reportProgress):
        band = np.asarray(image.getData()[:, :, 0], dtype=np.float32)
        return VardaRaster(
            ArrayDataSource(band, bandNames=["first"]), name=f"{image.name} first"
        )


def test_result_is_saved_to_the_requested_path_and_still_joins_the_project(
    qtbot, tmp_path
):
    image = generate_random_image((20, 20, 10))
    images = ProjectImages([image])
    runner = AnalysisRunner(images)
    target = tmp_path / "first.img"

    with qtbot.waitSignal(runner.sigFinished, timeout=10_000) as blocker:
        runner.run(_FirstBand(), image, outputPath=str(target))

    (result,) = blocker.args
    assert result in images
    assert target.exists()
    loaded = openDataSource(str(target))
    np.testing.assert_array_equal(
        loaded.readAllBands()[:, :, 0],
        np.asarray(image.getData()[:, :, 0], dtype=np.float32),
    )
    assert loaded.bandNames == ["first"]


class _WithCompanion(_FirstBand):
    analysisId = "with_companion"

    def runAll(self, image, reportProgress):
        main = self.run(image, reportProgress)
        quality = VardaRaster(
            ArrayDataSource(np.ones((20, 20, 1), np.float32), bandNames=["q"]),
            name=f"{image.name} quality",
        )
        return [main, quality]


def test_companion_results_join_the_project_and_are_saved_beside(qtbot, tmp_path):
    image = generate_random_image((20, 20, 10))
    images = ProjectImages([image])
    runner = AnalysisRunner(images)
    target = tmp_path / "first.img"

    with qtbot.waitSignal(runner.sigFinished, timeout=10_000) as blocker:
        runner.run(_WithCompanion(), image, outputPath=str(target))

    (result,) = blocker.args
    companion = images[-1]
    assert result in images and companion.name.endswith(" quality")
    assert companion.extraMetadata["provenance"]["processId"] == "with_companion"
    assert target.exists()
    assert openDataSource(str(tmp_path / "first_quality.img")).bandNames == ["q"]


def test_without_a_path_nothing_is_written(qtbot, tmp_path):
    image = generate_random_image((20, 20, 10))
    runner = AnalysisRunner(ProjectImages([image]))

    with qtbot.waitSignal(runner.sigFinished, timeout=10_000):
        runner.run(_FirstBand(), image)

    assert list(tmp_path.iterdir()) == []
