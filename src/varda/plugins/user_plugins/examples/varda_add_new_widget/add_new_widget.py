import logging

from PyQt6.QtWidgets import QWidget, QPushButton, QLabel

import varda

logger = logging.getLogger(__name__)


@varda.api.hookimpl
def onLoad():
    """Hook called on plugin load."""
    logger.info("Plugin hook implementation called: varda_add_new_widget :O")
    varda.api.registerWidget(MyNewWidget)


class MyNewWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        self.setWindowTitle("My New Widget")
        self.label = QLabel(self)
        button = QPushButton("Click Me", self)
        button.clicked.connect(self.onButtonClick)

    def onButtonClick(self):
        """Handle button click event."""
        self.label.setText("Hello World!")

    def onActivate(self):
        """Called when the widget is activated."""
        logger.info("MyNewWidget activated!")
