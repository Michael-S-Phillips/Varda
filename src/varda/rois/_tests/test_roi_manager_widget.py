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
    """Records plot() and plotWithFill() calls instead of drawing."""

    def __init__(self):
        self.calls = []
        self.fillCalls = []

    def plot(self, x, y, color=None, name=None, **kwargs):
        self.calls.append(
            SimpleNamespace(x=np.asarray(x), y=np.asarray(y), color=color, name=name)
        )

    def plotWithFill(
        self, x, y, yLower, yUpper, fillBrush=None, color=None, name=None, **kwargs
    ):
        self.fillCalls.append(
            SimpleNamespace(
                x=np.asarray(x),
                y=np.asarray(y),
                yLower=np.asarray(yLower),
                yUpper=np.asarray(yUpper),
                color=color,
                name=name,
            )
        )


def test_plot_spectrum_records_filled_curve(qtbot, make_split_image):
    c = ROICollection()
    fid = c.addROI(box(2, 2, 8, 8), "roi", RED, ROIMode.RECTANGLE)
    plot = _FakePlot()
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), plot)
    w.plotSpectrum(fid)
    assert len(plot.fillCalls) == 1
    np.testing.assert_array_almost_equal(plot.fillCalls[0].y, [8.0, 8.0, 8.0])
    assert plot.fillCalls[0].name == "roi"


def test_plot_spectrum_fill_band_is_mean_plus_minus_std(qtbot):
    # A 2x2 ROI over pixels with values 1, 2, 3, 4 -> mean 2.5, std ~1.118.
    data = np.array(
        [[[1.0], [2.0]], [[3.0], [4.0]]], dtype=np.float64
    )  # shape (2, 2, 1)

    def get_data(bandIndices=None, window=None):
        if window is None:
            return data
        r, col, h, w = window
        return data[r : r + h, col : col + w, :]

    image = SimpleNamespace(
        width=2,
        height=2,
        bandCount=1,
        nodata=None,
        wavelengths=np.array([0.0]),
        wavelengthsType=float,
        getData=get_data,
    )
    c = ROICollection()
    fid = c.addROI(box(0, 0, 2, 2), "roi", RED, ROIMode.RECTANGLE)
    plot = _FakePlot()
    w = ROIManagerWidget(c, image, plot)
    w.plotSpectrum(fid)

    expected_std = float(np.std([1.0, 2.0, 3.0, 4.0]))  # population std, matches nanstd
    call = plot.fillCalls[0]
    np.testing.assert_array_almost_equal(call.y, [2.5])
    np.testing.assert_array_almost_equal(call.yLower, [2.5 - expected_std])
    np.testing.assert_array_almost_equal(call.yUpper, [2.5 + expected_std])


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


def test_set_template_updates_model_and_emits(qtbot, make_split_image):
    c = ROICollection()
    fid = c.addROI(box(2, 2, 8, 8), "tmpl", RED, ROIMode.RECTANGLE)
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    with qtbot.waitSignal(w.sigTemplateChanged, timeout=500) as sig:
        w.setTemplate(fid)
    assert w.templateFid == fid
    assert w.model.templateFid == fid
    assert sig.args == [fid]


def test_place_template_plain_paste(qtbot, make_split_image):
    # Non-georeferenced collection -> geometries stored in pixel space.
    c = ROICollection()
    tmpl = c.addROI(box(2, 2, 6, 6), "tmpl", RED, ROIMode.RECTANGLE)  # centroid (4,4)
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    w.setTemplate(tmpl)
    before = len(c)
    w.placeTemplate(clickRow=14, clickCol=20, lockColumn=False)
    assert len(c) == before + 1
    new_fid = c.fids[-1]
    coords = c.getPixelCoordinates(new_fid)
    cx, cy = coords[:, 0].mean(), coords[:, 1].mean()
    # Copy centroid lands at the click (dx = 20-4 = 16, dy = 14-4 = 10).
    assert abs(cx - 20) < 1e-6
    assert abs(cy - 14) < 1e-6


def test_place_template_noop_without_template(qtbot, make_split_image, monkeypatch):
    import varda.rois.roi_manager_widget as mod

    monkeypatch.setattr(mod.QMessageBox, "information", lambda *a, **k: None)
    c = ROICollection()
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    w.placeTemplate(clickRow=5, clickCol=5, lockColumn=False)
    assert len(c) == 0


def test_removing_template_clears_it(qtbot, make_split_image):
    c = ROICollection()
    fid = c.addROI(box(2, 2, 6, 6), "tmpl", RED, ROIMode.RECTANGLE)
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    w.setTemplate(fid)
    c.removeROI(fid)
    assert w.templateFid is None
