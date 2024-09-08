from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys

#When you subclass a Qt class you must always call the super 
# __init__ function to allow Qt to set up the object.

class BasicWidget(QWidget):

    def __init__(self):
        super(BasicWidget, self).__init__()
        # self.setStyleSheet("border: 2px solid; fill: gray")
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("gray"))
        self.setPalette(palette)



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SpecLab")

        self.setFixedSize(QSize(1100, 850))

        mainLayout = QHBoxLayout()

        left_panel_layout = QVBoxLayout()
        file_explorer = BasicWidget()
        image_manager = BasicWidget()
        left_panel_layout.addWidget(file_explorer)
        left_panel_layout.addWidget(image_manager)

        context_zoom_layout = QHBoxLayout()
        contextImage = BasicWidget()
        zoomImage = BasicWidget()
        context_zoom_layout.addWidget(contextImage)
        context_zoom_layout.addWidget(zoomImage)

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
        


app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()

