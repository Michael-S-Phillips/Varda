"""The contract every analysis implements."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

import attrs
from PyQt6.QtWidgets import QWidget

from varda.common.entities import VardaRaster
from varda.common.parameter import ParameterGroup
from varda.rois.roi_collection import ROICollection

# (percent 0-100, message)
ProgressCallback = Callable[[int, str], None]


SUBMENU = "/"  # separates the levels of a category path


def categoryLevels(category: str) -> list[str]:
    """The menus a category sits in, outermost first:
    "Filtering/Spatial" -> ["Filtering", "Filtering/Spatial"]."""
    parts = [part.strip() for part in category.split(SUBMENU)]
    return [SUBMENU.join(parts[: i + 1]) for i in range(len(parts))]


def categoryTitle(category: str) -> str:
    """How a category reads in text: "Filtering → Spatial"."""
    return " → ".join(category.split(SUBMENU))


@attrs.frozen
class AnalysisContext:
    """What the workspace offers an analysis beyond the image itself."""

    rois: ROICollection | None = None


class Analysis(ParameterGroup):
    """An analysis turns one image into a new image that joins the project.

    Subclasses declare their settings as class-level Parameters — the settings
    UI is generated from them — and implement ``run``. ``run`` executes in a
    background thread: it must not touch widgets, and should call
    ``reportProgress`` as it goes.
    """

    # Stable identifier used in action ids (snake_case).
    analysisId: ClassVar[str] = "analysis"
    name: ClassVar[str] = "Analysis"
    description: ClassVar[str] = ""
    # Processing-menu submenu the analysis is listed under; "/" nests submenus
    # ("Filtering/Spatial" is the Spatial submenu of Filtering).
    category: ClassVar[str] = "General"
    # What the analysis needs when isAvailable() is False, e.g. "HyPyRameter".
    requirement: ClassVar[str] = ""
    # True when Varda can install the requirement itself (Optional Features).
    installable: ClassVar[bool] = False
    # Whether the analysis trains on / uses the workspace's ROIs.
    needsRois: ClassVar[bool] = False
    # "<name> <version>" of the plugin that added it ("" for Varda's own);
    # recorded in results' provenance.
    plugin: ClassVar[str] = ""

    def __init__(self) -> None:
        super().__init__()
        self.context = AnalysisContext()

    def setContext(self, context: AnalysisContext) -> None:
        self.context = context

    @classmethod
    def isAvailable(cls) -> bool:
        """False when an optional dependency the analysis needs is missing."""
        return True

    def prepareFor(self, image: VardaRaster) -> None:
        """Adapt the settings to the image about to be analyzed, e.g. offer the
        choices its wavelengths support. Called on the GUI thread whenever the
        dialog's image changes, before the settings widget is (re)built."""

    def unavailableReason(self, image: VardaRaster) -> str:
        """Why this analysis cannot run on ``image`` (shown instead of Run), or
        "" when it can."""
        return ""

    def createPreviewWidget(self, image: VardaRaster) -> QWidget | None:
        """An optional widget shown below the settings, e.g. a plot that helps
        choose them. Rebuilt whenever the image changes."""
        return None

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        raise NotImplementedError
