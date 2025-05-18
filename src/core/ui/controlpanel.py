from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QDockWidget, QLabel,
    QWidget, QListWidget, QListWidgetItem, QScrollArea, QFileDialog, QMenu
)
from PyQt6.QtCore import Qt, QPoint
import numpy as np
import pyqtgraph as pg
import csv

from features.image_view_band import BandManager
from features.image_view_stretch import StretchManager, getStretchView
from gui.widgets.pixel_plot_widget import PixelPlotWidget

class ControlPanel(QMainWindow):
    """
    Control panel tied dynamically to the currently selected image.
    """

    def __init__(self, main_window: QMainWindow, parent=None):
        super().__init__(parent)

        print("[DEBUG] 🔥 ControlPanel CLASS INSTANTIATED 🔥")

        self.main_window = main_window
        self.project_context = main_window.proj

        self.setWindowTitle("Control Panel")
        self.resize(600, 300)

        self.tabsDock = QDockWidget("Control Panel", self)
        self.dock_widget_content = QWidget()
        self.main_layout = QVBoxLayout()

        self.headerLabel = QLabel("Control Panel Menu")
        self.headerLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.headerLabel.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.activeImageLabel = QLabel("No image selected")
        self.activeImageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activeImageLabel.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.treeWidget = QTreeWidget()
        self.treeWidget.setHeaderLabel("Options")

        self.views_item = QTreeWidgetItem(self.treeWidget, ["Views"])
        self.edit_item = QTreeWidgetItem(self.treeWidget, ["Edit"])
        self.plotsLabel = QTreeWidgetItem(self.treeWidget, ["Plots"])

        self.bandViewLabel = QTreeWidgetItem(self.edit_item, ["Band View"])
        self.histogramViewLabel = QTreeWidgetItem(self.edit_item, ["Histogram View"])
        self.stretchViewLabel = QTreeWidgetItem(self.edit_item, ["Stretch View"])

        self.bandViewItem = QTreeWidgetItem(self.bandViewLabel)
        self.histogramViewItem = QTreeWidgetItem(self.histogramViewLabel)
        self.stretchViewItem = QTreeWidgetItem(self.stretchViewLabel)
        self.plotsViewItem = QTreeWidgetItem(self.plotsLabel)
        self.pixelPlotItem = QTreeWidgetItem(self.plotsLabel, ["Pixel Plot"])

        for name in ["Raster Data", "ROI Table"]:
            QTreeWidgetItem(self.views_item, [name])

        self.main_layout.addWidget(self.headerLabel)
        self.main_layout.addWidget(self.activeImageLabel)
        self.main_layout.addWidget(self.treeWidget)
        self.dock_widget_content.setLayout(self.main_layout)
        self.tabsDock.setWidget(self.dock_widget_content)

        self.treeWidget.itemClicked.connect(self.handleItemClick)
        self.treeWidget.itemExpanded.connect(self.handleItemExpanded)
        self.treeWidget.itemCollapsed.connect(self.handleItemCollapsed)
        self.treeWidget.itemClicked.connect(self.handleViewClick)

        self.views_item.setExpanded(False)
        self.edit_item.setExpanded(False)

        self.updateActiveImage(self.image.index if self.image else None)

        self.bandView = BandManager(self.project_context, self.image.index, self)
        self.treeWidget.setItemWidget(self.bandViewItem, 0, self.bandView)
        self.bandView.hide()

        self.histogramView = StretchManager(self.project_context, self.image.index, self)
        self.treeWidget.setItemWidget(self.histogramViewItem, 0, self.histogramView)
        self.histogramView.hide()

        self.stretchView = getStretchView(self.project_context, self.image.index, self)
        self.treeWidget.setItemWidget(self.stretchViewItem, 0, self.stretchView)
        self.stretchView.hide()

        self.pixelPlot = PixelPlotWidget()
        self.pixelPlot.clicked.connect(self.showPixelPlotWindow)
        self.treeWidget.setItemWidget(self.pixelPlotItem, 0, self.pixelPlot)
        self.pixelPlot.hide()

        self.plotsView = None

    @property
    def image(self):
        return self.main_window.selectedImage

    def updateActiveImage(self, index):
        if index is None:
            self.activeImageLabel.setText("No image selected")
        else:
            img = self.project_context.getImage(index)
            filename = img.metadata.filePath.split("/")[-1]
            self.activeImageLabel.setText(f"Active Image: {filename[:10]}...")
            self.activeImageLabel.setToolTip(filename)

    def showPixelPlotWindow(self):
        image = self.image
        if image is None or image.raster is None:
            print("[DEBUG] No image data for popup.")
            return

        try:
            wavelengths = np.char.strip(image.metadata.wavelengths.astype(str)).astype(float)
        except Exception:
            wavelengths = np.arange(image.raster.shape[2])

        # Only create once
        if not hasattr(self, 'pixelPlotPopup') or self.pixelPlotPopup is None:
            from features.image_view_raster.PixelPlotWindow import PixelPlotWindow
            self.pixelPlotPopup = PixelPlotWindow()
            # Register with main window for tracking
            if hasattr(self, 'main_window') and self.main_window:
                self.main_window.trackPixelPlotWindow(self.pixelPlotPopup)

        # Use last clicked pixel (or 0,0 if not tracked)
        x, y = getattr(self, 'lastPixelCoords', (0, 0))
        spectrum = image.raster[y, x, :]
        self.pixelPlotPopup.update_plot(wavelengths, spectrum, (x, y))
        self.pixelPlotPopup.show()

    def handleItemClick(self, item, column):
        name = item.text(0)
        print(f"[DEBUG] handleItemClick -> '{name}' clicked")
        if name == "Raster Data":
            self.main_window.openRasterView(self.image.index)
        elif name == "ROI Table":
            self.main_window.openROIView(self.image.index)
        elif name == "Band View":
            self.main_window.openBandView(self.image.index)
        elif name == "Histogram View":
            self.main_window.openHistogramView(self.image.index)
        elif name == "Stretch View":
            self.main_window.openStretchView(self.image.index)
        elif name == "Pixel Plot":
            self.showPixelPlot()

    def handleItemExpanded(self, item):
        if item == self.plotsLabel:
            self.showPlotsView()

    def handleItemCollapsed(self, item):
        if item == self.plotsLabel and self.plotsView:
            self.plotsView.hide()

    def handleViewClick(self, item, column):
        if item in [self.bandViewItem, self.histogramViewItem, self.stretchViewItem]:
            return

    def showPlotsView(self):
        if self.plotsView is None:
            from features.image_view_histogram import PlotsView
            self.plotsView = PlotsView(self.project_context, self.image.index, self)
            self.treeWidget.setItemWidget(self.plotsViewItem, 0, self.plotsView)
        self.plotsView.show()

    def showPixelPlot(self):
        image = self.image
        if image is None or image.raster is None:
            print("[DEBUG] No image data for pixel plot.")
            return

        try:
            wavelengths = np.asarray(image.metadata.wavelengths, dtype=float)
        except Exception as e:
            print(f"[DEBUG] Failed to get wavelength data: {e}")
            wavelengths = np.arange(image.raster.shape[2])

        # Dummy test pixel for now until wired
        spectrum = image.raster[0, 0, :]
        coords = (0, 0)

        self.pixelPlot.update_plot(wavelengths, spectrum, coords)
        self.pixelPlot.show()

    def updatePixelPlotFromCrosshair(self, x, y):
        image = self.image
        if image is None or image.raster is None:
            print("[DEBUG] Cannot update pixel plot — no image.")
            return

        try:
            wavelengths = np.char.strip(image.metadata.wavelengths.astype(str)).astype(float)
        except Exception:
            wavelengths = np.arange(image.raster.shape[2])

        spectrum = image.raster[y, x, :]
        self.lastPixelCoords = (x, y)  # Track for popup
        self.pixelPlot.update_plot(wavelengths, spectrum, (x, y))
        if hasattr(self, 'pixelPlotPopup') and self.pixelPlotPopup:
            self.pixelPlotPopup.update_plot(wavelengths, spectrum, (x, y))

