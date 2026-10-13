"""Filtering: noise removal that keeps the image's bands."""

from __future__ import annotations

import numpy as np

from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.iovf import iovfFilter
from varda.analysis.rasters import readCube, sameBandsRaster
from varda.common.entities import VardaRaster
from varda.common.parameter import FloatParameter, IntParameter


class IovfAnalysis(Analysis):
    analysisId = "iovf"
    name = "Iterative Outlier Voting Filter (IOVF)"
    category = "Filtering"
    description = (
        "Removes isolated spikes without smoothing the spectra (Phillips et al. "
        "2023): Grubbs outlier tests vote on every voxel of the noise left after "
        "a smooth reference spectrum, and voxels most windows flag are replaced "
        "by their neighbors, round after round. Slow on large cubes."
    )

    windowRows = IntParameter(
        "Window Rows", 7, range=(3, 15), description="Odd number of pixels or bands"
    )
    windowColumns = IntParameter(
        "Window Columns", 5, range=(3, 15), description="Odd number of pixels or bands"
    )
    windowBands = IntParameter(
        "Window Bands", 5, range=(3, 15), description="Odd number of pixels or bands"
    )
    stopPercent = FloatParameter(
        "Stop Below",
        1.0,
        range=(0.0, 50.0),
        units="% of round 1",
        description=(
            "Stop once a round replaces fewer voxels than this share of the "
            "first round's; 0 runs until nothing is flagged (slower, with very "
            "little further change)."
        ),
        step=0.5,
    )

    def unavailableReason(self, image: VardaRaster) -> str:
        window = self._window()
        if any(w % 2 == 0 for w in window):
            return "Window sizes must be odd."
        if (
            image.height < window[0]
            or image.width < window[1]
            or image.bandCount < window[2]
        ):
            return "The image is smaller than the filter window."
        return ""

    def _window(self) -> tuple[int, int, int]:
        return (
            int(self.windowRows.value),
            int(self.windowColumns.value),
            int(self.windowBands.value),
        )

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        reportProgress(0, "reading image")
        cube, valid = readCube(image)  # missing bands filled; unusable pixels NaN
        result = iovfFilter(
            cube,
            self._window(),
            stopFraction=float(self.stopPercent.value) / 100.0,
            progress=lambda percent, message: reportProgress(
                5 + int(0.9 * percent), message
            ),
        )
        filtered = result.filtered
        filtered[~valid] = np.nan
        return sameBandsRaster(
            image,
            filtered,
            name=f"{image.name} IOVF",
            description=(
                f"IOVF of {image.name}: {sum(result.replaced)} voxels replaced in "
                f"{result.rounds} rounds"
            ),
        )
