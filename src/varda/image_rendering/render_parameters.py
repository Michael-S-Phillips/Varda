from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QSignalBlocker, pyqtSlot
from PyQt6.QtWidgets import (
    QComboBox,
    QMessageBox,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from varda.common.entities import VardaRaster
from varda.common.parameter import Parameter, paramLayoutDefault
from varda.common.vec2 import Vec2
from varda.image_rendering.stretch_algorithms import (
    StretchAlgorithm,
    stretchAlgorithmRegistry,
)


class BandParameter(Parameter[int]):
    """Selects a band by index. The widget lists the image's wavelengths.

    Image-aware: ``setImage()`` must be called before building the widget (mirrors
    ``ImageParameter.setProvider``).
    """

    def __init__(
        self,
        name: str,
        default: int = 0,
        description: str | None = None,
        parent=None,
    ):
        super().__init__(name, default, description, parent)
        self.image: VardaRaster | None = None

    def setImage(self, image: VardaRaster) -> None:
        self.image = image
        if self.value >= image.bandCount:
            self.value = 0

    def getWidget(self, parent=None) -> QWidget:
        return self.BandParameterWidget(self, parent)

    def clone(self, parent=None) -> BandParameter:
        new = BandParameter(self.name, self.default, self.description, parent)
        if self.image is not None:
            new.setImage(self.image)
        new.value = self.value
        return new

    class BandParameterWidget(QWidget):
        def __init__(self, param: BandParameter, parent=None):
            super().__init__(parent)
            self.param = param
            self.param.sigParameterChanged.connect(self.onParamChanged)
            assert self.param.image is not None, (
                "BandParameter.setImage() must be called before building its widget"
            )
            self.comboBox = QComboBox(self)
            self.comboBox.addItems([str(w) for w in self.param.image.wavelengths])
            self.comboBox.setCurrentIndex(self.param.get())
            self.comboBox.currentIndexChanged.connect(self._onSelectionChanged)

            layout = paramLayoutDefault()
            layout.addWidget(self.comboBox)
            self.setLayout(layout)

        def _onSelectionChanged(self, index: int) -> None:
            self.param.set(index)

        @pyqtSlot(object)
        def onParamChanged(self, value: int) -> None:
            if self.comboBox.currentIndex() != value:
                with QSignalBlocker(self.comboBox):
                    self.comboBox.setCurrentIndex(value)
