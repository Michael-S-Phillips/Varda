# standard library
import logging

import numpy as np

# third party imports
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QAction
from PyQt6.QtWidgets import (
    QMenuBar,
    QMenu,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QFormLayout,
)

# local imports
import varda
from varda.user_plugins.examples import vectroscopy_lite

logger = logging.getLogger(__name__)


class MainMenuBar(QMenuBar):
    """Menubar widget. This is mainly to move all the code constructing the menubar
    to its own class, to keep mainGUI clean.
    """

    sigSaveProject = QtCore.pyqtSignal()
    sigSaveProjectAs = QtCore.pyqtSignal()
    sigOpenProject = QtCore.pyqtSignal()
    sigOpenProcessingMenu = QtCore.pyqtSignal()
    sigImportFile = QtCore.pyqtSignal()
    sigExitApp = QtCore.pyqtSignal()
    sigAboutDialog = QtCore.pyqtSignal()
    sigLoadDebugProject = QtCore.pyqtSignal()
    sigDumpProjectData = QtCore.pyqtSignal()

    # NEW DUAL IMAGE SIGNALS
    sigOpenDualImageView = QtCore.pyqtSignal()
    sigLinkSelectedImages = QtCore.pyqtSignal()
    sigUnlinkSelectedImages = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initUI()

    def _initUI(self):
        self._initFileMenu()
        self._initViewMenu()  # NEW: Add View menu
        self._initHelpmenu()
        self._initDebugMenu()
        self._initProcessMenu()

        self._initPluginMenu()

    # Note: adding "self" as the parent of the QMenu is important, to keep it from
    # being garbage collected immediately
    def _initFileMenu(self):
        fileMenu = QMenu("File", self)

        importMenu = QMenu("Import", self)
        importMenu.addAction("Import Image", QKeySequence("Ctrl+N"), self.sigImportFile)
        fileMenu.addMenu(importMenu)

        fileMenu.addAction("Open...", QKeySequence("Ctrl+O"), self.sigOpenProject)
        # fileMenu.addMenu(self._initOpenRecentMenu())
        fileMenu.addAction("Save", QKeySequence("Ctrl+S"), self.sigSaveProject)
        # fileMenu.addAction("Save As..", self.sigSaveProjectAs)
        fileMenu.addAction("Exit", self.sigExitApp)
        self.addMenu(fileMenu)
        return fileMenu

    # NEW VIEW MENU FOR DUAL IMAGE FUNCTIONALITY
    def _initViewMenu(self):
        viewMenu = QMenu("View", self)

        # Dual Image submenu
        dualImageMenu = QMenu("Dual Image", self)
        dualImageMenu.addAction(
            "Open Dual View...", QKeySequence("Ctrl+D"), self.sigOpenDualImageView
        )
        dualImageMenu.addSeparator()
        dualImageMenu.addAction(
            "Link Selected Images", QKeySequence("Ctrl+L"), self.sigLinkSelectedImages
        )
        dualImageMenu.addAction(
            "Unlink Selected Images",
            QKeySequence("Ctrl+U"),
            self.sigUnlinkSelectedImages,
        )

        viewMenu.addMenu(dualImageMenu)

        self.addMenu(viewMenu)

    def _initHelpmenu(self):
        helpMenu = QMenu("Help", self)
        helpMenu.addAction("About", self.sigAboutDialog)
        self.addMenu(helpMenu)

    def _initDebugMenu(self):
        debugMenu = QMenu("Debug", self)
        debugMenu.addAction(
            "Load Debug Project", QKeySequence("F10"), self.sigLoadDebugProject
        )
        debugMenu.addAction(
            "Project Data Dump", QKeySequence("F12"), self.sigDumpProjectData
        )
        self.addMenu(debugMenu)

    def _initProcessMenu(self):
        # Import the image process menu system
        from varda.gui.widgets.image_process_menu import MainMenuBarExtension

        # Use the extension to add the process menu
        processMenu = MainMenuBarExtension.addProcessMenuToMainMenuBar(self)

        # Add the legacy action for backward compatibility
        processMenu.addSeparator()
        processMenu.addAction("Legacy Image Processing...", self.sigOpenProcessingMenu)

    def _initPluginMenu(self):
        # Get all plugin menus from the registry
        pluginMenu = QMenu("Plugins", self)

        pluginWidgets = varda.app.registry.widgets
        for name, widgetClass in pluginWidgets:
            logger.debug(f"Adding widget {name}, class {widgetClass}")
            action = QAction(name, self)
            action.triggered.connect(lambda: self.openWidget(widgetClass))
            pluginMenu.addAction(action)
            logger.debug(f"Added plugin menu item: {name}")

        action = QAction("Vectroscopy Widget", self)
        action.triggered.connect(lambda: self.openWidget(VectroscopyWidget))
        pluginMenu.addAction(action)
        self.addMenu(pluginMenu)

    def openWidget(self, widgetClass):
        """Open a widget in the main window."""
        logger.debug(f"Opening widget {widgetClass}")
        widget = widgetClass(self.parent())
        widget.show()

    def registerAction(self, path: str, action):
        """Register an action to be added to the main menu."""
        pathElements = path.split("/")
        menu = self
        for item in pathElements[:-1]:
            notFound = True
            for child in menu.actions():
                if child.text() == item:
                    menu = child.menu()
                    notFound = False
                    break
            if notFound:
                menu = menu.addMenu(item)

        menu.addAction(action)


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
                self.image_combobox.addItem(
                    name, i
                )  # Store the image index as user data

            # Set the current image as the selected item if it exists
            self.image_combobox.setCurrentIndex(0)

            # Connect the combobox signal to update the selected image
            self.image_combobox.currentIndexChanged.connect(self.updateSelectedImage)
            self.updateSelectedImage()
            # Add the combobox to the layout
            layout.addRow(imageLabel, self.image_combobox)

        self.button = QPushButton("start")
        self.button.clicked.connect(self.startVectroscopy)
        layout.addRow(self.button)
        self.setLayout(layout)

    def startVectroscopy(self):
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
