# standard library
import logging

# third party imports
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMenuBar,
    QMenu,
    QWidget,
    QPushButton,
    QFormLayout,
)

# local imports
import varda

# from varda.plugins.user_plugins.examples import vectroscopy_lite

logger = logging.getLogger(__name__)


class VardaMenuBar(QMenuBar):
    """The primary menubar for varda. Allows dynamic registration of actions to specific menu paths."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def registerAction(self, path: str, action: QAction):
        """Register an action to be added to the main menu."""
        pathElements = path.split("/")
        menu = self
        for item in pathElements:
            # Try to find an existing submenu with this title
            submenu = None
            for child_action in menu.actions():
                sub = child_action.menu()
                if sub and sub.title() == item:
                    submenu = sub
                    break

            # Create submenu if not found
            if submenu is None:
                submenu = menu.addMenu(item)

            # Descend
            menu = submenu

        # Add the final action
        menu.addAction(action)


### OLD: But leaving for now to easily refer later.
class VectroscopyWidget(QWidget):
    """A simple widget for demonstrating a custom user plugin in Varda."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vectroscopy Widget")
        self.setMinimumSize(300, 200)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)

        layout = QFormLayout()
        self.proj = varda.app.proj

        # Add image selection combobox at the top
        if self.proj:
            # Create a label for the image selection
            imageLabel = QtWidgets.QLabel("Select Image:")
            imageLabel.setToolTip("Select the image")

            # Create the combobox
            self.image_combobox = QtWidgets.QComboBox()

            # Get all images from the project
            all_images = self.proj.getAllImages()

            # Populate the combobox with image names
            for i, img in enumerate(all_images):
                name = img.metadata.name or f"Image {i}"
                self.image_combobox.addItem(name, i)  # Store the image index as user data

            # Set the current image as the selected item if it exists
            self.image_combobox.setCurrentIndex(0)

            # Connect the combobox signal to update the selected image
            self.image_combobox.currentIndexChanged.connect(self.updateSelectedImage)
            self.updateSelectedImage()
            # Add the combobox to the layout
            layout.addRow(imageLabel, self.image_combobox)

        self.button = QPushButton("start")
        # self.button.clicked.connect(self.startVectroscopy)
        layout.addRow(self.button)
        self.setLayout(layout)

    def startVectroscopy(self):
        import numpy as np

        array = self.image.raster.filled(np.nan)[:, :, 0]
        threshold = ["95p"]
        crs = self.image.metadata.crs
        transform = self.image.metadata.transform
        name = self.image.metadata.name

        result = vectroscopy_lite.Vectroscopy.from_array(
            array, threshold, crs, transform, name
        )

        print(result)

    def updateSelectedImage(self):
        self.image = self.proj.getImage(self.image_combobox.currentIndex())
