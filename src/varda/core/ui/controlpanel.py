import logging

from PyQt6.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QDockWidget,
    QLabel,
    QWidget,
    QScrollArea,
    QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
import numpy as np

from varda.core.data import ProjectContext
from varda.features.image_view_roi import getROIView
from varda.features.image_view_band import BandManager
from varda.features.image_view_stretch import StretchManager
from varda.features.image_view_metadata import openMetadataEditor
from varda.gui.widgets.image_plot_widget import ImagePlotWidget

logger = logging.getLogger(__name__)


class ControlPanel(QWidget):
    """
    Control panel tied dynamically to the currently selected image.
    """

    sigPixelPlotClicked = pyqtSignal()

    def __init__(self, proj: ProjectContext, imageIndex: int, rasterView, parent=None):
        super().__init__(parent)

        print("[DEBUG] 🔥 ControlPanel CLASS INSTANTIATED 🔥")

        self.project_context = proj
        self.imageIndex = imageIndex
        self.rasterView = rasterView
        self.rasterView.sigImageClicked.connect(self.updatePixelPlotFromCrosshair)

        self.setWindowTitle("Control Panel")
        self.resize(600, 300)

        self.tabsDock = QDockWidget("Control Panel", self)
        self.dock_widget_content = QWidget()

        self.headerLabel = QLabel("Control Panel Menu")
        self.headerLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.headerLabel.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.activeImageLabel = QLabel("No image selected")
        self.activeImageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activeImageLabel.setStyleSheet("font-size: 14px; font-weight: bold;")

        # setup scrollable area for the tools
        self.toolSectionLayout = QVBoxLayout()
        self.toolSectionContainer = QWidget()
        self.toolSectionContainer.setLayout(self.toolSectionLayout)
        self.toolSection = QScrollArea()
        self.toolSection.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.toolSection.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.toolSection.setWidgetResizable(True)
        self.toolSection.setWidget(self.toolSectionContainer)

        self.editMetadataButton = QPushButton("Metadata")
        self.editMetadataButton.setToolTip("View and edit image metadata properties")
        self.editMetadataButton.clicked.connect(
            lambda: openMetadataEditor(self.project_context, self.imageIndex, self)
        )

        self.bandView = BandManager(self.project_context, self.imageIndex, self)

        self.histogramView = StretchManager(self.project_context, self.imageIndex, self)
        self.histogramView.sigStretchSelected.connect(self.rasterView.selectStretch)

        self.pixelPlot = ImagePlotWidget(
            self.project_context, self.imageIndex, parent=self
        )
        self.pixelPlot.sigClicked.connect(self.handlePixelPlotClicked)

        self.pixelPlotPopup = None  # Will be created on first click
        self.lastPixelCoords = (0, 0)  # Track last clicked pixel for popup
        self.plotsView = None

        self.ROITable = getROIView(self.project_context, self.imageIndex, self)
        self.ROITable.viewModel.setRasterView(self.rasterView)

        # Connect signals/slots for updates in both directions
        # TODO: This should be moved to the roi view model or something
        self.ROITable.roiSelectionChanged.connect(
            lambda roi_index: (
                self.rasterView.highlightROI(roi_index)
                if hasattr(rasterView, "highlightROI")
                else None
            )
        )

        self.toolSectionLayout.addWidget(self.editMetadataButton)
        self.toolSectionLayout.addWidget(self.ROITable)
        self.toolSectionLayout.addWidget(self.bandView)
        self.toolSectionLayout.addWidget(self.histogramView)
        self.toolSectionLayout.addWidget(self.pixelPlot)

        # create layout and add widgets
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.headerLabel)
        self.main_layout.addWidget(self.activeImageLabel)
        self.main_layout.addWidget(self.toolSection)

        self.dock_widget_content.setLayout(self.main_layout)
        self.tabsDock.setWidget(self.dock_widget_content)

        self.updateActiveImage(imageIndex)

    @property
    def image(self):
        return self.project_context.getImage(self.imageIndex)

    def updateActiveImage(self, index):
        self.imageIndex = index
        if self.imageIndex is None:
            self.activeImageLabel.setText("No image selected")
        else:
            filename = self.image.metadata.name
            self.activeImageLabel.setText(f"Active Image: {filename[:10]}...")
            self.activeImageLabel.setToolTip(filename)

    def handlePixelPlotClicked(self):
        self.sigPixelPlotClicked.emit()

        # Only create once
        if self.pixelPlotPopup is None:
            self.pixelPlotPopup = ImagePlotWidget(
                self.project_context,
                self.image.index,
                isWindow=True,
                parent=self.parent(),
            )
            self.pixelPlotPopup.destroyed.connect(self.removePixelPlotPopup)
            logger.debug("PixelPlotPopup created")

        # Use last clicked pixel
        x, y = self.lastPixelCoords
        self.pixelPlotPopup.showPixelSpectrum(x, y)

    def removePixelPlotPopup(self, obj=None):
        """Remove the pixel plot popup window from tracking."""
        self.pixelPlotPopup = None
        logger.debug("PixelPlotPopup removed")

    def updatePixelPlotFromCrosshair(self, x, y):
        self.pixelPlot.showPixelSpectrum(x, y)
        if self.pixelPlotPopup:
            self.pixelPlotPopup.showPixelSpectrum(x, y)
        self.lastPixelCoords = (x, y)  # Track for popup
