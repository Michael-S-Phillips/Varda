"""The Subset dialog's preview: drag a box on the image to choose rows and
columns, see the box's mean spectrum, and drag ranges on it to choose the
bands, all kept in step with the typed settings."""

import numpy as np
import pytest
from PyQt6.QtCore import QPointF

from varda.analysis.crop_preview import CropPreview
from varda.analysis.geometry import SubsetAnalysis
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

WL = np.linspace(1000.0, 2000.0, 11)  # 100 nm apart


def _image():
    rows, cols, bands = np.mgrid[0:40, 0:60, 0:11]
    data = (rows * 100 + cols + bands * 0.5).astype(np.float32)
    return VardaRaster(
        ArrayDataSource(
            data,
            wavelengths=WL,
            wavelengthUnits="nm",
            extraMetadata={"bbl": [1] * 10 + [0]},  # the last band is bad
        ),
        name="cube",
    )


@pytest.fixture
def preview(qtbot):
    image = _image()
    analysis = SubsetAnalysis()
    analysis.prepareFor(image)
    widget = analysis.createPreviewWidget(image)
    assert isinstance(widget, CropPreview)
    qtbot.addWidget(widget)
    return analysis, widget


def test_dragging_the_box_sets_the_rows_and_columns(preview):
    analysis, widget = preview
    widget.box.setPos(QPointF(10, 5))  # left 10, top 5
    widget.box.setSize(QPointF(20, 8))
    widget.box.sigRegionChangeFinished.emit(widget.box)
    assert (analysis.firstRow.value, analysis.lastRow.value) == (6, 13)
    assert (analysis.firstColumn.value, analysis.lastColumn.value) == (11, 30)


def test_typed_rows_and_columns_move_the_box(preview):
    analysis, widget = preview
    analysis.firstRow.set(3)
    analysis.lastColumn.set(25)
    x, y = widget.box.pos()
    width, _ = widget.box.size()
    assert (x, y) == (0, 2) and width == 25


def test_the_spectrum_is_the_boxs_mean_without_bad_bands(preview):
    analysis, widget = preview
    analysis.firstRow.set(11)
    analysis.lastRow.set(20)  # rows 10-19: mean 14.5
    analysis.firstColumn.set(1)
    analysis.lastColumn.set(10)  # columns 0-9: mean 4.5
    x, y = widget.curve.getData()
    np.testing.assert_allclose(x, WL)
    np.testing.assert_allclose(y[:10], 1450 + 4.5 + 0.5 * np.arange(10))
    assert np.isnan(y[10])


def test_dragging_ranges_on_the_spectrum_chooses_the_bands(preview):
    analysis, widget = preview
    assert len(widget.spans) == 1  # every band, to start
    widget.spans[0].setRegion((1150, 1450))  # bands 3-5
    widget.spans[0].sigRegionChangeFinished.emit(widget.spans[0])
    assert analysis.bands.value == "3-5"
    widget.addRange()
    widget.spans[1].setRegion((1750, 1950))  # bands 9-10
    widget.spans[1].sigRegionChangeFinished.emit(widget.spans[1])
    assert analysis.bands.value == "3-5, 9-10"
    widget.removeSpan(widget.spans[0])
    assert analysis.bands.value == "9-10"
    widget.keepAll()
    assert analysis.bands.value == "" and len(widget.spans) == 1


def test_typed_bands_show_as_ranges(preview):
    analysis, widget = preview
    analysis.bands.set("2-4, 8")
    assert [tuple(round(v) for v in s.getRegion()) for s in widget.spans] == [
        (1050, 1350),
        (1650, 1750),
    ]


def test_the_row_and_column_ranges_fit_the_image(preview):
    analysis, _ = preview
    assert analysis.lastRow.range == (1, 40) and analysis.lastColumn.range == (1, 60)
