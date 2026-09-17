"""The contract every analysis implements."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from varda.common.entities import VardaRaster
from varda.common.parameter import ParameterGroup

# (percent 0-100, message)
ProgressCallback = Callable[[int, str], None]


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
    # Processing-menu submenu the analysis is listed under.
    category: ClassVar[str] = "General"
    # What the analysis needs when isAvailable() is False, e.g. "HyPyRameter".
    requirement: ClassVar[str] = ""

    @classmethod
    def isAvailable(cls) -> bool:
        """False when an optional dependency the analysis needs is missing."""
        return True

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        raise NotImplementedError
