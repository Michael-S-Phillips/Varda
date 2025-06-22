from PyQt6.QtWidgets import QWidget
from abc import ABC, abstractmethod


class VWidget(QWidget):
    """
    The interface for Varda widgets.
    Widgets should implement this interface to be recognized by the Varda application.
    """

    v_name: str
    v_description: str
    v_icon: str

    def execute(self, context) -> None:
        """
        Execute the widget with the given context.
        """
