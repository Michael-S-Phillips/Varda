from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QDockWidget,
    QWidget
)
from PyQt6.QtCore import Qt
import sys

class ControlPanel(QMainWindow):
    """
    ControlPanel appears as a standalone window with expandable/collapsible menus for sub-options.
    """
    def __init__(self, imageIndex, parent=None):
        super(ControlPanel, self).__init__(parent)
        self.imageIndex = imageIndex
        self.setWindowTitle("Control Panel")
        self.resize(400, 300)

        # Create Dock Widget
        self.tabsDock = QDockWidget("Control Panel", self)

        # Main Widget and Layout for Dock Widget
        dock_widget_content = QWidget()
        main_layout = QVBoxLayout()

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

        # Add Tree Widget to Layout
        main_layout.addWidget(self.treeWidget)
        dock_widget_content.setLayout(main_layout)

        # Set Dock Widget Content
        self.tabsDock.setWidget(dock_widget_content)

    def handle_item_click(self, item, column):
        """Handle clicks on tree widget items."""
        if item.text(0) == "ROI":
            self.handle_draw_roi()
        elif item.text(0) == "Pixel Plot":
            self.handle_pixel_plot()
        elif item.text(0) == "Settings":
            print("Settings clicked")

    def handle_draw_roi(self):
        """Handle the Draw ROI action."""
        print(f"Drawing ROI for image index {self.imageIndex}")

    def handle_pixel_plot(self):
        """Handle the Show Pixel Plot action."""
        print(f"Showing pixel plot for image index {self.imageIndex}")

# Example usage
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ControlPanel(imageIndex=1)
    window.show()
    sys.exit(app.exec())
