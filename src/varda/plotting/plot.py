import json
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QPoint, QByteArray, QMimeData
from PyQt6.QtGui import QDrag, QColor
from PyQt6.QtWidgets import QWidget, QComboBox, QScrollArea
import pyqtgraph as pg

from varda.common.entities import VardaRaster

from varda.common.ui import (
    VBoxBuilder,
    HBoxBuilder,
    SectionBox,
    ButtonBuilder,
    WrapperWidget,
    VerticalScrollArea,
)
from varda.common.vec2 import Vec2
from varda.plotting.library_spectra import (
    DEFAULT_LIBRARY_PATH,
    listSpectra,
    loadSpectrum,
)
from varda.common.parameter import (
    ParameterGroup,
    FloatParameter,
    Vec2Parameter,
    ColorParameter,
    BoolParameter,
)

CURVE_MIME_TYPE = "application/x-varda-curve"


class CurveConfig(ParameterGroup):
    width = FloatParameter(
        "Curve Width",
        default=2.0,
        range=(0.1, 10.0),
        units="px",
        description="Width of the curve in pixels",
    )
    color = ColorParameter(
        "Curve Color",
        default="#ff0000",
        description="Color of the curve",
    )
    offset = FloatParameter(
        "Y Offset",
        default=0.0,
        units="y",
        description="Vertical offset of the curve",
    )
    scale = FloatParameter(
        "Y Scale",
        default=1.0,
        units="y",
        description="Vertical scale of the curve",
    )


class Curve(QObject):
    sigClicked = pyqtSignal(object)  # emits self when clicked

    def __init__(
        self,
        plotDataItem: pg.PlotDataItem,
        config: CurveConfig,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.plotDataItem = plotDataItem
        self.plotDataItem.sigClicked.connect(lambda: self.sigClicked.emit(self))
        self.config = config

        self.config.sigParameterChanged.connect(self.onConfigChanged)

        self.onConfigChanged()

    def onConfigChanged(self):
        pen = pg.mkPen(color=self.config.color.value, width=self.config.width.value)
        self.plotDataItem.setPen(pen)
        self.plotDataItem.setTransform(
            pg.QtGui.QTransform()
            .scale(1.0, self.config.scale.value)
            .translate(0.0, self.config.offset.value)
        )

    def setClickable(self, clickable: bool):
        self.plotDataItem.setCurveClickable(clickable, width=20)

    def setHighlighted(self, highlighted: bool):
        if highlighted:
            self.plotDataItem.setShadowPen(pg.mkPen("#ffff0088", width=10))
        else:
            self.plotDataItem.setShadowPen(None)

    def serialize(self) -> dict:
        x, y = self.plotDataItem.getData()
        return {
            "x": x.tolist() if x is not None else [],
            "y": y.tolist() if y is not None else [],
            "name": self.plotDataItem.name() or "",
            "color": self.config.color.value.name(),
            "width": self.config.width.value,
            "offset": self.config.offset.value,
            "scale": self.config.scale.value,
        }

    @classmethod
    def deserialize(cls, data: dict) -> "Curve":
        curve = cls.fromData(data["x"], data["y"], name=data["name"] or None)
        curve.config.color.set(QColor(data["color"]))
        curve.config.width.set(data["width"])
        curve.config.offset.set(data["offset"])
        curve.config.scale.set(data["scale"])
        return curve

    @classmethod
    def fromData(cls, x, y, **kwargs):
        plotItem = pg.PlotDataItem(x, y, **kwargs)
        defaultConfig = CurveConfig()
        return cls(plotItem, defaultConfig)


class WindowConfig(ParameterGroup):
    backgroundColor = ColorParameter("Background Color", "#000000")
    autoViewRange = BoolParameter(
        "Auto Range",
        True,
        "Should view range be manually set or automatically adjust?",
    )


class RangeConfig(ParameterGroup):
    viewRangeX = Vec2Parameter(
        "X View Range", default=Vec2(0.0, 1.0), valueNames=("Min", "Max")
    )
    viewRangeY = Vec2Parameter(
        "Y View Range", default=Vec2(0.0, 1.0), valueNames=("Min", "Max")
    )


class _PlotGraphicsView(pg.GraphicsView):
    def __init__(self, parent: "VardaPlotWidget"):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._dragStartPos: QPoint | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            parent = self.parent()
            if isinstance(parent, VardaPlotWidget) and parent.selectedCurve is not None:
                self._dragStartPos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            self._dragStartPos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.pos() - self._dragStartPos).manhattanLength() >= 10
        ):
            self._dragStartPos = None
            parent = self.parent()
            if isinstance(parent, VardaPlotWidget) and parent.selectedCurve is not None:
                self._initiateDrag(parent.selectedCurve)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._dragStartPos = None
        super().mouseReleaseEvent(event)

    def _initiateDrag(self, curve: Curve) -> None:
        data = curve.serialize()
        data["source_id"] = id(self.parent())
        mimeData = QMimeData()
        mimeData.setData(CURVE_MIME_TYPE, QByteArray(json.dumps(data).encode("utf-8")))
        drag = QDrag(self)
        drag.setMimeData(mimeData)
        drag.exec(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(CURVE_MIME_TYPE):
            event.accept()
        # Do NOT call super() — pg.GraphicsView.dragEnterEvent calls ev.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(CURVE_MIME_TYPE):
            event.accept()

    def dropEvent(self, event) -> None:
        if event.mimeData().hasFormat(CURVE_MIME_TYPE):
            parent = self.parent()
            if isinstance(parent, VardaPlotWidget):
                parent.onCurveDrop(event)


class VardaPlotWidget(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        libraryPath: Path = DEFAULT_LIBRARY_PATH,
    ):
        super().__init__(parent)
        self.selectedCurve: Curve | None = None
        self.libraryPath = libraryPath

        self.plots: list[Curve] = []
        self._fillItems: list[pg.GraphicsObject] = []
        self.gv = _PlotGraphicsView(self)
        # if the user clicks on the plot area and none of the plots catch the click (therefore selecting it), deselect any selected plot
        self.gv.scene().sigMouseClicked.connect(self.onSceneClicked)
        self.plotItem = pg.PlotItem()
        self.plotItem.addLegend()
        self.plotItem.setMouseEnabled(x=False, y=False)
        self.gv.setCentralItem(self.plotItem)

        self.windowConfig = WindowConfig()
        self.windowConfig.sigParameterChanged.connect(self.onWindowParamsChanged)

        self.rangeConfig = RangeConfig()
        self.rangeConfig.sigParameterChanged.connect(self.onRangeParamsChanged)

        self.curveSettingsBox = SectionBox("Curve Settings")

        self.windowConfigWidget = self.windowConfig.createWidget()
        self.rangeConfigWidget = self.rangeConfig.createWidget()
        self.rangeConfigWidget.hide()

        sidebar = VBoxBuilder(Qt.AlignmentFlag.AlignTop).withWidget(
            self.curveSettingsBox
        )

        spectraNames = listSpectra(libraryPath) if libraryPath else []
        if spectraNames:
            self.libraryCombo = QComboBox()
            self.libraryCombo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            self.libraryCombo.addItems(spectraNames)
            sidebar.withWidget(
                SectionBox(
                    "Library Spectra",
                    VBoxBuilder()
                    .withWidget(self.libraryCombo)
                    .withWidget(
                        ButtonBuilder("Add to Plot").onClick(self._addLibrarySpectrum)
                    ),
                )
            )

        sidebar.withWidget(
            SectionBox(
                "Window Settings",
                VBoxBuilder()
                .withWidget(self.windowConfigWidget)
                .withWidget(self.rangeConfigWidget),
            )
        )

        self.setLayout(
            HBoxBuilder()
            .withWidget(self.gv, stretch=2)
            .withWidget(VerticalScrollArea(sidebar))
        )

    def onWindowParamsChanged(self):
        self.gv.setBackground(self.windowConfig.backgroundColor.value)

        if self.windowConfig.autoViewRange.value:
            self.plotItem.enableAutoRange()
            self.rangeConfigWidget.hide()
        else:
            self.plotItem.disableAutoRange()
            self.rangeConfigWidget.show()
            self.onRangeParamsChanged()

    def onRangeParamsChanged(self):
        if not self.windowConfig.autoViewRange.value:
            xRange = self.rangeConfig.viewRangeX.value
            yRange = self.rangeConfig.viewRangeY.value
            self.plotItem.setXRange(xRange.x, xRange.y)
            self.plotItem.setYRange(yRange.x, yRange.y)

    def plot(self, x, y, **kwargs) -> Curve:
        """
        TODO: Maybe give each new plot a different starting color?

        :param self: Description
        :param x: Description
        :param y: Description
        :param kwargs: Description
        """
        curve = Curve.fromData(x, y, **kwargs)
        curve.setClickable(True)
        curve.sigClicked.connect(self.selectPlot)
        self.plots.append(curve)
        self.plotItem.addItem(curve.plotDataItem)
        return curve

    def selectPlot(self, curve: Curve) -> None:
        self.deselectPlot()
        self.selectedCurve = curve
        curve.setHighlighted(True)
        self.curveSettingsBox.setContent(
            WrapperWidget(
                VBoxBuilder(Qt.AlignmentFlag.AlignTop)
                .withWidget(curve.config.createWidget())
                .withWidget(
                    ButtonBuilder("Remove Curve").onClick(
                        lambda: self.removePlot(curve)
                    )
                )
            )
        )

    def onSceneClicked(self, event):
        if event.isAccepted():
            return
        self.deselectPlot()

    def deselectPlot(self):
        if self.selectedCurve is not None:
            self.selectedCurve.setHighlighted(False)
            self.curveSettingsBox.setContent(None)
        self.selectedCurve = None

    def _addLibrarySpectrum(self) -> None:
        folderName = self.libraryCombo.currentText()
        name, wavelengths, reflectance = loadSpectrum(self.libraryPath, folderName)
        self.plot(wavelengths, reflectance, name=name)

    def removePlot(self, curve: Curve) -> None:
        if curve not in self.plots:
            return
        self.plots.remove(curve)
        self.plotItem.removeItem(curve.plotDataItem)
        if self.selectedCurve is curve:
            self.deselectPlot()

    def onCurveDrop(self, event) -> None:
        data = json.loads(bytes(event.mimeData().data(CURVE_MIME_TYPE)).decode("utf-8"))
        if data.get("source_id") == id(self):
            event.ignore()
            return
        curve = Curve.deserialize(data)
        curve.setClickable(True)
        curve.sigClicked.connect(self.selectPlot)
        self.plots.append(curve)
        self.plotItem.addItem(curve.plotDataItem)
        event.accept()

    def plotWithFill(self, x, y, yLower, yUpper, fillBrush, **kwargs):
        """Plot a curve with a filled region between yLower and yUpper.

        Useful for displaying mean +/- standard deviation.
        """
        self.plot(x, y, **kwargs)

        upperCurve = pg.PlotDataItem(x, yUpper, pen=pg.mkPen(None))
        lowerCurve = pg.PlotDataItem(x, yLower, pen=pg.mkPen(None))
        fill = pg.FillBetweenItem(lowerCurve, upperCurve, brush=fillBrush)

        self.plotItem.addItem(upperCurve)
        self.plotItem.addItem(lowerCurve)
        self.plotItem.addItem(fill)
        self._fillItems.extend([upperCurve, lowerCurve, fill])

    @staticmethod
    def getPlottableWavelengths(image: VardaRaster, bandCount: int) -> np.ndarray:
        """Return a numeric x-axis array suitable for plotting spectral data.

        Uses the image's wavelengths if they are numeric, otherwise falls
        back to band indices.
        """
        if image.wavelengthsType in (int, float):
            return np.asarray(image.wavelengths, dtype=float)
        return np.arange(bandCount, dtype=float)

    def clearPlots(self):
        for plot in self.plots:
            self.plotItem.removeItem(plot.plotDataItem)
        self.plots.clear()
        for item in self._fillItems:
            self.plotItem.removeItem(item)
        self._fillItems.clear()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import numpy as np

    app = QApplication([])

    w = VardaPlotWidget()
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    w.plot(x, y, pen=pg.mkPen(color="g", width=2), name="Sine Wave", antialias=True)

    x2 = np.linspace(0, 10, 100)
    y2 = np.cos(x2)
    w.plot(x2, y2, pen=pg.mkPen(color="r", width=2), name="Cosine Wave", antialias=True)
    w.show()

    app.exec()
