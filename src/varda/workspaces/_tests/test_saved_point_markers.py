"""Saved points stay marked on the image(s) as circles in their colour."""

import numpy as np
from psygnal import Signal
from PyQt6.QtCore import QPointF

from varda.common.entities import Color, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.points.point_collection import PointCollection
from varda.workspaces.saved_point_markers import SavedPointMarkers

RED = Color(1.0, 0.0, 0.0, 1.0)


class FakeMarker:
    def __init__(self, pos: QPointF, color, symbol: str) -> None:
        self.pos, self.color, self.symbol = pos, color, symbol
        self.removed = False
        self.highlighted = False

    def setPos(self, pos: QPointF) -> None:
        self.pos = pos

    def setColor(self, color) -> None:
        self.color = color

    def setHighlighted(self, highlighted: bool) -> None:
        self.highlighted = highlighted

    def setVisible(self, visible: bool) -> None:
        pass

    def remove(self) -> None:
        self.removed = True


class FakeViewport:
    sigImageChanged = Signal()  # fires when the shown region (local coords) moves

    def __init__(self) -> None:
        self.markers: list[FakeMarker] = []
        self.offset = np.array([0.0, 0.0])

    def pixelToLocalCoords(self, pixelCoords: np.ndarray) -> np.ndarray:
        return np.asarray(pixelCoords, dtype=float) - self.offset

    def addPointOverlay(self, pos: QPointF, color, symbol: str = "x") -> FakeMarker:
        marker = FakeMarker(pos, color, symbol)
        self.markers.append(marker)
        return marker

    def live(self) -> list[FakeMarker]:
        return [m for m in self.markers if not m.removed]


def _image() -> VardaRaster:
    return VardaRaster(ArrayDataSource(np.zeros((10, 10, 3))), name="scene")


def test_saved_points_are_drawn_as_circles_and_follow_the_collection(qtbot):
    points = PointCollection()
    viewports = [FakeViewport(), FakeViewport()]
    markers = SavedPointMarkers(points, viewports)
    fid = points.addPixel(_image(), 3, 4, color=RED)

    for viewport in viewports:
        (marker,) = viewport.live()
        assert (marker.pos.x(), marker.pos.y()) == (3.5, 4.5)
        assert marker.symbol == "o"
        assert marker.color == RED.toQColor()

    points.removePoint(fid)
    assert viewports[0].live() == []
    del markers


def test_saved_markers_follow_a_viewport_whose_shown_region_moves(qtbot):
    points = PointCollection()
    viewport = FakeViewport()
    markers = SavedPointMarkers(points, [viewport])
    points.addPixel(_image(), 3, 4, color=RED)

    viewport.offset = np.array([2.0, 1.0])
    viewport.sigImageChanged.emit()

    (marker,) = viewport.live()
    assert (marker.pos.x(), marker.pos.y()) == (1.5, 3.5)
    del markers


def test_a_selected_point_is_highlighted(qtbot):
    points = PointCollection()
    viewport = FakeViewport()
    markers = SavedPointMarkers(points, [viewport])
    first = points.addPixel(_image(), 1, 1, color=RED)
    points.addPixel(_image(), 2, 2, color=RED)

    markers.highlight(first)

    assert [m.highlighted for m in viewport.live()] == [True, False]
    markers.highlight(None)
    assert [m.highlighted for m in viewport.live()] == [False, False]
