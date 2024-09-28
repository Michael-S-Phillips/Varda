from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys
from gui.customwidgets import *
from pathlib import Path

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
# When you subclass a Qt class you must always call the super
# __init__ function to allow Qt to set up the object



class MainWindow(QMainWindow):
    '''
    Creates the main window and layout for the GUI. Each GUI
    component is initialized (we will probably need to turn each
    component into a class attribute that is publicly accessible)
    '''

    def __init__(self):
        super().__init__()

        self.setWindowTitle("SpecLab")

        # self.setFixedSize(QSize(1100, 850))

        # ----------- creating layout for mainWindow ---------
        mainLayout = QHBoxLayout()
        splitter = QSplitter()

        self.fileExplorer = FileExplorer()
        imageManager = TextWidget("Image Manager")

        splitter.addWidget(self.fileExplorer)
        splitter.addWidget(imageManager)

        # Context Zoom Setup
        contextZoomLayout = QHBoxLayout()
        contextZoomSplitter = QSplitter()
        contextImage = TextWidget("contextImage")
        zoomImage = TextWidget("zoomImage")

        contextZoomSplitter.addWidget(contextImage)
        contextZoomSplitter.addWidget(zoomImage)

        contextZoomLayout.addWidget(contextZoomSplitter)

        imageViewingLayout = QVBoxLayout()

        # only spectral image display and spectral data viewer talk?
        # when button is clicked to open file, send message to spectralImgDis
        # thru the main gui to create a spectral data viewer object

        self.imageView = SpectralImageDisplay(mainLayout)
        #imageView.setFixedSize(800, 500)
        self.fullImageWidget = QSplitter(Qt.Orientation.Vertical)
        self.fullImageWidget.addWidget(self.imageView)
        self.fullImageWidget.addWidget(contextZoomSplitter)

        imageViewingLayout.addWidget(self.fullImageWidget)

        menuOptions = TextWidget("Menu Options")
        tabs = TextWidget("Tabs")
        tabs.setFixedSize(800, 40)
        menuOptions.setFixedSize(800, 40)
        menuLayout = QVBoxLayout()
        menuLayout.addWidget(menuOptions)
        menuLayout.addWidget(tabs)

        rightPanelLayout = QVBoxLayout()
        rightPanelLayout.addLayout(menuLayout)
        rightPanelLayout.addLayout(imageViewingLayout)

        #rightPanelLayout.addLayout(fullImageWidget)

        #rightPanelLayout.addLayout(contextZoomLayout)

        rightPanelLayout.setSpacing(2)
        # left_panel_layout.setSpacing(2)

        mainLayout.addWidget(splitter)
        # mainLayout.addLayout(left_panel_layout)
        mainLayout.addLayout(rightPanelLayout)
        mainLayout.setSpacing(2)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        widget = QWidget()
        widget.setLayout(mainLayout)
        self.setCentralWidget(widget)

        # ---------------------------------- 
        self.add_image(str(Path("./testImages/CRISM/frt00012dfa_07_if164j_mtr3.hdr")))

    def add_image(self, filePath):
        print("here")
        self.imageView.createPlt(filePath)




def startGui():
    # showing main window
    app = QApplication(sys.argv)
    with open(str(Path("./resources/style.qss")), "r") as styling:
        app.setStyleSheet(styling.read())
    window = MainWindow()
    window.showMaximized()

    app.exec()
