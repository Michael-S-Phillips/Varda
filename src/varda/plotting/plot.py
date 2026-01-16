from dataclasses import dataclass, field
from unicodedata import name

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QSignalBlocker, QObject, pyqtSignal
from PyQt6.QtGui import QPen, QColor
import pyqtgraph as pg

from varda.common.ui import VBoxBuilder, HBoxBuilder, SectionBox
from varda.common.parameter import (
    ParameterGroup,
    ParameterGroupWidget,
    FloatParameter,
    Vec2Parameter,
    ColorParameter,
    BoolParameter,
)


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

    @classmethod
    def fromData(cls, x, y, **kwargs):
        plotItem = pg.PlotDataItem(x, y, **kwargs)
        defaultConfig = CurveConfig()
        return cls(plotItem, defaultConfig)


class VardaPlotWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.selectedCurve: Curve | None = None

        self.plots: list[Curve] = []
        self.gv = pg.GraphicsView()
        # if the user clicks on the plot area and none of the plots catch the click (therefore selecting it), deselect any selected plot
        self.gv.scene().sigMouseClicked.connect(self.onSceneClicked)
        self.plotItem = pg.PlotItem()
        self.plotItem.addLegend()
        self.plotItem.setMouseEnabled(x=False, y=False)
        self.gv.setCentralItem(self.plotItem)

        self.backgroundColor = ColorParameter(
            name="Background Color",
            default="#000000",
            description=None,
        )
        self.autoViewRange = BoolParameter(
            name="Automatically Calculate Range",
            default=True,
            description="Whether view range should be automatically calculated based on the plotted data, or manually set.",
        )
        self.viewRangeX = Vec2Parameter(
            name="X View Range",
            default=None,
            description=None,
            valueNames=("Min", "Max"),
        )
        self.viewRangeY = Vec2Parameter(
            name="Y View Range",
            default=None,
            description=None,
            valueNames=("Min", "Max"),
        )

        self.windowParams = ParameterGroupWidget(
            [self.backgroundColor, self.autoViewRange]
        )
        self.windowParams.sigParameterChanged.connect(self.onWindowParamsChanged)

        self.rangeParams = ParameterGroupWidget([self.viewRangeX, self.viewRangeY])
        self.rangeParams.sigParameterChanged.connect(self.onRangeParamsChanged)
        self.rangeParams.hide()

        self.curveSettingsBox = SectionBox("Curve Settings")
        self.setLayout(
            HBoxBuilder()
            .withWidget(self.gv)
            .withLayout(
                VBoxBuilder(Qt.AlignmentFlag.AlignTop)
                .withWidget(self.curveSettingsBox)
                .withWidget(
                    SectionBox(
                        "Window Settings",
                        VBoxBuilder()
                        .withWidget(self.windowParams)
                        .withWidget(self.rangeParams),
                    )
                )
            )
        )

    def onWindowParamsChanged(self):
        color = QColor(self.backgroundColor.value)
        self.gv.setBackground(color)

        if self.autoViewRange.get():
            self.plotItem.enableAutoRange()
            self.rangeParams.hide()
        else:
            self.plotItem.disableAutoRange()
            self.rangeParams.show()
            self.onRangeParamsChanged()

    def onRangeParamsChanged(self):
        if not self.autoViewRange.get():
            xRange = self.viewRangeX.get()
            yRange = self.viewRangeY.get()
            self.plotItem.setXRange(xRange.x, xRange.y)
            self.plotItem.setYRange(yRange.x, yRange.y)

    def plot(self, x, y, **kwargs):
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

    def selectPlot(self, curve: Curve):
        self.deselectPlot()
        self.selectedCurve = curve
        curve.setHighlighted(True)
        self.curveSettingsBox.setContent(curve.config.createWidget())

    def onSceneClicked(self, event):
        if event.isAccepted():
            return
        self.deselectPlot()

    def deselectPlot(self):
        if self.selectedCurve is not None:
            self.selectedCurve.setHighlighted(False)
            self.curveSettingsBox.setContent(None)
        self.selectedCurve = None

    def removePlot(self, plot: pg.PlotDataItem):
        if plot in self.plots:
            self.plots.remove(plot)
            self.plotItem.removeItem(plot)

    def clearPlots(self):
        for plot in self.plots:
            self.plotItem.removeItem(plot)
        self.plots.clear()


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
