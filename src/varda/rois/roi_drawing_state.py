"""What the next drawn ROI becomes: its shape and its class.

ROIs that share a name form a class (one material, drawn as several shapes).
Drawing keeps adding shapes to the active class until the user starts a new
class or picks another one. Shared by the ROI manager, the class picker shown
under a view while drawing, and the drawing tools.
"""

from __future__ import annotations

from dataclasses import dataclass

from psygnal import Signal
from shapely.geometry.base import BaseGeometry

from varda.common.entities import Color, ROIMode
from varda.common.palette import CLASS_PALETTE
from varda.rois.roi_collection import ROICollection

CLASS_ALPHA = "80"  # ROI fills are half transparent


@dataclass(frozen=True)
class ROIClass:
    name: str
    color: Color
    count: int  # its ROIs; 0 for a class started but not drawn yet


def _paletteColor(hexColor: str) -> Color:
    return Color.fromHexString(hexColor + CLASS_ALPHA)


class ROIDrawingState:
    sigShapeChanged = Signal(object)  # ROIMode
    sigActiveClassChanged = Signal(object)  # class name or None
    sigClassesChanged = Signal()

    def __init__(self, collection: ROICollection):
        self.collection = collection
        self.shape = ROIMode.FREEHAND
        self.activeClass: str | None = None
        # Colors of classes made active here, for when they have no ROIs
        self._colors: dict[str, Color] = {}
        for signal in (
            collection.sigROIAdded,
            collection.sigROIRemoved,
            collection.sigROIUpdated,
            collection.sigCollectionChanged,
        ):
            signal.connect(self._onCollectionChanged)

    def setShape(self, shape: ROIMode) -> None:
        if shape != self.shape:
            self.shape = shape
            self.sigShapeChanged.emit(shape)

    def classes(self) -> list[ROIClass]:
        """Classes in drawing order, plus the active class if it has no ROIs yet."""
        groups = self.collection.classes()
        names = list(groups)
        if self.activeClass is not None and self.activeClass not in groups:
            names.append(self.activeClass)
        return [ROIClass(n, self._colorOf(n), len(groups.get(n, []))) for n in names]

    def setActiveClass(self, name: str) -> None:
        if name == self.activeClass:
            return
        self._colors[name] = self._colorOf(name)  # remembered if its ROIs go
        self.activeClass = name
        self.sigActiveClassChanged.emit(name)
        self.sigClassesChanged.emit()

    def newClass(self) -> str:
        """Start a class with an unused name and color, and make it active."""
        taken = {c.name for c in self.classes()}
        number = 1
        while f"Class {number}" in taken:
            number += 1
        name = f"Class {number}"
        used = {c.color.toQColor().name() for c in self.classes()}
        free = [c for c in CLASS_PALETTE if c not in used]
        fallback = CLASS_PALETTE[len(taken) % len(CLASS_PALETTE)]
        self._colors[name] = _paletteColor(free[0] if free else fallback)
        self.setActiveClass(name)
        return name

    def addDrawnShape(self, geometry: BaseGeometry, roiType: ROIMode) -> int:
        """Add a drawn shape to the active class (starting one if needed)."""
        name = self.activeClass or self.newClass()
        return self.collection.addROI(geometry, name, self._colorOf(name), roiType)

    def _colorOf(self, name: str) -> Color:
        existing = self.collection.classColor(name)
        if existing is not None:
            return existing
        return self._colors.setdefault(name, _paletteColor(CLASS_PALETTE[0]))

    def _onCollectionChanged(self, *_args) -> None:
        self.sigClassesChanged.emit()
