"""Dialog utilities for varda_rewrite.

This module provides utility functions and classes for creating and managing dialog boxes.
It simplifies the process of creating file dialogs, message boxes, progress dialogs, and option dialogs.
"""

from typing import Optional, List, Tuple, Callable, Dict, Any, Union
from pathlib import Path
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QProgressDialog,
    QApplication,
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QHBoxLayout,
)


# TODO: This doesnt need to be contained within a class
class DialogUtils:
    """Utility class for creating and managing dialog boxes.

    This class provides methods for creating file dialogs, message boxes,
    progress dialogs, and option dialogs. It simplifies the process of
    creating and using dialog boxes in PyQt6 applications.
    """

    @staticmethod
    def requestFilePath(
        title: str = "Open File", directory: str = "", filter: str = "", parent=None
    ) -> Optional[str]:
        """Opens a file dialog to request a file path from the user.

        Args:
            title: The title of the file dialog
            directory: The initial directory to open
            filter: The file filter to use (e.g., "Image Files (*.png *.jpg)")
            parent: The parent widget

        Returns:
            The selected file path, or None if the dialog was canceled
        """
        fileName, _ = QFileDialog.getOpenFileName(
            parent,
            title,
            directory,
            filter,
        )
        return fileName if fileName else None

    @staticmethod
    def showMessageBox(
        title: str,
        message: str,
        icon: QMessageBox.Icon = QMessageBox.Icon.Information,
        parent=None,
    ) -> int:
        """Displays a message box to the user.

        Args:
            title: The title of the message box
            message: The message to display
            icon: The icon to display (Information, Warning, Critical, Question)
            parent: The parent widget

        Returns:
            The result of the message box (e.g., QMessageBox.StandardButton.Ok)
        """
        msg_box = QMessageBox(parent)
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        return msg_box.exec()

    @staticmethod
    def showErrorMessage(message: str, title: str = "Error", parent=None) -> int:
        """Displays an error message to the user.

        Args:
            message: The error message to display
            title: The title of the error message box
            parent: The parent widget

        Returns:
            The result of the message box
        """
        return DialogUtils.showMessageBox(
            title, message, QMessageBox.Icon.Critical, parent
        )

    @staticmethod
    def showWarningMessage(message: str, title: str = "Warning", parent=None) -> int:
        """Displays a warning message to the user.

        Args:
            message: The warning message to display
            title: The title of the warning message box
            parent: The parent widget

        Returns:
            The result of the message box
        """
        return DialogUtils.showMessageBox(
            title, message, QMessageBox.Icon.Warning, parent
        )

    @staticmethod
    def showProgressDialog(
        title: str,
        label_text: str,
        cancel_button_text: str = "Cancel",
        minimum: int = 0,
        maximum: int = 100,
        parent=None,
        modal: bool = True,
        auto_close: bool = True,
        auto_reset: bool = True,
        min_duration_ms: int = 1000,
    ) -> QProgressDialog:
        """Shows a progress dialog.

        Args:
            title: The title of the progress dialog
            label_text: The text to display in the progress dialog
            cancel_button_text: The text for the cancel button
            minimum: The minimum value of the progress bar
            maximum: The maximum value of the progress bar
            parent: The parent widget
            modal: Whether the dialog is modal
            auto_close: Whether to automatically close the dialog when complete
            auto_reset: Whether to automatically reset the dialog when complete
            min_duration_ms: The minimum duration before showing the dialog

        Returns:
            The progress dialog
        """
        dialog = QProgressDialog(
            label_text,
            cancel_button_text,
            minimum,
            maximum,
            parent,
        )
        dialog.setWindowTitle(title)

        if modal:
            dialog.setWindowModality(Qt.WindowModality.WindowModal)

        dialog.setMinimumDuration(min_duration_ms)
        dialog.setAutoClose(auto_close)
        dialog.setAutoReset(auto_reset)

        return dialog

    @staticmethod
    def showIndeterminateProgressDialog(
        title: str,
        label_text: str,
        cancel_button_text: str = "Cancel",
        parent=None,
        modal: bool = True,
        auto_close: bool = True,
        auto_reset: bool = True,
        min_duration_ms: int = 1000,
    ) -> QProgressDialog:
        """Shows an indeterminate progress dialog (with a busy indicator).

        Args:
            title: The title of the progress dialog
            label_text: The text to display in the progress dialog
            cancel_button_text: The text for the cancel button
            parent: The parent widget
            modal: Whether the dialog is modal
            auto_close: Whether to automatically close the dialog when complete
            auto_reset: Whether to automatically reset the dialog when complete
            min_duration_ms: The minimum duration before showing the dialog

        Returns:
            The progress dialog
        """
        dialog = DialogUtils.showProgressDialog(
            title,
            label_text,
            cancel_button_text,
            0,  # minimum
            0,  # maximum of 0 makes it indeterminate
            parent,
            modal,
            auto_close,
            auto_reset,
            min_duration_ms,
        )

        return dialog

    @staticmethod
    def showOptionsDialog(
        title: str,
        message: str,
        options: List[str],
        default_option: int = 0,
        parent=None,
    ) -> Optional[str]:
        """Shows a dialog with radio button options.

        Args:
            title: The title of the dialog
            message: The message to display
            options: List of option strings
            default_option: Index of the default selected option
            parent: The parent widget

        Returns:
            The selected option string, or None if canceled
        """
        dialog = QDialog(parent or QApplication.activeWindow())
        dialog.setWindowTitle(title)

        layout = QVBoxLayout()

        # Add message
        layout.addWidget(QLabel(message))

        # Add options
        option_group = QButtonGroup(dialog)
        option_buttons = []

        for i, option_text in enumerate(options):
            option = QRadioButton(option_text)
            option_buttons.append(option)

            if i == default_option:
                option.setChecked(True)

            option_group.addButton(option)
            layout.addWidget(option)

        # Add buttons
        button_layout = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)

        # Show dialog and get result
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            for i, option in enumerate(option_buttons):
                if option.isChecked():
                    return options[i]

        return None
