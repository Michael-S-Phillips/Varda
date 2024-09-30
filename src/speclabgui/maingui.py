from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from speclabgui.customwidgets import *
# don't know why this must be explicit
from speclabgui.customwidgets.spectralimagedisplay import SpectralZoomImage
from pathlib import Path
import sys
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

'''
"FYI": maingui.py will initialize window and layout.
It will only interact with widget classes (in customwidgets) to maintain
low cohesion. Widget classes will interact with processing / 
visualization classes accordingly. 
'''


class MainGui(QMainWindow):
    """
    Creates the main window and layout for the GUI. Each GUI
    component is initialized (we will probably need to turn each
    component into a class attribute that is publicly accessible)
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpecLab")

        # ----------- creating layout for mainWindow ---------
        mainLayout = QHBoxLayout()
        splitter = QSplitter()

        self.fileExplorer = FileExplorer()
        imageManager = TextWidget("Image Manager")
        self.imageView = SpectralImageDisplay(mainLayout)

        splitter.addWidget(self.fileExplorer)
        splitter.addWidget(imageManager)

        splitter.setStretchFactor(0, 10)
        splitter.setStretchFactor(1, 13)

        # Context Zoom Setup
        contextZoomLayout = QHBoxLayout()
        contextZoomSplitter = QSplitter()
        self.contextImage = SpectralZoomImage(mainLayout)
        self.zoomImage = SpectralZoomImage(mainLayout)

        contextZoomSplitter.addWidget(self.contextImage)
        contextZoomSplitter.addWidget(self.zoomImage)

        contextZoomLayout.addWidget(contextZoomSplitter)

        imageViewingLayout = QVBoxLayout()

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

        rightPanelLayout.setSpacing(2)
        imageWidget = QWidget()
        imageWidget.setLayout(rightPanelLayout)
        splitter.addWidget(imageWidget)
        splitter.setStretchFactor(2, 10)

        mainLayout.addWidget(splitter)
        mainLayout.setSpacing(2)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        widget = QWidget()
        widget.setLayout(mainLayout)
        self.setCentralWidget(splitter)

        # ----------------------------------
        self.add_image(str(Path("./testImages/HySpex/220724_VNIR_Reflectance.hdr")))

    def add_image(self, filePath):
        self.imageView.createPlt(filePath)


def startGui():
    # showing main window
    app = QApplication(sys.argv)
    with open(str(Path("./resources/style.qss")), "r") as styling:
        app.setStyleSheet(styling.read())
    window = MainGui()
    window.showMaximized()

    app.exec()
