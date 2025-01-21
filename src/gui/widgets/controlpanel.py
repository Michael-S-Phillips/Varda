from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QDockWidget,
    QLabel,  # Add this import
    QWidget
)

from PyQt6.QtCore import Qt
import pyqtgraph as pg
import sys

# local imports
from core.data.project_context import ProjectContext
from gui.widgets.ROIselector import ROISelector
from core.entities import FreeHandROI


class ControlPanel(QMainWindow):
    """
    ControlPanel appears as a standalone window with expandable/collapsible menus for sub-options.
    """
    def __init__(self, project_context: ProjectContext, parent=None):
        super(ControlPanel, self).__init__(parent)
        self.project_context = project_context
        self.imageIndex = None
        self.setWindowTitle("Control Panel")
        self.roiSelector = None


        self.setWindowTitle("Control Panel")
        self.resize(400, 300)

        # Add graphics view to layout

        # Create Dock Widget
        self.tabsDock = QDockWidget("Control Panel", self)

        # Main Widget and Layout for Dock Widget
        self.dock_widget_content = QWidget()
        self.main_layout = QVBoxLayout()


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
        self.main_layout.addWidget(self.activeImageLabel)
        self.main_layout.addWidget(self.treeWidget)
        self.dock_widget_content.setLayout(self.main_layout)

        # Set Dock Widget Content
        self.tabsDock.setWidget(self.dock_widget_content)

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
        if self.imageIndex is None:
            print("No active image selected.")
            return

        # Access the current image
        current_image = self.project_context.getImage(self.imageIndex)

        # Initialize or update ROI Selector
        if self.roiSelector is None:
            self.roiSelector = ROISelector()

        # add to the raster view the roi functionalty (roiExperiment): done 
        # make a similar roi view model that will save roi data that was drawn on 
        # the main raster view
        # roi view folder needs:
        #   - __init__.py: initializes import: done
        #   - roi_view.py: a widget for viewing ROIs (QWidget): done
        #   - roi_viewmodel.py: will handle the logic and interaction with the project context: set up
        #       - the raster view will send the created ROI to the project context: done
        #       - the project context will send a signal that a new ROI has been created: done
        #       - the roi_view will update the table with the new ROI added: done
        #   - image_view_roi.py: returns/updates an instance of roi_view: done
        # create option to open an roiWindow from the mainGUI: done
        # saving the roi is done with saveROI in the project context: done

        # move button to draw roi to the roi table
        
        # to do: add multiple ROIs at a time (each one a different color)
        # transform into ROI pyqt object to get mean spectrum data
        # add buttons to table to do so

        else:
            self.roiSelector.raster = current_image.raster  # Update raster

        # Add image and ROI selector to the scene
        self.roiSelector.addToScene(self.graphicsScene)

        # Prompt the user to draw the ROI
        self.roiSelector.draw()
        print("Start drawing ROI...")

        # After drawing, retrieve the points
        roi_points = self.roiSelector.getLinePts()
        if roi_points is None:
            print("No ROI drawn.")
            return

        # Convert points to FreeHandROI
        new_roi = FreeHandROI(points=roi_points)

        # Add ROI to the current image in the project context
        roi_index = self.project_context.addROI(self.imageIndex, new_roi)
        print(f"ROI added at index {roi_index} with points: {roi_points}")

    def handle_pixel_plot(self):
        """Handle the Show Pixel Plot action."""
        if self.imageIndex is not None:
            print(f"Showing pixel plot for image index {self.imageIndex}")
        else:
            print("No active image selected.")

    def updateActiveImage(self, index):
        """Update the active image index and label based on the selected image."""
        self.imageIndex = index
        if index is None:
            self.activeImageLabel.setText("No image selected")
        else:
            # Dynamically generate the name if it wasn't explicitly set
            image_name = f"Image {index}" if not hasattr(self.project_context.getImage(index).metadata,
                                                         "name") else self.project_context.getImage(index).metadata.name
            self.activeImageLabel.setText(f"Active Image: {image_name}")


# Example usage
if __name__ == "__main__":
    app = QApplication(sys.argv)
    project_context = ProjectContext()  # Replace with actual initialization
    window = ControlPanel(project_context)
    window.show()
    sys.exit(app.exec())
