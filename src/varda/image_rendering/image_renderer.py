import sys
from enum import Enum, auto

from PyQt6.QtCore import pyqtSignal, QObject, Qt, QSignalBlocker
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QStackedLayout,
    QApplication,
)
import numpy as np

from varda.common.parameter import (
    ParameterGroup,
    EnumParameter,
    FloatParameter,
    ParameterGroupWidget,
)
from varda.common.entities import VardaRaster
from varda.common.vec2 import Vec2
from varda.utilities import debug
from varda.image_rendering.render_parameters import (
    BandParameter,
    ColorMapParameter,
    StretchParameter,
)


class RenderMode(Enum):
    MONO = auto()
    RGB = auto()


class RgbBandGroup(ParameterGroup):
    red = BandParameter("Red Band")
    green = BandParameter("Green Band")
    blue = BandParameter("Blue Band")


class MonoViewGroup(ParameterGroup):
    band = BandParameter("Band")
    colorMap = ColorMapParameter("Color Map")


class RendererSettings(ParameterGroup):
    mode = EnumParameter("Mode", RenderMode, RenderMode.MONO)
    rgb = RgbBandGroup()
    mono = MonoViewGroup()
    stretch = StretchParameter("Stretch Algorithm")
    opacity = FloatParameter(
        "Opacity", 1.0, (0.0, 1.0), "%", "Opacity of the rendered image."
    )

    def __init__(self, image: VardaRaster, parent: QObject | None = None):
        super().__init__(parent)
        self.image = image
        for bandParam in (self.rgb.red, self.rgb.green, self.rgb.blue, self.mono.band):
            bandParam.setImage(image)
        # seed band selections from the image's default bands
        defaultBands = image.defaultBands
        self.rgb.red.value = int(defaultBands[0])
        self.rgb.green.value = int(defaultBands[1])
        self.rgb.blue.value = int(defaultBands[2])
        self.mono.band.value = int(defaultBands[0])

    def clone(self, parent: QObject | None = None) -> "RendererSettings":
        # RendererSettings needs the image at construction, unlike the base ParameterGroup
        # whose clone() calls self.__class__(parent) with no image.
        return RendererSettings(self.image, parent)


class ImageRenderer(QObject):
    sigShouldRefresh: pyqtSignal = pyqtSignal()

    def __init__(
        self,
        image: VardaRaster | None = None,
        settings: RendererSettings | None = None,
    ):
        super().__init__()
        if settings is not None:
            self.settings = settings
        elif image is not None:
            self.settings = RendererSettings(image)
        else:
            raise ValueError("Either image or settings must be provided.")
        self.image = self.settings.image
        self.cachedRender = None
        self._stretchedData = None  # latest render post-stretch but pre-colormap
        self._rawBandData = None  # extracted band data with no processing applied
        self.settings.sigParameterChanged.connect(self._onSettingsChanged)

    def _onSettingsChanged(self, *args) -> None:
        # any parameter (UI or programmatic) changed: drop caches and request a refresh
        self.cachedRender = None
        self._stretchedData = None
        self.sigShouldRefresh.emit()

    def render(self):
        """
        Render the image with the current band and stretch settings.
        Returns: numpy ndarray with shape (height, width, 4) representing an RGBA image.
        """
        if self.cachedRender is not None:
            return self.cachedRender
        if self.image is None or self.settings is None:
            raise ValueError("Image and settings must be set before rendering.")

        mode = self.settings.mode.get()
        if mode == RenderMode.MONO:
            # maintain 3D shape so stretch algorithms don't branch on 2d/3d
            data = self.image.getBands([int(self.settings.mono.band.get())])
        else:
            data = self.image.getBands(
                [
                    int(self.settings.rgb.red.get()),
                    int(self.settings.rgb.green.get()),
                    int(self.settings.rgb.blue.get()),
                ]
            )
        self._rawBandData = data

        if np.ma.isMaskedArray(data):
            data = data.filled(np.nan)

        data = self.settings.stretch.current.apply(data)
        self._stretchedData = data
        data[np.isnan(data)] = 0

        if mode == RenderMode.MONO:
            data = np.squeeze(data)  # back to 2D because ColorMap expects it
            lut = self.settings.mono.colorMap.get().getLookupTable(
                0, 1, 256, alpha=False
            )
            data = lut[(data * 255).astype(np.uint8)]
        else:
            data = (data * 255).astype(np.uint8)

        alpha = np.full(
            (data.shape[0], data.shape[1], 1),
            int(self.settings.opacity.get() * 255),
            dtype=np.uint8,
        )
        rgba = np.concatenate((data, alpha), axis=2)
        self.cachedRender = rgba
        return rgba

    def getStretchedData(self) -> np.ndarray:
        if self._stretchedData is None:
            self.render()
        assert self._stretchedData is not None
        return self._stretchedData

    def getRawBandData(self) -> np.ndarray:
        if self._rawBandData is None:
            self.render()
        assert self._rawBandData is not None
        return self._rawBandData

    def getMinMaxValues(self):
        if self.cachedRender is None:
            self.render()
        return self.settings.stretch.current.minMaxVals()

    def setManualStretch(self, lo: float, hi: float) -> None:
        """Switch to the manual stretch and set every channel to [lo, hi]."""
        manual = self.settings.stretch.option(StretchParameter.MANUAL_NAME)
        value = Vec2(float(lo), float(hi))
        # batch the param edits into a single refresh
        with QSignalBlocker(self.settings):
            manual.config.redStretch.set(value)
            manual.config.greenStretch.set(value)
            manual.config.blueStretch.set(value)
            self.settings.stretch.selectByName(StretchParameter.MANUAL_NAME)
        self.settings.sigParameterChanged.emit(self.settings)

    def setStretchMinMax(self, channel: int, lo: float, hi: float) -> None:
        """Set one channel's manual min/max (0=red, 1=green, 2=blue).

        When switching into the manual stretch, seed all channels from the current
        stretch's computed min/max so the other channels don't jump.
        """
        stretch = self.settings.stretch
        manual = stretch.option(StretchParameter.MANUAL_NAME)
        channelParams = [
            manual.config.redStretch,
            manual.config.greenStretch,
            manual.config.blueStretch,
        ]
        # batch all edits (seed + select + channel set) into a single refresh
        with QSignalBlocker(self.settings):
            if stretch.current is not manual:
                self.render()  # ensure the current stretch has computed its min/max
                seed = stretch.current.minMaxVals()
                if seed is not None:
                    mins = np.resize(
                        np.atleast_1d(np.asarray(seed[0], dtype=float)).ravel(), 3
                    )
                    maxs = np.resize(
                        np.atleast_1d(np.asarray(seed[1], dtype=float)).ravel(), 3
                    )
                    for i, param in enumerate(channelParams):
                        param.set(Vec2(float(mins[i]), float(maxs[i])))
                stretch.selectByName(StretchParameter.MANUAL_NAME)
            channelParams[channel].set(Vec2(float(lo), float(hi)))
        self.settings.sigParameterChanged.emit(self.settings)

    def getSettingsPanel(self) -> "RendererSettingsPanel":
        return RendererSettingsPanel(self.settings)


class RendererSettingsPanel(QWidget):
    """Panel for adjusting render settings, generated from the settings' parameters."""

    def __init__(self, settings: RendererSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Render Settings")
        self.settings = settings

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.setSpacing(2)

        # Mode
        layout.addWidget(QLabel("Mode:"))
        layout.addWidget(settings.mode.getWidget(self))

        # Band / colormap area, swapped by the mode parameter
        self.bandStack = QStackedLayout()
        self.bandStack.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._rgbIndex = self.bandStack.addWidget(settings.rgb.createWidget())
        self._monoIndex = self.bandStack.addWidget(settings.mono.createWidget())
        layout.addLayout(self.bandStack)
        self._syncBandStack()
        settings.mode.sigParameterChanged.connect(self._syncBandStack)

        # Stretch (self-contained combo + stacked sub-form)
        layout.addWidget(QLabel("Stretch Algorithm:"))
        layout.addWidget(settings.stretch.getWidget(self))

        # Opacity (labeled form row)
        layout.addWidget(ParameterGroupWidget([settings.opacity], self))

        self.setLayout(layout)

    def _syncBandStack(self, *args) -> None:
        isRgb = self.settings.mode.get() == RenderMode.RGB
        self.bandStack.setCurrentIndex(self._rgbIndex if isRgb else self._monoIndex)


if __name__ == "__main__":
    q_app = QApplication(sys.argv)
    image = debug.generate_random_image((100, 100, 10), (10, 10, 10))
    renderer = ImageRenderer(image)
    settingsPanel = renderer.getSettingsPanel()
    settingsPanel.show()
    q_app.exec()
