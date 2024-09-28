"""
specimagedisplay.py
"""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from . import BasicWidget
import numpy as np
import qimage2ndarray
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import *
from gui.SpectralDataViewer import SpectralDataViewer
import matplotlib
matplotlib.use('QtAgg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

class SpectralImageDisplay(FigureCanvasQTAgg):
    def __init__(self, parent):
        super(SpectralImageDisplay, self).__init__()
        self.label = QLabel(self)
        self.figure, self.ax = plt.subplots(figsize=(6, 6))
        self.canvas = FigureCanvasQTAgg(self.figure)

        self.vertices = [] 

    def setImage(self, img: np.ndarray):
        self.label.clear()
        self.label.setPixmap(QPixmap(qimage2ndarray.array2qimage(img, normalize=(0, 1))))

    def onclick(self, event):
        # Right-click to finish drawing the polygon
        if event.button == 3:
            self.finish_ROI()
            return

        # Add vertex if left mouse button is clicked
        if event.inaxes is not None and self.is_drawingROI:
            self.vertices.append((event.xdata, event.ydata))
            self.draw_ROI()

    def draw_ROI(self): 
        self.ax.set_aspect('equal', adjustable='box')

        self.ax.imshow(self.current_image)
        
        if self.vertices:
            x, y = zip(*self.vertices)
            self.ax.fill(x + (x[0],), y + (y[0],), alpha=0.5, edgecolor='black')

        self.draw()

    def finish_ROI(self):
        self.draw()

    def ROIclicked(self):
        if (self.is_drawingROI):
            self.is_drawingROI = False
        else:
            self.is_drawingROI = True

    def zoomClicked(self):
        if (self.is_drawingROI):
            self.is_drawingROI = False
        else:
            self.is_drawingROI = True

    def on_click(self, event):
        if self.zoomButton.isChecked():
            if event.button == 1:  # Left click for zoom in
                self.zoom(1.2)
            elif event.button == 3:  # Right click for zoom out
                self.zoom(1 / 1.2)

    def zoom(self, factor):
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        # Calculate new limits
        new_xlim = [(x - (xlim[1] - xlim[0]) / 2 * (1 - factor)) for x in xlim]
        new_ylim = [(y - (ylim[1] - ylim[0]) / 2 * (1 - factor)) for y in ylim]

        # Set new limits
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        self.draw()

    def setZoomActionEvents(self):
        # self.setFocusPolicy(Qt.ClickFocus)
        self.mpl_connect('button_press_event', self.on_click)

        self.zoomButton = QPushButton("Zoom in", self)
        self.zoomButton.setStyleSheet('background-color: grey; padding: 5px; margin-left: 80px')
        self.zoomButton.clicked.connect(self.zoomClicked)

        self.ROIbutton = QPushButton("Select ROI", self)
        self.ROIbutton.setStyleSheet('background-color: grey; padding: 5px')
        self.ROIbutton.clicked.connect(self.ROIclicked)
        # Connect the mouse click event to the onclick method
        self.cid = self.figure.canvas.mpl_connect("button_press_event", self.onclick)

    def createPlt(self, fileName):
        print('Creating plt...')
        self.is_drawingROI = False
        self.setZoomActionEvents()
        sdv = SpectralDataViewer(fileName)
        self.current_image = np.array(sdv.image)
        
        # Display the image
        self.ax.imshow(self.current_image)
        # Set fixed limits based on the image dimensions
        self.ax.set_xlim(0, self.current_image.shape[1])
        self.ax.set_ylim(self.current_image.shape[0], 0)  # Invert y-axis
        
        self.draw()  # Refresh the plot


# drawing the ROI on the zoom image?
# what format should spectralZoomImage take in?
# adobe photo shop organic image and also polygon 

# context: slight zoomed in version of the main image window
# zoom: will move around based on where we are in the image window (super zoomed in)
# ROI: statisics of ROI associated (plot *avg spectrum std histogram, wavelength array*)
    # option to add columns and also custom functions
    # perhaps a toggle button for ROI in context window
    # option to select a given ROI




class SpectralZoomImage(SpectralImageDisplay):
    def __init__(self, parent):
        super(SpectralZoomImage, self).__init__(parent)

class SpectralContextImage(SpectralImageDisplay):
    def __init__(self, parent):
        super(SpectralZoomImage, self).__init__(parent)







    



