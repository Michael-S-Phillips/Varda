from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys
from customwidgets import *


# When you subclass a Qt class you must always call the super
# __init__ function to allow Qt to set up the object
class TextWidget(BasicWidget):
    def __init__(self, text: str):
        super(TextWidget, self).__init__()
        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(self.label)


class MainWindow(QMainWindow):
    '''
    Creates the main window and layout for the GUI. Each GUI
    component is initialized (we will probably need to turn each
    component into a class attribute that is publicly accessible)
    '''

    def __init__(self):
        super().__init__()

        self.setWindowTitle("SpecLab")

        #self.setFixedSize(QSize(1100, 850))

        # ----------- creating layout for mainWindow ---------
        mainLayout = QHBoxLayout()
        splitter = QSplitter()

        file_explorer = FileExplorer()
        image_manager = TextWidget("Image Manager")

        splitter.addWidget(file_explorer)
        splitter.addWidget(image_manager)

        context_zoom_layout = QHBoxLayout()
        contextImage = TextWidget("contextImage")
        zoomImage = TextWidget("zoomImage")
        context_zoom_layout.addWidget(contextImage)
        context_zoom_layout.addWidget(zoomImage)

        image_viewing_layout = QVBoxLayout()
        menu_options = TextWidget("Menu Options")
        tabs = TextWidget("Tabs")
        image_view = SpectralImageDisplay()

        image_view.setFixedSize(800, 500)
        tabs.setFixedSize(800, 40)
        menu_options.setFixedSize(800, 40)

        image_viewing_layout.addWidget(menu_options)
        image_viewing_layout.addWidget(tabs)
        image_viewing_layout.addWidget(image_view)

        right_panel_layout = QVBoxLayout()
        right_panel_layout.addLayout(image_viewing_layout)
        right_panel_layout.addLayout(context_zoom_layout)

        right_panel_layout.setSpacing(2)
        # left_panel_layout.setSpacing(2)

        mainLayout.addWidget(splitter)
        # mainLayout.addLayout(left_panel_layout)
        mainLayout.addLayout(right_panel_layout)
        mainLayout.setSpacing(2)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        widget = QWidget()
        widget.setLayout(mainLayout)
        self.setCentralWidget(widget)
        # ---------------------------------- 


def startGui():
    # showing main window
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
