import sys
from dataclasses import dataclass, field
import logging
from typing import Optional

from PyQt6.QtCore import pyqtSlot, pyqtSignal, QObject, Qt
from PyQt6.QtWidgets import (
    QWidget,
    QFormLayout,
    QComboBox,
    QButtonGroup,
    QRadioButton,
    QHBoxLayout,
    QStackedLayout,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QApplication,
    QLayout,
    QSizePolicy,
)
import pyqtgraph as pg
from pyqtgraph import ColorMap
import numpy as np

import varda.utilities.debug
from varda.image_rendering.stretch_management_and_histogram.stretch_algorithms import (
    stretchAlgorithmRegistry,
    StretchAlgorithm,
)


@dataclass
class RendererSettings:
    mode: str
    bands: np.ndarray[tuple[int], np.dtype[np.uint]]
    stretch: StretchAlgorithm
    # default to a simple black-to-white gradient
    colorMap: ColorMap

    @staticmethod
    def new(image):
        return RendererSettings(
            mode="mono",
            bands=image.metadata.defaultBand,
            stretch=stretchAlgorithmRegistry["Min-Max (Full Range)"](),
            colorMap=pg.ColorMap(None, color=[0.0, 1.0]),
        )

    def __repr__(self):
        return f"RendererSettings (\n    mode={self.mode},\n    bands={self.bands},\n    stretch={self.stretch},\n    colorMap={self.colorMap}\n)"


class ImageRenderer(QObject):

    sigShouldRefresh: pyqtSignal = pyqtSignal()

    def __init__(self, image=None, settings: Optional[RendererSettings] = None):
        super().__init__()
        self.image = image
        self.settings = settings if settings is not None else RendererSettings.new(image)

        self.cachedRender = None
        self._stretchedData = (
            None  # the data from the latest render post-stretch but pre-colormap.
        )
        self._rawBandData = None  # extracted data bands with no processing applied.

    def render(self):
        """
        Render the image with the current band and stretch settings.
        Returns: numpy ndarray with shape (height, width, 3) representing an RGB image.

        """
        if self.cachedRender is not None:
            return self.cachedRender

        if self.image is None or self.settings is None:
            raise ValueError("Image and settings must be set before rendering.")

        # Extract the raster data for the specified band
        if self.settings.mode == "mono":
            # maintain 3D shape so stretch algorithms don't need to account for both 2d and 3d arrays
            rgbData = self.image.raster[:, :, self.settings.bands[0]][:, :, np.newaxis]
        else:
            rgbData = self.image.raster[:, :, self.settings.bands[:3]]
        self._rawBandData = rgbData

        # if array is masked, convert to regular array with nans
        if np.ma.isMaskedArray(rgbData):
            rgbData = rgbData.filled(np.nan)

        # Run the stretch algorithm
        rgbData = self.settings.stretch.apply(rgbData)

        # save the stretched data pre-colormap; expand mono image to RGB image
        self._stretchedData = rgbData

        # convert NaNs to zeros before color mapping and outputting
        rgbData[np.isnan(rgbData)] = 0

        # Apply color map
        if self.settings.mode == "mono":
            rgbData = np.squeeze(rgbData)  # go back to 2D because ColorMap expects it
            rgbData = self.settings.colorMap.mapToByte(rgbData)
        else:
            # convert the image to byte values, since it's faster to display I think.
            # (ColorMap already does this for mono images)
            rgbData = (rgbData * 255).astype(np.uint8)
        self.cachedRender = rgbData
        return rgbData

    def getStretchedData(self):
        if self._stretchedData is None:
            self.render()
        return self._stretchedData

    def getRawBandData(self):
        # Extract the raster data for the specified band
        if self._rawBandData is None:
            self.render()
        return self._rawBandData

    def getMinMaxValues(self):
        if self.cachedRender is None:
            self.render()
        return self.settings.stretch.minMaxVals()

    def isLinearStretch(self):
        return isinstance(
            self.settings.stretch,
            stretchAlgorithmRegistry["Linear Percentile"]
            | stretchAlgorithmRegistry["Min-Max (Full Range)"],
        )

    def updateSettings(self, settings: RendererSettings):
        print(f"ImageRenderer: Received new settings. {settings}")
        self.settings = settings
        # delete cache so new image is generated
        self.cachedRender = None
        self._stretchedData = None
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
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.setSpacing(2)

        ## Mode selection ##
        modeSelector = QButtonGroup(self)
        modeSelector.addButton(rgbMode := QRadioButton("rgb"))
        modeSelector.addButton(monoMode := QRadioButton("mono"))
        modeLayout = QHBoxLayout()
        modeLayout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        modeLayout.addWidget(rgbMode)
        modeLayout.addWidget(monoMode)
        layout.addWidget(QLabel("Mode:"))
        layout.addLayout(modeLayout)

        ## Band Selection ##
        self.rgbBands: list[QComboBox] = []
        self.bandLayout = QStackedLayout()
        self.bandLayout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        rgbBandLayout = QHBoxLayout()
        rgbBandLayout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # generate band layout for rgb mode
        for i in range(3):
            comboBox = getComboBox()
            comboBox.addItems([str(w) for w in self.image.metadata.wavelengths])
            comboBox.setMaximumWidth(100)
            comboBox.currentIndexChanged.connect(self._onBandsChanged)
            self.rgbBands.append(comboBox)
            rgbBandLayout.addWidget(comboBox)
        # generate band layout for mono mode
        monoBandLayout = QVBoxLayout()
        monoBandLayout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
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

        layout.addLayout(self.bandLayout)

        ## Stretch Selection ##
        stretchLayout = QVBoxLayout()
        stretchLayout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.stretchAlgSelector = getComboBox()
        self.stretchAlgSelector.addItems([key for key in stretchAlgorithmRegistry.keys()])
        stretchLayout.addWidget(self.stretchAlgSelector)
        self.stretchParameters = QStackedLayout()
        # self.stretchParameters.setSizeConstraint(
        #     QStackedLayout.SizeConstraint.SetMinimumSize
        # )
        self.stretchParameters.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        # self.stretchParameters.setContentsMargins(0, 0, 0, 0)
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

        layout.addWidget(QLabel("Stretch Algorithm:"))
        layout.addLayout(stretchLayout)

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
    q_app = QApplication(sys.argv)
    image = varda.utilities.debug.generate_random_image((100, 100, 10), (10, 10, 10))
    settings = RendererSettings.new(image)
    renderer = ImageRenderer(image, settings)
    settingsPanel = RendererSettingsPanel(image, settings)
    settingsPanel.sigSettingsChanged.connect(renderer.updateSettings)
    settingsPanel.show()
    q_app.exec()
