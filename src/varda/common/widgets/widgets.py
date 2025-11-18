from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QSplitter, QLayout


class WrapperWidget(QWidget):
    def __init__(self, layout, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)


class VBoxBuilder(QVBoxLayout):
    def __init__(self):
        super().__init__()

    def withWidget(
        self, widget: QWidget, stretch: int = 0, alignment=Qt.AlignmentFlag(0)
    ):
        self.addWidget(widget, stretch, alignment)
        return self

    def withLayout(self, layout: QVBoxLayout, stretch: int = 0):
        self.addLayout(layout, stretch)
        return self

    def wrapped(self) -> QWidget:
        return WrapperWidget(self)


class SplitterBuilder(QSplitter):
    def __init__(self, orientation: Qt.Orientation):
        super().__init__()
        self.setOrientation(orientation)

    def withWidget(self, widget: QWidget):
        self.addWidget(widget)
        return self

    def withLayout(self, layout: QLayout):
        wrapper = WrapperWidget(layout)
        self.addWidget(wrapper)
        return self
