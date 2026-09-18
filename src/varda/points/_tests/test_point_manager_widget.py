"""The Points Manager lists saved points and can delete them."""

import numpy as np
from PyQt6.QtCore import Qt

from varda.common.entities import Color, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.points.point_collection import PointCollection
from varda.points.point_manager_widget import PointManagerWidget

RED = Color(1.0, 0.0, 0.0, 1.0)


def _image() -> VardaRaster:
    return VardaRaster(ArrayDataSource(np.zeros((10, 10, 3))), name="scene")


def _cell(widget, row, column) -> str:
    model = widget.model
    return model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole)


def test_table_lists_the_points_and_follows_the_collection(qtbot):
    points = PointCollection()
    widget = PointManagerWidget(points)
    qtbot.addWidget(widget)
    assert widget.model.rowCount() == 0

    points.addPixel(_image(), 3, 4, name="rock", color=RED)

    assert widget.model.rowCount() == 1
    assert _cell(widget, 0, 0) == "rock"
    assert _cell(widget, 0, 1) == "scene"
    assert (_cell(widget, 0, 2), _cell(widget, 0, 3)) == ("3", "4")


def test_delete_selected_removes_the_point(qtbot):
    points = PointCollection()
    first = points.addPixel(_image(), 1, 1, color=RED)
    second = points.addPixel(_image(), 2, 2, color=RED)
    widget = PointManagerWidget(points)
    qtbot.addWidget(widget)

    widget.table.selectRow(0)
    widget.deleteButton.click()

    assert points.fids == [second]
    assert first not in points.fids


def test_selecting_a_row_reports_its_fid(qtbot):
    points = PointCollection()
    points.addPixel(_image(), 1, 1, color=RED)
    fid = points.addPixel(_image(), 2, 2, color=RED)
    widget = PointManagerWidget(points)
    qtbot.addWidget(widget)
    seen = []
    widget.sigSelectionChanged.connect(seen.append)

    widget.table.selectRow(1)

    assert seen[-1] == fid
