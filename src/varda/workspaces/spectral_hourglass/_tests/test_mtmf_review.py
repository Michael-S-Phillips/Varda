"""Reviewing an MTMF result: thresholds on score and infeasibility pick the
detections."""

import numpy as np
import pytest

from varda.analysis.mapping import MapMethod, mapRaster
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.workspaces.spectral_hourglass.mtmf_review import MtmfReview


def _mtmfRaster() -> VardaRaster:
    rng = np.random.default_rng(0)
    image = VardaRaster(ArrayDataSource(np.zeros((20, 30, 3))), name="scene")
    n = 600
    mf = rng.normal(0.0, 0.1, size=(n, 2))
    infeasibility = np.abs(rng.normal(2.0, 0.5, size=(n, 2)))
    mf[:10, 1] = 0.9  # ten clean detections of endmember B
    infeasibility[:10, 1] = 1.0
    mf[10:15, 1] = 0.9  # five false alarms: high score, infeasible
    infeasibility[10:15, 1] = 20.0
    bands = np.column_stack([mf, infeasibility])
    names = ["A", "B"]
    bandNames = ["MF(A)", "MF(B)", "Infeasibility(A)", "Infeasibility(B)"]
    return mapRaster(
        image,
        np.arange(n),
        bands,
        bandNames,
        method=MapMethod.MTMF,
        names=names,
        colors=["#ff0000", "#00ff00"],
        detail="test",
    )


@pytest.fixture
def review(qtbot):
    widget = MtmfReview()
    qtbot.addWidget(widget)
    widget.setResult(_mtmfRaster())
    return widget


def test_lists_the_endmembers_of_the_result(review):
    assert [review.endmemberBox.itemText(i) for i in range(2)] == ["A", "B"]


def test_thresholds_select_high_score_feasible_pixels(review, qtbot):
    review.endmemberBox.setCurrentIndex(1)
    with qtbot.waitSignal(review.sigDetectionsChanged) as blocker:
        review.setThresholds(minScore=0.5, maxInfeasibility=5.0)
    mask, color = blocker.args
    assert mask.shape == (20, 30) and color == "#00ff00"
    flat = mask.ravel()
    assert flat[:10].all() and not flat[10:15].any()
    assert flat.sum() == 10
    assert "10 pixels" in review.summary.text()


def test_dragging_the_lines_changes_the_thresholds(review):
    review.endmemberBox.setCurrentIndex(1)
    review.scoreLine.setValue(0.8)
    review.infeasibilityLine.setValue(30.0)
    assert review.detections().ravel().sum() == 15


def test_detections_raster_keeps_scores_only_where_detected(review):
    review.endmemberBox.setCurrentIndex(1)
    review.setThresholds(minScore=0.5, maxInfeasibility=5.0)
    raster = review.detectionsRaster()
    assert raster.name == "scene MTMF detections B"
    values = raster.getData()[:, :, 0].ravel()
    assert np.isfinite(values).sum() == 10 and values[0] == pytest.approx(0.9)
