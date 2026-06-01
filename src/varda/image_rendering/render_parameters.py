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
from varda.common.parameter import Parameter, ParameterGroup, paramLayoutDefault
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


class ColorMapParameter(Parameter[pg.ColorMap]):
    """A pyqtgraph ColorMap, edited via a gradient widget."""

    def __init__(
        self,
        name: str,
        default: pg.ColorMap | None = None,
        description: str | None = None,
        parent=None,
    ):
        if default is None:
            default = pg.ColorMap(None, color=[0.0, 1.0])  # simple black -> white map
        super().__init__(name, default, description, parent)

    def getWidget(self, parent=None) -> QWidget:
        return self.ColorMapParameterWidget(self, parent)

    def clone(self, parent=None) -> ColorMapParameter:
        return ColorMapParameter(self.name, self.default, self.description, parent)

    class ColorMapParameterWidget(QWidget):
        def __init__(self, param: ColorMapParameter, parent=None):
            super().__init__(parent)
            self.param = param
            self.param.sigParameterChanged.connect(self.onParamChanged)

            self.gradient = pg.GradientWidget()
            self.gradient.setColorMap(self.param.get())
            self.gradient.sigGradientChanged.connect(self._onGradientChanged)

            layout = paramLayoutDefault()
            layout.addWidget(self.gradient)
            self.setLayout(layout)

        def _onGradientChanged(self, item) -> None:
            try:
                colorMap = item.colorMap()  # raises NotImplementedError for HSV maps
            except NotImplementedError:
                QMessageBox.warning(
                    self,
                    "Unsupported Color Map",
                    "HSV color maps are not supported yet.",
                )
                with QSignalBlocker(self.gradient):
                    self.gradient.setColorMap(self.param.get())  # revert
                return
            self.param.set(colorMap)

        @pyqtSlot(object)
        def onParamChanged(self, colorMap: pg.ColorMap) -> None:
            with QSignalBlocker(self.gradient):
                self.gradient.setColorMap(colorMap)


class StretchParameter(Parameter[StretchAlgorithm]):
    """Selects the active stretch algorithm from the registry.

    The value is the active ``StretchAlgorithm`` instance. One instance of every
    registered algorithm is built up-front and kept, so each option retains its own
    sub-parameters. The widget is a self-contained combo + stacked sub-form.
    """

    DEFAULT_NAME = "Min-Max (Auto Full Range)"
    MANUAL_NAME = "Min-Max (Manual)"  # used by ImageRenderer's manual-stretch convenience methods

    def __init__(self, name: str, description: str | None = None, parent=None):
        self._instances: dict[str, StretchAlgorithm] = {
            n: cls() for n, cls in stretchAlgorithmRegistry.items()
        }
        default = self._instances.get(self.DEFAULT_NAME) or next(
            iter(self._instances.values())
        )
        super().__init__(name, default, description, parent)
        # Keep ParameterGroup references alive so Qt signal connections are not dangling.
        # Algorithms whose parameters() returns a fresh group each call need their group
        # kept alive here; algorithms that return self.config are also fine.
        self._paramGroups: dict[str, ParameterGroup] = {}
        for alg_name, instance in self._instances.items():
            group = instance.parameters()
            self._paramGroups[alg_name] = group
            group.sigParameterChanged.connect(self._onSubParamChanged)

    def _onSubParamChanged(self, *args) -> None:
        # A sub-parameter of one of the algorithms changed. All algorithms' groups stay
        # connected (to keep them alive and avoid dangling-connection crashes), so only
        # propagate when the group that changed belongs to the *active* algorithm.
        if self.sender() is self._paramGroups[self.nameOf(self.value)]:
            self.sigParameterChanged.emit(self.value)

    @property
    def current(self) -> StretchAlgorithm:
        return self.value

    @property
    def optionNames(self) -> list[str]:
        return list(self._instances.keys())

    def option(self, name: str) -> StretchAlgorithm:
        return self._instances[name]

    def nameOf(self, instance: StretchAlgorithm) -> str:
        for n, inst in self._instances.items():
            if inst is instance:
                return n
        raise ValueError("instance is not one of this parameter's algorithms")

    def selectByName(self, name: str) -> None:
        self.set(self._instances[name])

    def getWidget(self, parent=None) -> QWidget:
        return self.StretchParameterWidget(self, parent)

    def clone(self, parent=None) -> StretchParameter:
        new = StretchParameter(self.name, self.description, parent)
        new.selectByName(self.nameOf(self.value))
        return new

    class StretchParameterWidget(QWidget):
        def __init__(self, param: StretchParameter, parent=None):
            super().__init__(parent)
            self.param = param
            self.param.sigParameterChanged.connect(self.onParamChanged)

            self.comboBox = QComboBox(self)
            self.comboBox.addItems(self.param.optionNames)

            self.stack = QStackedLayout()
            self.stack.setAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
            )
            for name in self.param.optionNames:
                self.stack.addWidget(self.param._paramGroups[name].createWidget())

            self.comboBox.currentIndexChanged.connect(self._onComboChanged)

            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(self.comboBox)
            layout.addLayout(self.stack)
            self.setLayout(layout)

            self._syncToParam()

        def _onComboChanged(self, index: int) -> None:
            self.param.selectByName(self.param.optionNames[index])

        def _syncToParam(self) -> None:
            index = self.param.optionNames.index(self.param.nameOf(self.param.current))
            with QSignalBlocker(self.comboBox):
                self.comboBox.setCurrentIndex(index)
            self.stack.setCurrentIndex(index)

        @pyqtSlot(object)
        def onParamChanged(self, value) -> None:
            self._syncToParam()
