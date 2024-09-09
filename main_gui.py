from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys

# When you subclass a Qt class you must always call the super 
# __init__ function to allow Qt to set up the object.

class BasicWidget(QWidget):
    '''
    A wrapper class for a widget. If we want to apply a consistent style
    to each widget in the layout, we can use this when creating a new one.
    '''
    def __init__(self):
        super(BasicWidget, self).__init__()
        # self.setStyleSheet("border: 2px solid; fill: gray")

        # sets background color to gray as default
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("gray"))
        self.setPalette(palette)



class MainWindow(QMainWindow):
    '''
    Creates the main window and layout for the GUI. Each GUI
    component is initialized (we will probably need to turn each
    component into a class attribute that is publicly accessible)
    '''
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpecLab")

        self.setFixedSize(QSize(1100, 850))

        # ----------- creating layout for mainWindow ---------
        mainLayout = QHBoxLayout()

        left_panel_layout = QVBoxLayout()
        file_explorer = BasicWidget()
        image_manager = BasicWidget()
        left_panel_layout.addWidget(file_explorer)
        left_panel_layout.addWidget(image_manager)

        context_zoom_layout = QHBoxLayout()
        context_image = BasicWidget()
        zoom_image = BasicWidget()
        context_zoom_layout.addWidget(context_image)
        context_zoom_layout.addWidget(zoom_image)

        image_viewing_layout = QVBoxLayout()
        menu_options = BasicWidget()
        tabs = BasicWidget()
        image_view = BasicWidget()

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
        left_panel_layout.setSpacing(2)
  
        mainLayout.addLayout(left_panel_layout)
        mainLayout.addLayout(right_panel_layout)
        mainLayout.setSpacing(2)
        mainLayout.setContentsMargins(0,0,0,0)

        widget = QWidget()
        widget.setLayout(mainLayout)
        self.setCentralWidget(widget)
        # ---------------------------------- 

        # creating attributes for class 
        self.main_layout = mainLayout

        self.file_explorer = file_explorer
        self.image_manager = image_manager
        self.context_image = context_image
        self.zoom_image = zoom_image
        self.menu_options = menu_options
        self.tabs = tabs
        self.image_view = image_view
        

# showing main window
app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()

