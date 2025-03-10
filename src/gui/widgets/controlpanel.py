from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QDockWidget, QLabel, QWidget, QSplitter
)
from PyQt6.QtCore import Qt, QSize
# from features.image_view_raster import getRasterView
# from features.image_view_roi import getROIView
# from features.image_view_histogram import getHistogramView
# from features.image_view_stretch import getStretchView
# from features.image_view_band import getBandView

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

    def handleItemCollapsed(self, item):
        """ Hide the Band View or Histogram View when their labels are collapsed, but keep them in memory. """
        if item == self.bandViewLabel and self.bandView:
            self.bandView.hide()
        elif item == self.histogramViewLabel and self.histogramView:
            self.histogramView.hide()
        elif item == self.stretchViewLabel and self.stretchView:
            self.stretchView.hide()

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