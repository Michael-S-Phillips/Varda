from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QSplitter,
    QLayout,
    QFormLayout,
)


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
    ) -> VBoxBuilder:
        self.addWidget(widget, stretch, alignment)
        return self

    def withLayout(self, layout: QVBoxLayout, stretch: int = 0) -> VBoxBuilder:
        self.addLayout(layout, stretch)
        return self

    def wrapped(self) -> WrapperWidget:
        return WrapperWidget(self)


class HBoxBuilder(QHBoxLayout):
    def __init__(self):
        super().__init__()

    def withWidget(
        self, widget: QWidget, stretch: int = 0, alignment=Qt.AlignmentFlag(0)
    ) -> HBoxBuilder:
        self.addWidget(widget, stretch, alignment)
        return self

    def withLayout(self, layout: QHBoxLayout, stretch: int = 0) -> HBoxBuilder:
        self.addLayout(layout, stretch)
        return self

    def wrapped(self) -> WrapperWidget:
        return WrapperWidget(self)


class SplitterBuilder(QSplitter):
    def __init__(self, orientation: Qt.Orientation):
        super().__init__()
        self.setOrientation(orientation)

    def withWidget(self, widget: QWidget, stretchFactor: int = 1) -> SplitterBuilder:
        self.addWidget(widget)
        self.setStretchFactor(self.indexOf(widget), stretchFactor)
        return self

    def withLayout(self, layout: QLayout, stretchFactor: int = 1) -> SplitterBuilder:
        wrapper = WrapperWidget(layout)
        self.addWidget(wrapper)
        self.setStretchFactor(self.indexOf(wrapper), stretchFactor)
        return self


class FormBuilder(QFormLayout):
    def __init__(self):
        super().__init__()

    def withRow(self, label: str, widget: QWidget) -> FormBuilder:
        self.addRow(label, widget)
        return self

    def wrapped(self) -> WrapperWidget:
        return WrapperWidget(self)
