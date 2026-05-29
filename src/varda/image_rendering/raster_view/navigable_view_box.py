import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal, QPointF, Qt


class NavigableViewBox(pg.ViewBox):
    """A ViewBox that can either navigate itself or hand its gestures to a controller.

    pyqtgraph's ViewBox already implements pan (`mouseDragEvent`) and zoom (`wheelEvent`)
    cleanly, anchoring zoom at the cursor and respecting the aspect lock. We keep that
    behaviour for self-navigation. When self-navigation is turned off, we instead
    translate the same gestures into high-level signals (in view/data coordinates) so an
    external controller (e.g. RegionController) can decide what they mean — without the
    ViewBox moving its own view.

    Because these are the ViewBox's own event methods, a gesture only reaches them when no
    child item (such as an ROI) claimed the press first, so "don't pan while dragging an
    ROI" is handled by the scene rather than by manual hit-testing.
    """

    # Emitted only while self-navigation is disabled. Positions are in view (data) coords.
    sigPanStarted = pyqtSignal(QPointF)  # press position
    sigPanned = pyqtSignal(QPointF, QPointF)  # (current position, start position)
    sigPanEnded = pyqtSignal()
    # (scaleFactor, anchorFraction): scaleFactor < 1 zooms in; anchorFraction is the cursor
    # position normalised to [0, 1] within the current view rect.
    sigZoomed = pyqtSignal(float, QPointF)

    zoomFactor: float = 1.2  # View scale change per wheel notch (120 units)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._selfNavigating = True

    def setSelfNavigating(self, enabled: bool):
        """Whether gestures pan/zoom this ViewBox itself (True) or are emitted as
        signals for an external controller to handle (False)."""
        self._selfNavigating = enabled

    def mouseDragEvent(self, ev, axis=None):
        if self._selfNavigating:
            super().mouseDragEvent(ev, axis)
            return

        # Only left-drag (no modifier) is a navigation gesture; ignore everything else
        # so it can fall through to other handlers (e.g. context menu).
        if (
            ev.button() != Qt.MouseButton.LeftButton
            or ev.modifiers() != Qt.KeyboardModifier.NoModifier
        ):
            return

        ev.accept()
        # The view doesn't move (self-navigation is off), so mapToView is stable across
        # the drag and start-relative deltas are well defined.
        startView = self.mapToView(ev.buttonDownPos())
        currentView = self.mapToView(ev.pos())
        if ev.isStart():
            self.sigPanStarted.emit(startView)
        self.sigPanned.emit(currentView, startView)
        if ev.isFinish():
            self.sigPanEnded.emit()

    def wheelEvent(self, ev, axis=None):
        if self._selfNavigating:
            super().wheelEvent(ev, axis)
            return

        delta = ev.delta()
        if delta == 0:
            return
        ev.accept()

        # delta > 0 (scroll up) -> scaleFactor < 1 -> zoom in.
        scaleFactor = self.zoomFactor ** (-delta / 120.0)

        rect = self.viewRect()
        cursorView = self.mapToView(ev.pos())
        fracX = max(0.0, min(1.0, (cursorView.x() - rect.left()) / rect.width()))
        fracY = max(0.0, min(1.0, (cursorView.y() - rect.top()) / rect.height()))
        self.sigZoomed.emit(scaleFactor, QPointF(fracX, fracY))

    def keyPressEvent(self, ev):
        # Disable the ViewBox's arrow-key range navigation.
        ev.ignore()
