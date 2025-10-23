from dataclasses import dataclass, field
import logging

from PyQt6.QtCore import pyqtSlot, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QWidget,
    QFormLayout,
    QComboBox,
    QButtonGroup,
    QRadioButton,
    QHBoxLayout,
    QStackedLayout,
    QVBoxLayout,
)
import pyqtgraph as pg
from pyqtgraph import ColorMap
import numpy as np

import varda.utilities.debug
from varda.common.entities import Image
from varda.image_loading import ImageLoadingService
from varda.image_rendering.stretch_management_and_histogram.stretch_algorithms import (
    stretchAlgorithmRegistry,
    StretchAlgorithm,
    NoStretch,
)

logger = logging.getLogger(__name__)


@dataclass
class RendererSettings:
    mode: str = "mono"
    bands: np.ndarray[tuple[int], np.dtype[np.uint]] = field(
        default_factory=lambda: np.zeros(3, dtype=np.uint)
    )
    stretch: StretchAlgorithm = field(
        default_factory=lambda: stretchAlgorithmRegistry["No Stretch"]()
    )
    # default to a simple black-to-white gradient
    colorMap: ColorMap = field(
        default_factory=lambda: pg.ColorMap(None, color=[0.0, 1.0])
    )

    def __repr__(self):
        return f"RendererSettings (\n    mode={self.mode},\n    bands={self.bands},\n    stretch={self.stretch},\n    colorMap={self.colorMap}\n)"


class ImageRenderer(QObject):

    sigShouldRefresh: pyqtSignal = pyqtSignal()

    def __init__(self, image=None, settings: RendererSettings = None):
        super().__init__()
        self.image = image
        if settings is not None:
            self.settings = settings
        else:
            self.settings = RendererSettings()
        self.cachedRender = None

    def render(self):
        """
        Render the image with the current band and stretch settings.
        Returns: numpy ndarray with shape (height, width, 3) representing an RGB image.

        """
        if self.image is None or self.settings is None:
            raise ValueError("Image and settings must be set before rendering.")

        if self.cachedRender is not None:
            return self.cachedRender

        # Extract the raster data for the specified band
        if self.settings.mode == "mono":
            # maintain 3D shape so stretch algorithms don't need to account for both 2d and 3d arrays
            rgb_data = self.image.raster[:, :, self.settings.bands[0]][:, :, np.newaxis]
        else:
            rgb_data = self.image.raster[:, :, self.settings.bands[:3]]

        # Run the stretch algorithm
        rgb_data = self.settings.stretch.apply(rgb_data)

        # Apply color map
        if self.settings.mode == "mono":
            rgb_data = np.squeeze(rgb_data)  # go back to 2D because ColorMap expects it
            rgb_data = self.settings.colorMap.map(rgb_data)

        self.cachedRender = rgb_data
        return rgb_data

    def updateSettings(self, settings: RendererSettings):
        print(f"ImageRenderer: Received new settings. {settings}")
        self.settings = settings
        # delete cache so new image is generated
        self.cachedRender = None
        self.sigShouldRefresh.emit()


def getComboBox():
    comboBox = QComboBox()
    # None of these seem to work to stop it from expanding to the full width lol.
    # comboBox.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    # comboBox.setSizeAdjustPolicy(
    #     QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    # )
    return comboBox


class RendererSettingsPanel(QWidget):

    sigSettingsChanged: pyqtSignal = pyqtSignal(RendererSettings)

    def __init__(self, image, settings: RendererSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Render Settings")
        self.image = image
        self.settings = settings

        ### init UI ###
        layout = QFormLayout()
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        ## Mode selection ##
        modeSelector = QButtonGroup(self)
        modeSelector.addButton(rgbMode := QRadioButton("rgb"))
        modeSelector.addButton(monoMode := QRadioButton("mono"))
        modeLayout = QHBoxLayout()
        modeLayout.addWidget(rgbMode)
        modeLayout.addWidget(monoMode)
        layout.addRow("Mode", modeLayout)

        ## Band Selection ##
        self.rgbBands: list[QComboBox] = []
        self.bandLayout = QStackedLayout()
        rgbBandLayout = QHBoxLayout()
        # generate band layout for rgb mode
        for i in range(3):
            comboBox = getComboBox()
            comboBox.addItems([str(w) for w in self.image.metadata.wavelengths])
            comboBox.currentIndexChanged.connect(self._onBandsChanged)
            self.rgbBands.append(comboBox)
            rgbBandLayout.addWidget(comboBox)
        # generate band layout for mono mode
        monoBandLayout = QVBoxLayout()
        self.monoBand = getComboBox()
        self.monoBand.addItems([str(w) for w in self.image.metadata.wavelengths])
        self.monoBand.currentIndexChanged.connect(self._onBandsChanged)
        monoBandLayout.addWidget(self.monoBand)
        colormapSelector = pg.GradientWidget()
        colormapSelector.sigGradientChanged.connect(self._onColorMapChanged)
        monoBandLayout.addWidget(colormapSelector)

        # add to the stacked layout
        widgetContainer = QWidget()
        widgetContainer.setLayout(rgbBandLayout)
        self.bandLayout.addWidget(widgetContainer)
        widgetContainer = QWidget()
        widgetContainer.setLayout(monoBandLayout)
        self.bandLayout.addWidget(widgetContainer)

        layout.addRow("Band", self.bandLayout)

        ## Stretch Selection ##
        stretchLayout = QVBoxLayout()
        self.stretchAlgSelector = getComboBox()
        self.stretchAlgSelector.addItems([key for key in stretchAlgorithmRegistry.keys()])
        stretchLayout.addWidget(self.stretchAlgSelector)
        self.stretchParameters = QStackedLayout()

        self.stretchInstances = []  # list of StretchAlgorithm objects, one for each
        for alg in stretchAlgorithmRegistry.values():
            instance = alg()
            parameters = instance.parameters()
            # parameters are already associated with the stretch algorithm instance,
            # so we dont need to edit the settings object at all. Just indicate that a refresh is needed.
            parameters.sigParameterChanged.connect(
                lambda: self.sigSettingsChanged.emit(self.settings)
            )
            self.stretchParameters.addWidget(parameters)
            self.stretchInstances.append(instance)
        stretchLayout.addLayout(self.stretchParameters)
        layout.addRow("Stretch Algorithm", stretchLayout)

        ### Finish Init UI ###
        self.setLayout(layout)

        ### Connect Signals ###
        self.stretchAlgSelector.currentIndexChanged.connect(self._onStretchAlgChanged)
        modeSelector.buttonToggled.connect(self._onModeToggled)

        self.rgbBands[0].currentIndexChanged.connect(self._onBandsChanged)

        ### Set Defaults ###
        if self.settings.mode == "rgb":
            rgbMode.setChecked(True)
        elif self.settings.mode == "mono":
            monoMode.setChecked(True)
        colormapSelector.setColorMap(self.settings.colorMap)
        self.rgbBands[0].setCurrentIndex(self.settings.bands[0])
        self.rgbBands[1].setCurrentIndex(self.settings.bands[1])
        self.rgbBands[2].setCurrentIndex(self.settings.bands[2])
        self.monoBand.setCurrentIndex(self.settings.bands[0])
        # this is kinda hacky whoops
        self.stretchAlgSelector.setCurrentIndex(
            list(stretchAlgorithmRegistry.values()).index(self.settings.stretch.__class__)
        )

    def _onModeToggled(self, button, checked):
        # this gets triggered by both the radio button that was checked and the radio button that was unchecked.
        # so we skip the unchecked one.
        if not checked:
            return
        self.settings.mode = button.text()

        if self.settings.mode == "rgb":
            self.bandLayout.setCurrentIndex(0)
        elif self.settings.mode == "mono":
            self.bandLayout.setCurrentIndex(1)
        else:
            raise ValueError("Invalid mode selected.")

        self.sigSettingsChanged.emit(self.settings)

    def _onStretchAlgChanged(self, index):
        self.stretchParameters.setCurrentIndex(index)
        self.settings.stretch = self.stretchInstances[index]
        self.sigSettingsChanged.emit(self.settings)

    def _onBandsChanged(self, index: int):
        if self.settings.mode == "rgb":
            self.settings.bands[0] = self.rgbBands[0].currentIndex()
            self.settings.bands[1] = self.rgbBands[1].currentIndex()
            self.settings.bands[2] = self.rgbBands[2].currentIndex()
        elif self.settings.mode == "mono":
            self.settings.bands[0] = self.monoBand.currentIndex()
        else:
            raise ValueError("Invalid mode selected.")

        self.sigSettingsChanged.emit(self.settings)

    def _onColorMapChanged(self, colorMap: pg.GradientEditorItem):
        self.settings.colorMap = colorMap.colorMap()
        self.sigSettingsChanged.emit(self.settings)


if __name__ == "__main__":
    q_app = pg.mkQApp()
    image = varda.utilities.debug.generateRandomImage((100, 100, 10), (10, 10, 10))
    settings = RendererSettings()
    renderer = ImageRenderer(image, settings)
    settingsPanel = RendererSettingsPanel(image, settings)
    settingsPanel.sigSettingsChanged.connect(renderer.updateSettings)
    settingsPanel.show()
    q_app.exec()
