from PyQt6.QtWidgets import QWidget, QComboBox, QVBoxLayout


class BandSelector(QWidget):
    def __init__(self, proj, imageIndex):
        super().__init__()
        self.proj = proj
        self.imageID = imageIndex

        # Create the combobox
        self.bandComboBox = QComboBox()

        # Populate it based on the project context
        self.populateComboBox()

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.bandComboBox)
        self.setLayout(layout)

    def populateComboBox(self):
        image = self.proj.getImage(self.imageID)
        self.bandComboBox.addItems([band.name for band in image.band])


class StretchSelector(QWidget):
    def __init__(self, proj, imageIndex):
        super().__init__()
        self.proj = proj
        self.imageID = imageIndex

        # Create the combobox
        self.stretchComboBox = QComboBox()

        # Populate it based on the project context
        self.populateComboBox()

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.stretchComboBox)
        self.setLayout(layout)

    def populateComboBox(self):
        image = self.proj.getImage(self.imageID)
        self.stretchComboBox.addItems([stretch.name for stretch in image.stretch])
