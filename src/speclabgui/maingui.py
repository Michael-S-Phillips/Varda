from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from speclabgui.customwidgets import SpectralImageWorkspace, FileExplorer, TextWidget
from pathlib import Path
import sys

'''
"FYI": maingui.py will initialize window and layout.
It will only interact with widget classes (in customwidgets) to maintain
low cohesion. Widget classes will interact with processing / 
visualization classes accordingly. 
'''


class MainGui(QtWidgets.QMainWindow):
    """
    Creates the main window and layout for the GUI. Each GUI
    component is initialized (we will probably need to turn each
    component into a class attribute that is publicly accessible)
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpecLab")
        # set configs
        pg.setConfigOptions(imageAxisOrder='row-major')
        # ----------- creating layout for mainWindow ---------
        mainLayout = QtWidgets.QHBoxLayout()
        splitter = QtWidgets.QSplitter()

        self.fileExplorer = FileExplorer()
        imageManager = TextWidget("Image Manager")

        splitter.addWidget(self.fileExplorer)
        splitter.addWidget(imageManager)

        splitter.setStretchFactor(0, 10)
        splitter.setStretchFactor(1, 13)

        menuOptions = TextWidget("Menu Options")
        tabs = TextWidget("Tabs")
        tabs.setFixedSize(800, 40)
        menuOptions.setFixedSize(800, 40)
        menuLayout = QtWidgets.QVBoxLayout()
        menuLayout.addWidget(menuOptions)
        menuLayout.addWidget(tabs)

        self.imageView = SpectralImageWorkspace(self)

        rightPanelLayout = QtWidgets.QVBoxLayout()
        rightPanelLayout.addLayout(menuLayout)
        rightPanelLayout.addWidget(self.imageView)

        rightPanelLayout.setSpacing(2)
        imageWidget = QtWidgets.QWidget()
        imageWidget.setLayout(rightPanelLayout)
        splitter.addWidget(imageWidget)
        splitter.setStretchFactor(2, 10)

        mainLayout.addWidget(splitter)
        mainLayout.setSpacing(2)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        widget = QtWidgets.QWidget()
        widget.setLayout(mainLayout)
        self.setCentralWidget(splitter)

        # ----------------------------------
        # self.add_image(str(Path("./testImages/HySpex/220724_VNIR_Reflectance.hdr")))

    def add_image(self, filePath):
        self.imageView.loadNewImage(filePath)


def startGui():
    # showing main window
    app = QtWidgets.QApplication(sys.argv)
    with open(str(Path("./resources/style.qss")), "r") as styling:
        app.setStyleSheet(styling.read())
    window = MainGui()
    window.showMaximized()
    window.show()
    app.exec()
