from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

"""
Since We can do the style.qss file, We might not actually need this wrapper class? 
But I'll leave it for now.
"""
class BasicWidget(QWidget):
    """
    A wrapper class for a widget. If we want to apply a consistent style
    to each widget in the layout, we can use this when creating a new one.
    """

    def __init__(self):
        super(BasicWidget, self).__init__()

        #self.setStyleSheet("border: 3px solid; fill: black")
        # sets background color to gray as default
        self.setAutoFillBackground(True)
        #
        # palette = self.palette()
        # palette.setColor(QPalette.ColorRole.Window, QColor("gray"))
        # self.setPalette(palette)
