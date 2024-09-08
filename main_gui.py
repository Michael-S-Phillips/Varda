from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
import sys

#When you subclass a Qt class you must always call the super 
# __init__ function to allow Qt to set up the object.

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SpecLab")

        self.setFixedSize(QSize(1000, 750))


app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()

