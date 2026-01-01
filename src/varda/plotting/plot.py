from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QSignalBlocker
from PyQt6.QtGui import QPen, QColor
import pyqtgraph as pg

from varda.common.ui import VBoxBuilder, HBoxBuilder, SectionBox
from varda.common.parameter import ParameterGroup, FloatParameter, ColorParameter


@dataclass
class PlotData:
    data: pg.PlotDataItem
    offset: tuple[float, float] = (0.0, 0.0)
    scale: float = 1.0
    thickness: float = 2.0
    color: str = "r"


class VardaPlotWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.selectedPlot = None

        self.plots: list[pg.PlotDataItem] = []
        self.plotMetadata: list[PlotData] = []
        self.gv = pg.GraphicsView()
        # if the user clicks on the plot area and none of the plots catch the click (therefore selecting it), deselect any selected plot
        self.gv.scene().sigMouseClicked.connect(self.onSceneClicked)
        self.plotItem = pg.PlotItem()
        self.plotItem.addLegend()
        self
        self.plotItem.setMouseEnabled(x=False, y=False)
        self.gv.setCentralItem(self.plotItem)

        self.lineWidth = FloatParameter(
            name="Line Width",
            default=1.0,
            description=None,
            units="px",
            valueRange=(0.1, 10.0),
        )
        self.lineColor = ColorParameter(
            name="Line Color",
            default="#ff0000",
            description=None,
        )
        self.offset = FloatParameter(
            name="Offset",
            default=0.0,
            description=None,
            units="units",
        )
        self.scale = FloatParameter(
            name="Scale",
            default=1.0,
            description=None,
            units="x",
        )
        self.lineParams = ParameterGroup(
            [self.lineWidth, self.lineColor, self.offset, self.scale]
        )
        self.lineParams.sigParameterChanged.connect(self.onLineParamsChanged)

        self.backgroundColor = ColorParameter(
            name="Background Color",
            default="#000000",
            description=None,
        )
        self.windowParams = ParameterGroup([self.backgroundColor])
        self.windowParams.sigParameterChanged.connect(self.onWindowParamsChanged)
        self.setLayout(
            HBoxBuilder()
            .withWidget(self.gv)
            .withLayout(
                VBoxBuilder(Qt.AlignmentFlag.AlignTop)
                .withWidget(SectionBox("Curve Settings", self.lineParams))
                .withWidget(SectionBox("Window Settings", self.windowParams))
            )
        )

    def onLineParamsChanged(self):
        if self.selectedPlot is not None:
            pen = pg.mkPen(color=self.lineColor.value, width=self.lineWidth.value)
            self.selectedPlot.setPen(pen)
            self.selectedPlot.setTransform(
                pg.QtGui.QTransform()
                .scale(1.0, self.scale.value)
                .translate(0.0, self.offset.value)
            )

    def onWindowParamsChanged(self):
        color = QColor(self.backgroundColor.value)
        self.gv.setBackground(color)

    def plot(self, x, y, **kwargs) -> pg.PlotDataItem:
        plot = pg.PlotDataItem(x, y, **kwargs)
        plot.setCurveClickable(True, width=20)
        plot.sigClicked.connect(self.selectPlot)

        self.addPlot(plot)
        return plot

    def selectPlot(self, plot: pg.PlotDataItem):
        self.deselectPlot()
        self.selectedPlot = plot
        plot.setShadowPen(pg.mkPen("#ffff0088", width=10))

        with self.lineParams.editParams():
            self.offset.set(plot.transform().dy())
            self.scale.set(plot.transform().m22())
            currentPen: QPen = plot.opts["pen"]
            if currentPen is not None:
                self.lineColor.set(currentPen.color())
                self.lineWidth.set(currentPen.widthF())

    def onSceneClicked(self, event):
        if event.isAccepted():
            return
        self.deselectPlot()

    def deselectPlot(self):
        if self.selectedPlot is not None:
            self.selectedPlot.setShadowPen(None)
        self.selectedPlot = None
        self.lineParams.resetToDefaults()

    def addPlot(self, plot: pg.PlotDataItem):
        self.plots.append(plot)
        self.plotItem.addItem(plot)

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
    p1 = w.plot(
        x, y, pen=pg.mkPen(color="g", width=2), name="Sine Wave", antialias=True
    )

    x2 = np.linspace(0, 10, 100)
    y2 = np.cos(x2)
    p2 = w.plot(
        x2, y2, pen=pg.mkPen(color="r", width=2), name="Cosine Wave", antialias=True
    )
    w.show()

    # when user presses F, remove p1
    def keyPressEvent(event):
        if event.key() == Qt.Key.Key_F:
            w.removePlot(p1)

    w.keyPressEvent = keyPressEvent

    app.exec()
