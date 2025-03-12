from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QDockWidget, QLabel, QWidget,
    QListWidget, QListWidgetItem, QScrollArea, QVBoxLayout, QFileDialog, QMenu
)
from PyQt6.QtCore import Qt, QSize, QPoint
import numpy as np
import pyqtgraph as pg
import csv
from features.image_view_raster import getRasterView
from features.image_view_roi import getROIView
from features.image_view_histogram import getHistogramView
from features.image_view_stretch import getStretchView
from features.image_view_band import getBandView

class ControlPanel(QMainWindow):
    """
    Revamped Control Panel with expandable menu options.
    """
    def __init__(self, main_window: QMainWindow, parent=None):
        super(ControlPanel, self).__init__(parent)
        # as discussed, we will have one (1) control panel per image 
        # We will implement a mutli-image control panel later. The _image
        # property should never be changed after it is set.
        self._image = main_window.selectedImage
        self.project_context = main_window.proj
        self.main_window = main_window

        self.setWindowTitle("Control Panel")
        self.resize(600, 300)
        
        # Create Dock Widget
        self.tabsDock = QDockWidget("Control Panel", self)
        self.dock_widget_content = QWidget()
        self.main_layout = QVBoxLayout()

        self.activeImageLabel = QLabel("No image selected")
        self.activeImageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activeImageLabel.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        # Header Label
        self.headerLabel = QLabel("Control Panel Menu")
        self.headerLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.headerLabel.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        # Create Expandable Menu
        self.treeWidget = QTreeWidget()
        self.treeWidget.setHeaderLabel("Options")
        
        # Main Category: Views
        views_item = QTreeWidgetItem(self.treeWidget)
        views_item.setText(0, "Views")

        self.edit_item = QTreeWidgetItem(self.treeWidget)
        self.edit_item.setText(0, "Edit")
        self.treeWidget.addTopLevelItem(self.edit_item)

        # Band View child
        self.bandViewLabel = QTreeWidgetItem(self.edit_item)
        self.bandViewLabel.setText(0, "Band View")
        self.treeWidget.addTopLevelItem(self.bandViewLabel)
        self.bandViewItem = QTreeWidgetItem(self.bandViewLabel)

        # Histogram View child
        self.histogramViewLabel = QTreeWidgetItem(self.edit_item)
        self.histogramViewLabel.setText(0, "Histogram View")
        self.treeWidget.addTopLevelItem(self.histogramViewLabel)
        self.histogramViewItem = QTreeWidgetItem(self.histogramViewLabel)

        # stretch View child
        self.stretchViewLabel = QTreeWidgetItem(self.edit_item)
        self.stretchViewLabel.setText(0, "Stretch View")
        self.treeWidget.addTopLevelItem(self.stretchViewLabel)
        self.stretchViewItem = QTreeWidgetItem(self.stretchViewLabel)

        self.plotsLabel = QTreeWidgetItem(self.treeWidget)
        self.plotsLabel.setText(0, "Plots")
        self.treeWidget.addTopLevelItem(self.plotsLabel)
        self.plotsViewItem = QTreeWidgetItem(self.plotsLabel)
        
        # View options
        view_options = {
            "Raster Data": self.openRasterView,
            "ROI Table": self.openROIView,     
        }
        
        for name, method in view_options.items():
            option_item = QTreeWidgetItem(views_item)
            option_item.setText(0, name)
            option_item.setData(0, Qt.ItemDataRole.UserRole, method)
        
        self.treeWidget.itemClicked.connect(self.handleItemClick)
        
        # Expand Views by default
        views_item.setExpanded(False)
        self.edit_item.setExpanded(False)
        
        # Add widgets to layout
        self.main_layout.addWidget(self.headerLabel)
        self.main_layout.addWidget(self.activeImageLabel)
        self.main_layout.addWidget(self.treeWidget)
        self.dock_widget_content.setLayout(self.main_layout)
        
        # Set Dock Widget Content
        self.tabsDock.setWidget(self.dock_widget_content)
        self.treeWidget.itemClicked.connect(self.handleEditTabExpanded)
        self.treeWidget.itemExpanded.connect(self.handleItemExpanded)
        self.treeWidget.itemCollapsed.connect(self.handleItemCollapsed)
        self.treeWidget.itemClicked.connect(self.handleViewClick)

        self.rasterViewObj = None
        self.editContainer = None
        self.bandView = None
        self.histogramView = None
        self.stretchView = None
        self.plotsView = None

    @property
    def image(self):
        # returns the image associated with this control panel
        return self._image

    def updateActiveImage(self, index):
        """
        Update the active image index and label.
        """
        self.imageIndex = index
        if index is None:
            self.activeImageLabel.setText("No image selected")
        else:
            # Use the image index for the label
            fn = self.project_context.getImage(index).metadata._filename.split("/")[-1]
            if (len(fn) > 10):
                fn_short = fn[0:10]
            else:
                fn_short = fn
            self.activeImageLabel.setText(f"Active Image: {fn_short}...")
            self.activeImageLabel.setToolTip(fn)

    def handleItemClick(self, item, column):
        """
        Handle clicks on tree widget items.
        """
        method = item.data(0, Qt.ItemDataRole.UserRole)
        if callable(method):
            method()
    
    def openRasterView(self):
        view = getRasterView(self.project_context, self.image.index, self.main_window)
        self.rasterViewObj = view
        self.main_window.setCentralWidget(view)
        #self.openBandView()
    
    def openROIView(self):
        view = getROIView(self.project_context, self.image.index, self.main_window)
        if (self.rasterViewObj):
            view.viewModel.setRasterView(self.rasterViewObj)
        else:
            print("Must open raster view before drawing an ROI")
        dock = QDockWidget("ROI Table", self.main_window)
        dock.setWidget(view)
        self.main_window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

    
    def openROIView(self):
        """Retrieve or create the ROI Table for the selected image."""
        view = getROIView(self.project_context, self.image.index, self.main_window)
        if (self.rasterViewObj):
            view.viewModel.setRasterView(self.rasterViewObj)

        roi_view = self.project_context.setROIView(self.image.index, view)

        # Close any existing ROI tables before adding the new one
        for dock in self.findChildren(QDockWidget):
            if dock.widget() and isinstance(dock.widget(), type(roi_view)):
                dock.close()

        # Add ROI Table to UI
        dock = QDockWidget("ROI Table", self.main_window)
        dock.setWidget(roi_view)
        self.main_window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)
    

    def handleEditTabExpanded(self, item):
        """
        Add the Band View dynamically when the Edit tab is expanded.
        """
        if item == self.edit_item and self.rasterViewObj:
            self.bandViewItem.setHidden(False)
            self.histogramViewItem.setHidden(False)
            self.StretchViewItem.setHidden(False)

    
    def handleEditTabCollapsed(self, item):
        """
        Hide the Band View inside the Edit tab when collapsed.
        """
        if item == self.edit_item:
            self.bandViewItem.setHidden(True)
            self.histogramViewItem.setHidden(True)
            self.removeBandView()
            self.removeHistogramView()

    def handleItemExpanded(self, item):
        """ Show the Band View or Histogram View when their labels are expanded. """
        if item == self.bandViewLabel:
            self.showBandView()
        elif item == self.histogramViewLabel:
            self.showHistogramView()
        elif item == self.stretchViewLabel:
            self.showStretchView()
        elif item == self.plotsLabel:
            self.showPlotsView()

    def handleItemCollapsed(self, item):
        """ Hide the Band View or Histogram View when their labels are collapsed, but keep them in memory. """
        if item == self.bandViewLabel and self.bandView:
            self.bandView.hide()
        elif item == self.histogramViewLabel and self.histogramView:
            self.histogramView.hide()
        elif item == self.stretchViewLabel and self.stretchView:
            self.stretchView.hide()
        elif item == self.plotsLabel and self.plotsView:
            self.plotsView.hide()

    def handleViewClick(self, item, column):
        """ Prevent clicks from toggling views incorrectly. """
        if item == self.bandViewItem or item == self.histogramViewItem or item == self.stretchViewItem:
            return

    def showBandView(self):
        """ Show the Band View inside the Band Label item. """
        if self.bandView is None:  # Create only if needed
            self.bandView = getBandView(self.project_context, self.imageIndex, self)
            self.treeWidget.setItemWidget(self.bandViewItem, 0, self.bandView)
        self.bandView.show()

    def showHistogramView(self):
        """ Show the Histogram View inside the Histogram Label item. """
        if self.histogramView is None:  # Create only if needed
            self.histogramView = getHistogramView(self.project_context, self.imageIndex, self)
            self.treeWidget.setItemWidget(self.histogramViewItem, 0, self.histogramView)
        self.histogramView.show()

    def showStretchView(self):
        """ Show the Stretch View inside the Stretch Label item. """
        if self.stretchView is None:
            self.stretchView = getStretchView(self.project_context, self.imageIndex, self)
            self.treeWidget.setItemWidget(self.stretchViewItem, 0, self.stretchView)
        self.stretchView.show()

    def showPlotsView(self):
        """Show the Plots View inside the Plots Label item."""
        if self.plotsView is None:
            self.plotsView = PlotsView(self.project_context, self.imageIndex, self)
            self.treeWidget.setItemWidget(self.plotsViewItem, 0, self.plotsView)
        self.plotsView.show()


class PlotsView(QWidget):
    """Displays saved plots for an image with a right-click menu for each item."""

    def __init__(self, proj, image_index, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.image_index = image_index
        self.setWindowTitle("Plots View")

        # Scrollable list
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)

        self.listWidget = QListWidget()
        self.scrollArea.setWidget(self.listWidget)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.scrollArea)
        self.setLayout(layout)

        # Load saved plots
        self.loadPlots()

        # Right-click context menu
        self.listWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.listWidget.customContextMenuRequested.connect(self.showContextMenu)

        self.proj.sigDataChanged.connect(self.onDataChanged)

    def onDataChanged(self, index, changeType):
        """Refresh plot list when a new plot is added."""
        if index == self.image_index and changeType == self.proj.ChangeType.PLOT:
            self.loadPlots()

    def loadPlots(self):
        """Load saved plots and display up to 5 at a time."""
        self.listWidget.clear()
        plots = self.proj.getPlots(self.image_index)

        for plot in plots[:5]:  # Show only 5 plots
            item = QListWidgetItem(f"{plot.timestamp} - {plot.plot_type}")
            item.setData(Qt.ItemDataRole.UserRole, plot)  # Store the plot object in the item
            self.listWidget.addItem(item)

        self.listWidget.itemClicked.connect(self.showPlotInWindow)

    def showPlotInWindow(self, item):
        """Opens a separate pg.plot window displaying the selected plot."""
        plot = item.data(Qt.ItemDataRole.UserRole)
        if plot:
            self.plotWindow = pg.plot(
                title=f"ROI Mean Spectrum - {plot.timestamp}",
                pen="y"
            )
            self.plotWindow.setLabels(left="Intensity", bottom="Wavelength Index")
            self.plotWindow.addLegend()

            # Extract mean spectrum data from the ROI
            mean_spectrum = plot.data  # Mean spectrum from FreeHandROI
            wavelengths = np.arange(len(mean_spectrum))  # Generate dummy wavelengths

            # Plot the mean spectrum
            self.plotWindow.plot(wavelengths, mean_spectrum, pen="y", name="Mean Spectrum")

            self.plotWindow.show()

    def showContextMenu(self, pos: QPoint):
        """Display the context menu when right-clicking a plot item."""
        item = self.listWidget.itemAt(pos)
        if not item:
            return

        plot = item.data(Qt.ItemDataRole.UserRole)
        if not plot:
            return

        menu = QMenu(self)

        openAction = menu.addAction("Open Plot")
        exportAction = menu.addAction("Export Plot")
        discardAction = menu.addAction("Discard Plot")

        action = menu.exec(self.listWidget.mapToGlobal(pos))

        if action == openAction:
            self.showPlotInWindow(item)
        elif action == exportAction:
            self.exportPlot(plot)
        elif action == discardAction:
            self.discardPlot(item, plot)

    def exportPlot(self, plot):
        """Export plot data to a CSV file."""
        fileName, _ = QFileDialog.getSaveFileName(self, "Save Plot Data", "", "CSV Files (*.csv)")
        if fileName:
            with open(fileName, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Wavelength Index", "Mean Intensity"])
                for i, value in enumerate(plot.data):
                    writer.writerow([i, value])

    def discardPlot(self, item, plot):
        """Remove the plot from the list and from the project context."""
        self.listWidget.takeItem(self.listWidget.row(item))  # Remove from UI
        self.proj.getPlots(self.image_index).remove(plot)  # Remove from ProjectContext