from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QDockWidget, QLabel, QWidget, QSplitter
)
from PyQt6.QtCore import Qt
from core.data.project_context import ProjectContext
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
        
        # View options
        view_options = {
            "Raster Data": self.openRasterView,
            "ROI Table": self.openROIView,     
            "Stretch": self.openStretchView,
        }
        
        for name, method in view_options.items():
            option_item = QTreeWidgetItem(views_item)
            option_item.setText(0, name)
            option_item.setData(0, Qt.ItemDataRole.UserRole, method)
        
        self.treeWidget.itemClicked.connect(self.handleItemClick)
        
        # # Sub-options (placeholders for now)
        # for i in range(1, 6):
        #     option_item = QTreeWidgetItem(views_item)
        #     option_item.setText(0, f"Option {i}")
        
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
        self.treeWidget.itemCollapsed.connect(self.handleEditTabCollapsed)

        self.rasterViewObj = None
        self.editContainer = None
        self.bandView = None
        self.histogramView = None

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
    
    def openHistogramView(self, index):
        view = getHistogramView(self.project_context, index, self.main_window)
        dock = QDockWidget("Histogram", self.main_window)
        dock.setWidget(view)
        self.main_window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)
    
    def openStretchView(self, index):
        view = getStretchView(self.project_context, index, self.main_window)
        dock = QDockWidget("Stretch View", self.main_window)
        dock.setWidget(view)
        self.main_window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

    def handleEditTabExpanded(self, item):
        """
        Add the Band View dynamically when the Edit tab is expanded.
        """
        if item == self.edit_item:
            self.showEditViews(self.imageIndex)

    def handleEditTabCollapsed(self, item):
        """
        Hide the Band View inside the Edit tab when collapsed.
        """
        if item == self.edit_item and self.editContainer:
            self.editContainer.hide()

    def showHistogramView(self):
        """ Show or create the Histogram View inside the Edit tab. """
        if not self.histogramView:
            self.histogramView = getHistogramView(self.project_context, self.image.index, self)
            self.histogramViewItem = QTreeWidgetItem(self.edit_item)
            self.histogramViewItem.setText(0, "Histogram View")
            self.treeWidget.setItemWidget(self.edit_item, 0, self.histogramView)
        self.histogramView.show()
    
    def showBandView(self):
        """
        Show or create the Band View inside the Edit tab.
        """
        if not self.bandView:
            self.bandView = getBandView(self.project_context, self.image.index, self)
            self.treeWidget.setItemWidget(self.edit_item, 0, self.bandView)
        self.bandView.show()

    def addBandView(self):
        """
        Add the Band View inside the Options tree widget under the Edit tab.
        """
        if self.bandView:
            self.bandView.deleteLater()  # Remove previous band view if exists
        
        if self.rasterViewObj:
            self.bandView = getBandView(self.project_context, self.image.index, self.treeWidget)
            self.treeWidget.setItemWidget(self.edit_item, 0, self.bandView)

    def showEditViews(self, index):
        """ Show or create the Band View and Histogram View inside the Edit tab. """
        if not self.editContainer:
            self.editContainer = QWidget()
            self.editLayout = QVBoxLayout(self.editContainer)

            # Create Band View
            self.bandView = getBandView(self.project_context, index, self)
            self.bandViewItem = QTreeWidgetItem(self.edit_item)
            self.bandViewItem.setText(0, "Band View")

            # Create Histogram View
            self.histogramView = getHistogramView(self.project_context, index, self)
            self.histogramViewItem = QTreeWidgetItem(self.edit_item)
            self.histogramViewItem.setText(0, "Histogram View")

            # Add both widgets to a vertical layout inside the container
            self.editLayout.addWidget(self.bandView)
            self.editLayout.addWidget(self.histogramView)

            # Assign the container to the tree widget
            self.treeWidget.setItemWidget(self.edit_item, 0, self.editContainer)

        # Show container
        self.editContainer.show()
