from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QDockWidget,
    QLabel,
    QWidget
)
from PyQt6.QtCore import Qt
import sys
from features.image_view_raster.PixelPlotWindow import PixelPlotWindow

# Local imports
from core.data.project_context import ProjectContext
from features.image_view_raster.raster_view import RasterView
from features.image_view_raster.raster_viewmodel import RasterViewModel


class ControlPanel(QMainWindow):
    """
    ControlPanel appears as a standalone window with expandable/collapsible menus for sub-options.
    """
    def __init__(self, project_context: ProjectContext, parent=None):
        super(ControlPanel, self).__init__(parent)
        self.project_context = project_context
        self.imageIndex = None
        self.rasterView = None  # Keep the RasterView instance alive
        self.setWindowTitle("Control Panel")
        self.resize(400, 300)

        # Create Dock Widget
        self.tabsDock = QDockWidget("Control Panel", self)

        # Main Widget and Layout for Dock Widget
        dock_widget_content = QWidget()
        main_layout = QVBoxLayout()

        # Active Image Label
        self.activeImageLabel = QLabel("No image selected")
        self.activeImageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activeImageLabel.setStyleSheet("font-size: 14px; font-weight: bold;")

        # Create Tree Widget for Expandable/Collapsible Options
        self.treeWidget = QTreeWidget()
        self.treeWidget.setHeaderLabel("Control Options")

        # Add Main Categories and Sub-options
        image_tools_item = QTreeWidgetItem(self.treeWidget)
        image_tools_item.setText(0, "Image Tools")

        roi_item = QTreeWidgetItem(image_tools_item)
        roi_item.setText(0, "ROI")
        roi_item.setToolTip(0, "Draw Region of Interest")

        pixel_plot_item = QTreeWidgetItem(image_tools_item)
        pixel_plot_item.setText(0, "Pixel Plot")
        pixel_plot_item.setToolTip(0, "Show Pixel Plot")

        settings_item = QTreeWidgetItem(self.treeWidget)
        settings_item.setText(0, "Settings")

        # Connect TreeWidget Item Clicks
        self.treeWidget.itemClicked.connect(self.handle_item_click)

        # Add widgets to the layout
        main_layout.addWidget(self.activeImageLabel)
        main_layout.addWidget(self.treeWidget)
        dock_widget_content.setLayout(main_layout)

        # Set Dock Widget Content
        self.tabsDock.setWidget(dock_widget_content)

    def handle_item_click(self, item, column):
        """
        Handle clicks on tree widget items.
        """
        if item.text(0) == "ROI":
            self.handle_draw_roi()
        elif item.text(0) == "Pixel Plot":
            self.handle_pixel_plot()
        elif item.text(0) == "Settings":
            print("Settings clicked")

    def handle_draw_roi(self):
        """
        Handle the Draw ROI action.
        """
        if self.imageIndex is not None:
            print(f"Drawing ROI for image index {self.imageIndex}")
        else:
            print("No active image selected for ROI.")

    def handle_pixel_plot(self):
        """Handle the Show Pixel Plot action."""
        if self.imageIndex is not None:
            image = self.project_context.getImage(self.imageIndex)

            # Retrieve raster data and wavelength
            raster_data = image.raster
            wavelength = getattr(image.metadata, "wavelength", None)

            # Create and show the Pixel Plot Window
            self.pixelPlotWindow = PixelPlotWindow(raster_data, wavelength)
            self.pixelPlotWindow.show()
        else:
            print("No active image selected.")

    def updateActiveImage(self, index):
        """
        Update the active image index and label.
        """
        self.imageIndex = index
        if index is None:
            self.activeImageLabel.setText("No image selected")
        else:
            # Use the image index for the label
            self.activeImageLabel.setText(f"Active Image: Image {index}")


# Example usage
if __name__ == "__main__":
    app = QApplication(sys.argv)
    project_context = ProjectContext()  # Replace with actual initialization
    window = ControlPanel(project_context)
    window.show()
    sys.exit(app.exec())
