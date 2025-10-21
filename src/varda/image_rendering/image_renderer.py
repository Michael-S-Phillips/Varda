from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QFormLayout,
    QComboBox,
    QButtonGroup,
    QRadioButton,
    QHBoxLayout,
    QStackedLayout,
    QVBoxLayout,
    QSizePolicy,
)
import pyqtgraph as pg

import varda
from varda.common.entities import Image
from varda.image_loading import ImageLoadingService
from varda.image_rendering.stretch_management_and_histogram.stretch_algorithms import (
    stretchAlgorithmRegistry,
)


class ImageRenderer:
    def __init__(
        self,
        image=None,
        mode="rgb",
        band=None,
        stretch=None,
    ):
        self.image = image
        self.mode = "rgb"
        self.band = band
        self.stretch = stretch

    def render(self):
        """
        Render the image with the current band and stretch settings.
        Returns: numpy ndarray with shape (height, width, 3) representing an RGB image.

        """
        if self.image is None or self.band is None or self.stretch is None:
            raise ValueError("Image, band, and stretch must be set before rendering.")

        # Extract the raster data for the specified band
        rgb_data = self.band.apply(self.image)

        # TODO: handle nans/nodata values

        # Apply the stretch to the raster data
        rgb_data = self.stretch.apply(rgb_data)

        # TODO: handle color mapping

        return rgb_data


def getComboBox():
    comboBox = QComboBox()
    # None of these seem to work to stop it from expanding to the full width lol.
    # comboBox.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    # comboBox.setSizeAdjustPolicy(
    #     QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    # )
    return comboBox


class RendererSettings(QWidget):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Render Settings")
        self.mode = "rgb"
        self.image = image

        ### init UI ###
        layout = QFormLayout()
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        ## Mode selection ##
        modeSelector = QButtonGroup(self)
        modeSelector.addButton(rgbMode := QRadioButton("rgb"))
        modeSelector.addButton(monoMode := QRadioButton("mono"))
        rgbMode.setChecked(True)
        modeLayout = QHBoxLayout()
        modeLayout.addWidget(rgbMode)
        modeLayout.addWidget(monoMode)
        layout.addRow("Mode", modeLayout)

        ## Band Selection ##
        self.bands = []
        self.bandLayout = QStackedLayout()
        rgbBandLayout = QHBoxLayout()
        # generate band layout for rgb mode
        for i in range(3):
            comboBox = getComboBox()
            comboBox.addItems([str(w) for w in self.image.metadata.wavelengths])
            self.bands.append(comboBox)
            rgbBandLayout.addWidget(comboBox)
        # generate band layout for mono mode
        monoBandLayout = QVBoxLayout()
        comboBox = getComboBox()
        comboBox.addItems([str(w) for w in self.image.metadata.wavelengths])
        monoBandLayout.addWidget(comboBox)
        colormapSelector = pg.GradientWidget()
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
        self.stretchAlgSelector.addItems([alg.name for alg in stretchAlgorithmRegistry])
        stretchLayout.addWidget(self.stretchAlgSelector)
        layout.addRow("Stretch Algorithm", self.stretchAlgSelector)
        self.stretchParameters = QStackedLayout()
        self.stretchInstances = []
        for alg in stretchAlgorithmRegistry:
            instance = alg()
            self.stretchParameters.addWidget(instance.parameters())
            self.stretchInstances.append(instance)
        stretchLayout.addLayout(self.stretchParameters)
        layout.addRow("Stretch", stretchLayout)

        ### Finish Init UI ###
        self.setLayout(layout)

        ### Connect Signals ###
        self.stretchAlgSelector.currentIndexChanged.connect(self._onStretchAlgChanged)
        modeSelector.buttonToggled.connect(self._onModeToggled)

    def _onModeToggled(self, button, checked):
        # this gets triggered by both the radio button that was checked and the radio button that was unchecked.
        # so we skip the unchecked one.
        if not checked:
            return
        self.mode = button.text()

        if self.mode == "rgb":
            self.bandLayout.setCurrentIndex(0)
        elif self.mode == "mono":
            self.bandLayout.setCurrentIndex(1)
        else:
            raise ValueError("Invalid mode selected.")

    def _onStretchAlgChanged(self, index):
        self.stretchParameters.setCurrentIndex(index)


if __name__ == "__main__":
    q_app = pg.mkQApp()

    imageLoader = ImageLoadingService()
    raster, metadata = imageLoader.loadImageSync()
    image = Image(raster=raster, metadata=metadata)
    settingsPanel = RendererSettings(image)
    settingsPanel.show()
    q_app.exec()
