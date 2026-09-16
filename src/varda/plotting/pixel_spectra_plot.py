"""A plot for exploring pixel spectra from viewport clicks.

Spectra either accumulate (Collect) or supersede the previous one (Replace), and
each new spectrum takes the next color of a user-selected palette so it reads as
new. Pixel curves are tracked separately from other curves (e.g. library spectra
added for comparison), so Replace and Clear only touch spectra that came from
clicks.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from enum import Enum
from pathlib import Path

import matplotlib
from PyQt6.QtWidgets import QCheckBox, QPushButton, QWidget

from varda.common.entities import Color, VardaRaster
from varda.common.parameter import EnumParameter, ParameterGroup
from varda.common.ui import ButtonBuilder, HBoxBuilder, SectionBox, VBoxBuilder
from varda.plotting.library_spectra import DEFAULT_LIBRARY_PATH
from varda.plotting.plot import Curve, VardaPlotWidget

logger = logging.getLogger(__name__)


class SpectrumMode(Enum):
    COLLECT = 1
    REPLACE = 2


class ColorScheme(Enum):
    """matplotlib colormaps; values are the colormap names.

    Qualitative palettes (a handful of distinct entries) are cycled entry by
    entry. Continuous maps are sampled at ``CONTINUOUS_STEPS`` evenly spread
    positions and then cycle, so successive spectra stay clearly distinct
    instead of taking near-identical neighbouring shades.
    """

    # qualitative
    TAB10 = "tab10"
    TAB20 = "tab20"
    SET1 = "Set1"
    SET2 = "Set2"
    DARK2 = "Dark2"
    PAIRED = "Paired"
    ACCENT = "Accent"
    # continuous
    VIRIDIS = "viridis"
    PLASMA = "plasma"
    INFERNO = "inferno"
    MAGMA = "magma"
    CIVIDIS = "cividis"
    TURBO = "turbo"
    SPECTRAL = "Spectral"
    COOLWARM = "coolwarm"


# Distinct samples taken from a continuous colormap before it cycles.
CONTINUOUS_STEPS = 8
# Colormaps with at most this many entries are treated as qualitative palettes.
_MAX_QUALITATIVE_ENTRIES = 24


def paletteColor(scheme: ColorScheme, index: int) -> Color:
    """The ``index``-th color of the scheme, cycling past its end."""
    colormap = matplotlib.colormaps[scheme.value]
    if colormap.N <= _MAX_QUALITATIVE_ENTRIES:
        r, g, b, _a = colormap(index % colormap.N)
    else:
        position = (index % CONTINUOUS_STEPS) / (CONTINUOUS_STEPS - 1)
        r, g, b, _a = colormap(position)
    return Color(float(r), float(g), float(b), 1.0)


class PixelSpectraConfig(ParameterGroup):
    mode = EnumParameter(
        "Mode",
        SpectrumMode,
        SpectrumMode.COLLECT,
        "Collect keeps every clicked spectrum; Replace shows only the latest.",
    )
    colorScheme = EnumParameter(
        "Color Scheme",
        ColorScheme,
        ColorScheme.TAB10,
        "Palette cycled through so each new spectrum is distinct.",
    )


class PixelSpectraPlotWidget(VardaPlotWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        libraryPath: Path = DEFAULT_LIBRARY_PATH,
    ):
        super().__init__(parent, libraryPath)
        self.pixelConfig = PixelSpectraConfig()
        self.pixelCurves: list[Curve] = []
        self._colorIndex = 0

        # Multi-plot controls; a workspace's PixelSpectraDocks wires these up.
        # Standalone, the box stays checked and the button does nothing.
        self.activeCheckBox = QCheckBox("Receives pixel clicks")
        self.activeCheckBox.setChecked(True)
        self.activeCheckBox.setToolTip("Ctrl+click pixel selections are plotted here")
        self.newPlotButton = QPushButton("New Pixel Plot")
        self.newPlotButton.setToolTip(
            "Open another plot, e.g. to collect spectra from a different region"
        )

        # Directly after the base widget's "View" section
        self.insertSidebarSection(
            1,
            SectionBox(
                "Pixel Spectra",
                VBoxBuilder()
                .withWidget(self.pixelConfig.createWidget())
                .withWidget(self.activeCheckBox)
                .withLayout(
                    HBoxBuilder()
                    .withWidget(
                        ButtonBuilder("Clear Spectra").onClick(self.clearPixelSpectra)
                    )
                    .withWidget(self.newPlotButton)
                ),
            ),
        )

    def addPixelSpectrum(self, image: VardaRaster, x: int, y: int) -> Curve | None:
        """Plot the spectrum at pixel (x, y); returns None if out of bounds."""
        curves = self.addPixelSpectra([image], x, y)
        return curves[0] if curves else None

    def addPixelSpectra(
        self,
        images: Sequence[VardaRaster],
        x: int,
        y: int,
        *,
        labelWithImageName: bool = False,
    ) -> list[Curve]:
        """Plot the spectrum at pixel (x, y) of each image as one selection.

        In Replace mode the previous selection is cleared once, so every image
        of this selection stays. Images where (x, y) is out of bounds are
        skipped; a selection that hits no image leaves the plot unchanged.
        """
        inBounds = []
        for image in images:
            if 0 <= x < image.width and 0 <= y < image.height:
                inBounds.append(image)
            else:
                logger.warning(
                    f"Pixel ({x}, {y}) is outside the bounds of {image.name}"
                )
        if not inBounds:
            return []
        self._applyMode()

        curves = []
        for image in inBounds:
            spectrum = image.getSpectrum(x, y)
            wavelengths = self.getPlottableWavelengths(image, len(spectrum.values))
            label = (
                f"{image.name} ({x}, {y})"
                if labelWithImageName
                else f"Pixel ({x}, {y})"
            )
            curves.append(self._addTracked(wavelengths, spectrum.values, label))
        return curves

    def addSpectrum(self, wavelengths, values, label: str) -> Curve:
        """Plot any spectrum under the pixel-plot rules (mode and palette)."""
        return self.addSpectra([(wavelengths, values, label)])[0]

    def addSpectra(self, entries: Sequence[tuple]) -> list[Curve]:
        """Plot several (wavelengths, values, label) spectra as one selection:
        Replace mode clears once, so all of them stay."""
        self._applyMode()
        return [self._addTracked(w, v, label) for w, v, label in entries]

    def _applyMode(self) -> None:
        if self.pixelConfig.mode.value is SpectrumMode.REPLACE:
            self.clearPixelSpectra()

    def _addTracked(self, wavelengths, values, label: str) -> Curve:
        curve = self.plot(wavelengths, values, color=self._nextColor(), name=label)
        self.pixelCurves.append(curve)
        return curve

    def clearPixelSpectra(self) -> None:
        for curve in list(self.pixelCurves):
            self.removePlot(curve)
        self._colorIndex = 0

    def removePlot(self, curve: Curve) -> None:
        super().removePlot(curve)
        if curve in self.pixelCurves:
            self.pixelCurves.remove(curve)

    def _referenceCurve(self) -> Curve | None:
        """Prefer the latest pixel spectrum over other curves when none is selected."""
        if self.selectedCurve is None and self.pixelCurves:
            return self.pixelCurves[-1]
        return super()._referenceCurve()

    def _nextColor(self) -> Color:
        scheme = self.pixelConfig.colorScheme.value
        assert isinstance(scheme, ColorScheme)
        color = paletteColor(scheme, self._colorIndex)
        self._colorIndex += 1
        return color
