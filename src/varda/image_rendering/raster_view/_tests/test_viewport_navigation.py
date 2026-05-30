"""Tests for viewport navigation: the NavigableViewBox gesture contract and how
RegionController turns those gestures into ROI changes.

Gestures are exercised by calling the ViewBox's event handlers with lightweight fake
events (the same entry points pyqtgraph's scene would use), which keeps the tests free of
real windowing while still driving the production code paths.
"""

from contextlib import contextmanager

import numpy as np
import pytest
from psygnal import SignalInstance
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.region_controller import RegionController
from varda.rois.varda_roi import VardaROIItem


class _FakeWheelEvent:
    """Stand-in for QGraphicsSceneWheelEvent (only what NavigableViewBox.wheelEvent uses)."""

    def __init__(self, pos: QPointF, delta: int):
        self._pos = pos
        self._delta = delta

    def pos(self):
        return self._pos

    def delta(self):
        return self._delta

    def accept(self):
        pass


class _FakeDragEvent:
    """Stand-in for pyqtgraph's MouseDragEvent (only what NavigableViewBox uses)."""

    def __init__(
        self,
        pos: QPointF,
        downPos: QPointF,
        start=False,
        finish=False,
        button=Qt.MouseButton.LeftButton,
        modifiers=Qt.KeyboardModifier.NoModifier,
    ):
        self._pos = pos
        self._down = downPos
        self._start = start
        self._finish = finish
        self._button = button
        self._modifiers = modifiers

    def pos(self):
        return self._pos

    def lastPos(self):
        return self._down

    def buttonDownPos(self, btn=None):
        return self._down

    def button(self):
        return self._button

    def buttons(self):
        return self._button

    def modifiers(self):
        return self._modifiers

    def isStart(self):
        return self._start

    def isFinish(self):
        return self._finish

    def accept(self):
        pass


@contextmanager
def captures(signal: SignalInstance):
    """Record emissions of a psygnal signal within the block."""
    received: list[tuple] = []
    signal.connect(lambda *args: received.append(args))
    yield received


@pytest.fixture
def makeViewport(qtbot):
    """Factory for ready-to-use Imageviewports backed by a small in-memory raster."""

    def _make():
        data = (np.random.default_rng(0).random((64, 64, 3)) * 255).astype(np.uint8)
        raster = VardaRaster.fromDataSource(ArrayDataSource(data))
        viewport = ImageViewport(ImageRenderer(raster))
        qtbot.addWidget(viewport)
        viewport.resize(300, 300)
        viewport.show()
        qtbot.wait(10)  # let the ViewBox establish a valid transform
        return viewport

    return _make


class TestSelfNavigation:
    def test_self_navigating_zoom_changes_own_view(self, makeViewport):
        viewport = makeViewport()
        widthBefore = viewport.viewRect().width()

        with captures(viewport.sigViewRangeChangedManually) as emitted:
            viewport.viewBox.wheelEvent(_FakeWheelEvent(QPointF(150, 150), 120))

        assert emitted  # self-navigation reported the manual range change
        assert viewport.viewRect().width() < widthBefore  # scroll up zooms in

    def test_self_navigating_does_not_emit_gesture_signals(self, makeViewport):
        viewport = makeViewport()
        with captures(viewport.sigZoomed) as emitted:
            viewport.viewBox.wheelEvent(_FakeWheelEvent(QPointF(150, 150), 120))
        assert not emitted

    def test_disable_self_navigation_freezes_own_view(self, makeViewport):
        viewport = makeViewport()
        viewport.disableSelfNavigation()
        rectBefore = viewport.viewRect()

        viewport.viewBox.wheelEvent(_FakeWheelEvent(QPointF(150, 150), 120))

        assert viewport.viewRect() == rectBefore  # gesture no longer moves own view

    def test_disabled_viewport_emits_zoom_gesture(self, makeViewport):
        viewport = makeViewport()
        viewport.disableSelfNavigation()
        with captures(viewport.sigZoomed) as emitted:
            viewport.viewBox.wheelEvent(_FakeWheelEvent(QPointF(150, 150), 120))
        assert emitted  # gesture re-emitted instead of moving the view


class TestRegionController:
    @pytest.fixture
    def wired(self, makeViewport):
        """A source/target pair driven by a RegionController, as in the triple view."""
        source = makeViewport()
        target = makeViewport()
        target.disableSelfUpdating()
        target.disableSelfNavigation()
        roi = VardaROIItem.rectROI(
            (16, 16), (16, 16), -1, QColor(255, 0, 0, 0), aspectLocked=True
        )
        controller = RegionController(source, target, roi)
        return controller, source, target, roi

    def test_controller_shows_region_on_target(self, wired):
        _controller, _source, target, _roi = wired
        assert target.isShowingRegion

    def test_scroll_up_zooms_in_shrinks_roi(self, wired):
        _controller, _source, target, roi = wired
        sizeBefore = roi.size().x()
        target.viewBox.wheelEvent(_FakeWheelEvent(QPointF(150, 150), 120))
        assert roi.size().x() < sizeBefore

    def test_scroll_down_zooms_out_grows_roi(self, wired):
        _controller, _source, target, roi = wired
        sizeBefore = roi.size().x()
        target.viewBox.wheelEvent(_FakeWheelEvent(QPointF(150, 150), -120))
        assert roi.size().x() > sizeBefore

    def test_zoom_stays_within_source_bounds(self, wired):
        _controller, _source, target, roi = wired
        bounds = roi.maxBounds
        # Zoom out hard; the ROI must not grow beyond the source image extent.
        for _ in range(20):
            target.viewBox.wheelEvent(_FakeWheelEvent(QPointF(150, 150), -120))
        assert roi.size().x() <= bounds.width() + 1e-6
        assert roi.size().y() <= bounds.height() + 1e-6

    def test_drag_pans_roi(self, wired):
        _controller, _source, target, roi = wired
        posBefore = QPointF(roi.pos())

        down = QPointF(150, 150)
        target.viewBox.mouseDragEvent(_FakeDragEvent(down, down, start=True))
        target.viewBox.mouseDragEvent(_FakeDragEvent(QPointF(180, 180), down))
        target.viewBox.mouseDragEvent(
            _FakeDragEvent(QPointF(180, 180), down, finish=True)
        )

        assert roi.pos() != posBefore  # the drag moved the ROI on the source
