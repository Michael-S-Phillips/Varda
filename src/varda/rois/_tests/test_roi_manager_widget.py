"""Tests for ROIManagerWidget plotting + denominator behavior."""

from types import SimpleNamespace

import numpy as np
from shapely.geometry import box

from varda.common.entities import Color, ROIMode
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_manager_widget import ROIManagerWidget

RED = Color(1.0, 0.0, 0.0, 0.5)
BLUE = Color(0.0, 0.0, 1.0, 0.5)


class _FakePlot:
    """Records plot() calls instead of drawing."""

    def __init__(self):
        self.calls = []

    def plot(self, x, y, color=None, name=None, **kwargs):
        self.calls.append(
            SimpleNamespace(x=np.asarray(x), y=np.asarray(y), color=color, name=name)
        )


def test_plot_spectrum_records_curve(qtbot, make_split_image):
    c = ROICollection()
    fid = c.addROI(box(2, 2, 8, 8), "roi", RED, ROIMode.RECTANGLE)
    plot = _FakePlot()
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), plot)
    w.plotSpectrum(fid)
    assert len(plot.calls) == 1
    np.testing.assert_array_almost_equal(plot.calls[0].y, [8.0, 8.0, 8.0])
    assert plot.calls[0].name == "roi"


def test_set_denominator_updates_model_and_emits(qtbot, make_split_image):
    c = ROICollection()
    fid = c.addROI(box(2, 2, 8, 8), "roi", RED, ROIMode.RECTANGLE)
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    with qtbot.waitSignal(w.sigDenominatorChanged, timeout=500) as sig:
        w.setDenominator(fid)
    assert w.denominatorFid == fid
    assert w.model.denominatorFid == fid
    assert sig.args == [fid]


def test_plot_ratio_without_denominator_does_nothing(
    qtbot, monkeypatch, make_split_image
):
    import varda.rois.roi_manager_widget as mod

    monkeypatch.setattr(mod.QMessageBox, "information", lambda *a, **k: None)
    c = ROICollection()
    fid = c.addROI(box(2, 2, 8, 8), "roi", RED, ROIMode.RECTANGLE)
    plot = _FakePlot()
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), plot)
    w.plotRatioSpectrum(fid)
    assert plot.calls == []


def test_plot_ratio_with_denominator_records_ratio(qtbot, make_split_image):
    c = ROICollection()
    num = c.addROI(box(2, 2, 8, 8), "num", RED, ROIMode.RECTANGLE)
    den = c.addROI(box(31, 2, 38, 8), "den", BLUE, ROIMode.RECTANGLE)
    plot = _FakePlot()
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), plot)
    w.setDenominator(den)
    w.plotRatioSpectrum(num)
    assert len(plot.calls) == 1
    np.testing.assert_array_almost_equal(plot.calls[0].y, [2.0, 2.0, 2.0])
    assert plot.calls[0].name == "num / den"


def test_removing_denominator_clears_it(qtbot, make_split_image):
    c = ROICollection()
    den = c.addROI(box(31, 2, 38, 8), "den", BLUE, ROIMode.RECTANGLE)
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    w.setDenominator(den)
    c.removeROI(den)
    assert w.denominatorFid is None
