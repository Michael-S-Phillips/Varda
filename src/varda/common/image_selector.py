from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QComboBox



class ImageSelector(QWidget):
    def __init__(self, images, parent=None):
        super().__init__(parent)
        self.images = images

        # Create and setup list widget
        self.selector = QComboBox()
        self.image_list = QListWidget()

        # Setup layout
        layout = QVBoxLayout()
        layout.addWidget(self.image_list)
        self.setLayout(layout)

        # Populate the list
        self.populate_image_list()

    def populate_image_list(self):
        """Populate the list widget with image names from the project"""
        for index, image in enumerate(self.images.getAll()):
            self.selector.addItem(image.metadata.name, index)

    def get_selected_image(self):
        """Return the currently selected image or None if nothing is selected"""
        current_item = self.image_list.currentItem()
        if current_item:
            return current_item.data(1)
        return None
