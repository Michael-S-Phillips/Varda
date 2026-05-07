import json
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QPoint, QByteArray, QMimeData, QSize
from PyQt6.QtGui import QDrag, QColor
from PyQt6.QtWidgets import QWidget, QComboBox, QScrollArea
import pyqtgraph as pg

from varda.common.entities import VardaRaster, Color

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
        curve = cls.fromData(
            data["x"], data["y"], QColor(data["color"]), name=data["name"] or None
        )
        curve.config.color.set(QColor(data["color"]))
        curve.config.width.set(data["width"])
        curve.config.offset.set(data["offset"])
        curve.config.scale.set(data["scale"])
        return curve

    @classmethod
    def fromData(cls, x, y, color: QColor, **kwargs):
        plotItem = pg.PlotDataItem(x, y, **kwargs)
        defaultConfig = CurveConfig()
        curve = cls(plotItem, defaultConfig)

        # initialize parameters
        curve.config.color.set(color)

        return curve


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
        viewBox = self.plotItem.getViewBox()
        assert viewBox is not None
        self.viewBox: pg.ViewBox = viewBox
        # Left-drag draws a rubber-band rectangle and zooms in on release;
        # right-drag pans, wheel zooms.
        self.viewBox.setMouseMode(pg.ViewBox.RectMode)
        self.viewBox.setMouseEnabled(x=True, y=True)
        self.gv.setCentralItem(self.plotItem)

        # Whether manual range params have been seeded with a starting value.
        # Auto-range stays auto until the user opts into manual; the first
        # opt-in seeds the manual params from the current view, subsequent
        # toggles preserve whatever the user last set.
        self._manualRangeInitialized = False

        self.windowConfig = WindowConfig()
        self.windowConfig.sigParameterChanged.connect(self.onWindowParamsChanged)

        self.rangeConfig = RangeConfig()
        self.rangeConfig.sigParameterChanged.connect(self.onRangeParamsChanged)

        # sigRangeChangedManually fires only on user interaction (rubber-band
        # zoom, pan, wheel), not on programmatic setRange calls.
        self.viewBox.sigRangeChangedManually.connect(self._onUserViewChange)

        self.curveSettingsBox = SectionBox("Curve Settings")

        self.windowConfigWidget = self.windowConfig.createWidget()
        self.rangeConfigWidget = self.rangeConfig.createWidget()

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

    def sizeHint(self) -> QSize:
        # Sensible window size so plot isn't squashed by default.
        # Layout stretch factors only distribute space *beyond*
        # sizeHint, so without this the widget opens at the sum of children's
        # natural sizes (sidebar wide, plot tiny) and stretch never kicks in.
        return QSize(1200, 600)

    def onWindowParamsChanged(self):
        self.gv.setBackground(self.windowConfig.backgroundColor.value)

        if self.windowConfig.autoViewRange.value:
            self.plotItem.enableAutoRange()
        else:
            self.plotItem.disableAutoRange()
            if not self._manualRangeInitialized:
                self._seedManualRangeFromView()
            self.onRangeParamsChanged()

    def onRangeParamsChanged(self):
        if not self.windowConfig.autoViewRange.value:
            xRange = self.rangeConfig.viewRangeX.value
            yRange = self.rangeConfig.viewRangeY.value
            self.plotItem.setXRange(xRange.x, xRange.y, padding=0)
            self.plotItem.setYRange(yRange.x, yRange.y, padding=0)

    def _seedManualRangeFromView(self) -> None:
        xRange, yRange = self.viewBox.viewRange()
        self.rangeConfig.viewRangeX.set(Vec2(float(xRange[0]), float(xRange[1])))
        self.rangeConfig.viewRangeY.set(Vec2(float(yRange[0]), float(yRange[1])))
        self._manualRangeInitialized = True

    def _onUserViewChange(self) -> None:
        # User did a rubber-band zoom, pan, or wheel zoom. Sync our manual
        # range params to the new view and switch out of auto mode so the UI
        # reflects what the user just did.
        self._seedManualRangeFromView()
        if self.windowConfig.autoViewRange.value:
            self.windowConfig.autoViewRange.set(False)

    def _updateViewLimits(self) -> None:
        # Constrain panning and zooming so the view never extends past the
        # bounds of the plotted data.
        if not self.plots:
            self.viewBox.setLimits(
                xMin=None,
                xMax=None,
                yMin=None,
                yMax=None,
                maxXRange=None,
                maxYRange=None,
            )
            return
        xMin, xMax = float("inf"), float("-inf")
        yMin, yMax = float("inf"), float("-inf")
        for curve in self.plots:
            x, y = curve.plotDataItem.getData()
            if x is None or y is None or len(x) == 0:
                continue
            yScaled = (
                np.asarray(y) * curve.config.scale.value + curve.config.offset.value
            )
            xMin = min(xMin, float(np.min(x)))
            xMax = max(xMax, float(np.max(x)))
            yMin = min(yMin, float(np.min(yScaled)))
            yMax = max(yMax, float(np.max(yScaled)))
        if not np.isfinite(xMin) or xMax <= xMin or yMax <= yMin:
            return

        # apply padding
        xRange = xMax - xMin
        yRange = yMax - yMin
        xMin = xMin - (xRange * 0.05)
        xMax = xMax + (xRange * 0.05)
        yMin = yMin - (yRange * 0.05)
        yMax = yMax + (yRange * 0.05)

        self.viewBox.setLimits(
            xMin=xMin,
            xMax=xMax,
            yMin=yMin,
            yMax=yMax,
            maxXRange=xMax - xMin,
            maxYRange=yMax - yMin,
        )

    def plot(self, x, y, color: Color = Color(1.0, 0.0, 0.0, 0.5), **kwargs) -> Curve:
        """
        TODO: Maybe give each new plot a different starting color?

        :param self: Description
        :param x: Description
        :param y: Description
        :param kwargs: Description
        """
        curve = Curve.fromData(x, y, color.toQColor(), **kwargs)
        curve.setClickable(True)
        curve.sigClicked.connect(self.selectPlot)
        # offset/scale changes shift visible y-bounds, so refresh limits.
        curve.config.sigParameterChanged.connect(self._updateViewLimits)
        self.plots.append(curve)
        self.plotItem.addItem(curve.plotDataItem)
        self._updateViewLimits()
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
        self._updateViewLimits()

    def onCurveDrop(self, event) -> None:
        data = json.loads(bytes(event.mimeData().data(CURVE_MIME_TYPE)).decode("utf-8"))
        if data.get("source_id") == id(self):
            event.ignore()
            return
        curve = Curve.deserialize(data)
        curve.setClickable(True)
        curve.sigClicked.connect(self.selectPlot)
        curve.config.sigParameterChanged.connect(self._updateViewLimits)
        self.plots.append(curve)
        self.plotItem.addItem(curve.plotDataItem)
        self._updateViewLimits()
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
        self._updateViewLimits()


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
