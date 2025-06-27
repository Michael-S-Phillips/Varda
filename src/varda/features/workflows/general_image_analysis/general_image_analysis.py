from PyQt6.QtWidgets import QMainWindow, QDockWidget
from PyQt6.QtCore import Qt
import varda

class GeneralImageAnalysis(QMainWindow):
    """A workflow for performing general image analysis"""

    def __init__(self, imageIndex=0, parent=None):
        super().__init__(parent)

        self.bandView = varda.features.image_view_band.getBandView(varda.app.proj, imageIndex, self)
        self.stretchView = varda.features.image_view_stretch.StretchManager(varda.app.proj, imageIndex, self)
        self.rasterView = varda.features.image_view_raster.getRasterView(varda.app.proj, imageIndex, self)
        self.initUI()
        self.showMaximized()

    def initUI(self):
        """Initialize the user interface for the general image analysis workflow."""
        self.setWindowTitle("General Image Analysis")

        # Set up the main layout
        self.setCentralWidget(self.rasterView)

        stretchDock = QDockWidget("Stretch View", self)
        stretchDock.setWidget(self.stretchView)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, stretchDock)

        bandDock = QDockWidget("Band View", self)
        bandDock.setWidget(self.bandView)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, bandDock)

    def connectSignals(self):
        """Connect signals to their respective slots."""
        self.bandView.sigBandChanged.connect(self.rasterView.selectBand)
        self.stretchView.sigStretchSelected.connect(self.rasterView.selectStretch)
