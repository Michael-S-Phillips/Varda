from PyQt6.QtCore import QObject

from src.varda.common.entities import Image


class Project(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.images: list[Image] = []