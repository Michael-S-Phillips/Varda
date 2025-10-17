from PyQt6.QtWidgets import QComboBox, QLabel


class ImageSelectionBox(QComboBox):
    def __init__(self, images, parent=None):
        super().__init__(parent)
        # Create a label for the image selection
        imageLabel = QLabel("Select Image:")
        imageLabel.setToolTip("Select the image")

        # Populate the combobox with image names
        for i, img in enumerate(images):
            name = img.metadata.name or f"Image {i}"
            self.addItem(name, i)  # Store the image index as user data
