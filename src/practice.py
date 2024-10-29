import sys
import numpy as np
import pyqtgraph as pg
from pyqtgraph import ImageView, PolyLineROI
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtGui import QPolygonF

class PolylineROIExample(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Create an ImageView widget to display the image
        self.image_view = ImageView(self)
        self.setCentralWidget(self.image_view)
        
        # Load a sample image into the ImageView
        image_data = np.random.rand(200, 200) * 255  # 200x200 grayscale image
        self.image_view.setImage(image_data)

        # Create a PolyLine ROI with multiple vertices
        self.roi = PolyLineROI([ [30, 30], [100, 40], [120, 120], [40, 100] ], closed=True, pen='r')
        self.image_view.addItem(self.roi)

        # Check if the ROI is inside the image and convert to numpy array
        if self.is_roi_fully_inside_image():
            roi_array = self.extract_roi_as_array()
            print("ROI as numpy array:\n", roi_array)
        else:
            print("ROI is not fully inside the image.")

    def is_roi_fully_inside_image(self):
        """Check if all vertices of the PolyLineROI are inside the image bounds."""
        # Get image dimensions
        img_width, img_height = self.image_view.image.shape[1], self.image_view.image.shape[0]
        
        # Get the ROI's vertices
        for vertex in self.roi.getLocalHandlePositions():
            pos = vertex[1]  # Position of each vertex
            x, y = pos.x(), pos.y()

            # Check if each vertex is within image bounds
            if not (0 <= x < img_width and 0 <= y < img_height):
                return False  # If any vertex is outside the image bounds

        return True  # All vertices are inside

    def extract_roi_as_array(self):
        """Extracts the polyline ROI area from the image as a numpy array using a mask."""
        # Create a polygon mask based on ROI vertices
        vertices = self.roi.getLocalHandlePositions()
        polygon = QPolygonF([v[1] for v in vertices])

        # Create an empty mask
        mask = np.zeros(self.image_view.image.shape, dtype=bool)

        # Use QPainterPath to define the region inside the polygon and set mask pixels
        painter_path = pg.QtGui.QPainterPath()
        painter_path.addPolygon(polygon)
        for y in range(mask.shape[0]):
            for x in range(mask.shape[1]):
                if painter_path.contains(pg.QtCore.QPointF(x, y)):
                    mask[y, x] = True

        # Apply mask to the image
        roi_array = np.where(mask, self.image_view.image, 0)

        return roi_array

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PolylineROIExample()
    window.show()
    sys.exit(app.exec())






