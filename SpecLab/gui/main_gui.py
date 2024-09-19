from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys
from gui.customwidgets import *


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

        fileExplorer = FileExplorer()
        imageManager = TextWidget("Image Manager")

        splitter.addWidget(fileExplorer)
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

        imageView = SpectralImageDisplay()
        #imageView.setFixedSize(800, 500)
        fullImageWidget = QSplitter(Qt.Orientation.Vertical)
        fullImageWidget.addWidget(imageView)
        fullImageWidget.addWidget(contextZoomSplitter)

        imageViewingLayout.addWidget(fullImageWidget)

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


def startGui():
    # showing main window
    app = QApplication(sys.argv)
    with open("resources/style.qss", "r") as styling:
        app.setStyleSheet(styling.read())
    window = MainWindow()
    window.showMaximized()
    app.exec()
