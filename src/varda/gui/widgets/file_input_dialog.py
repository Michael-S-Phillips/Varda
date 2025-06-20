from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QHBoxLayout, QVBoxLayout

from varda.gui.widgets import FilePathBox


class FileInputDialog(QDialog):
    """Dialog for requesting a file path from the user."""

    def __init__(
        self, message="Select a file:", defaultPath="", fileFilter=None, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("File Selection")

        # Message label
        self.label = QLabel(message)

        self.fileInput = FilePathBox(defaultPath, fileFilter, parent=self)

        # OK and Cancel buttons
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        # Layouts
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.label)
        main_layout.addWidget(self.fileInput)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    @staticmethod
    def getFilePath(
        message="Select a file:", default_path="", fileFilter=None, parent=None
    ):
        """
        Static method to show the dialog and return the selected file path.

        Args:
            message: The message to display.
            default_path: The default path to show.
            fileFilter: Optional filter for file types.
            parent: Optional parent widget.

        Returns:
            str: The selected file path, or None if canceled.
        """
        dialog = FileInputDialog(message, default_path, fileFilter, parent)
        if dialog.exec():
            return dialog.fileInput.result  # Return the selected path
        return None  # Return None if cancelled
