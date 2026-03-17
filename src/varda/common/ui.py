from __future__ import annotations

from typing_extensions import override
from typing import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QWidget,
    QSplitter,
    QLayout,
    QFormLayout,
    QDockWidget,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMainWindow,
    QLabel,
    QDialog,
    QTabBar,
    QTabWidget,
    QSlider,
    QFrame,
    QSpinBox,
    QSizePolicy,
    QScrollArea,
)


class WrapperWidget(QWidget):
    def __init__(self, layout: QLayout, parent: QWidget | None = None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)


class VBoxBuilder(QVBoxLayout):
    def __init__(self, alignment=Qt.AlignmentFlag(0), margins=None):
        super().__init__()
        self.setAlignment(alignment)
        if margins is not None:
            self.setContentsMargins(margins, margins, margins, margins)

    def withWidget(
        self, widget: QWidget | None, stretch: int = 0, alignment=Qt.AlignmentFlag(0)
    ) -> VBoxBuilder:
        self.addWidget(widget, stretch, alignment)
        return self

    def withLayout(self, layout: QLayout | None, stretch: int = 0) -> VBoxBuilder:
        self.addLayout(layout, stretch)
        return self

    def withStretch(self, stretch: int = 0) -> VBoxBuilder:
        self.addStretch(stretch)
        return self


class HBoxBuilder(QHBoxLayout):
    def __init__(self, alignment=Qt.AlignmentFlag(0), margins=None):
        super().__init__()
        self.setAlignment(alignment)
        if margins is not None:
            self.setContentsMargins(margins, margins, margins, margins)

    def withWidget(
        self, widget: QWidget | None, stretch: int = 0, alignment=Qt.AlignmentFlag(0)
    ) -> HBoxBuilder:
        self.addWidget(widget, stretch, alignment)
        return self

    def withLayout(self, layout: QLayout | None, stretch: int = 0) -> HBoxBuilder:
        self.addLayout(layout, stretch)
        return self

    def withStretch(self, stretch: int = 0) -> HBoxBuilder:
        self.addStretch(stretch)
        return self


class GroupBoxBuilder(QGroupBox):
    def __init__(self, title: str, layout: QLayout):
        super().__init__(title)
        self.setLayout(layout)


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


class ScrollArea(QScrollArea):
    def __init__(self, contents: QWidget | QLayout, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if isinstance(contents, QLayout):
            contents = WrapperWidget(contents)

        self.setWidget(contents)


class FormBuilder(QFormLayout):
    def __init__(self):
        super().__init__()

    def withRow(self, label: str, widget: QWidget) -> FormBuilder:
        self.addRow(label, widget)
        return self


class ButtonBuilder(QPushButton):
    def __init__(self, label: str):
        super().__init__(label)

    def onClick(self, callback) -> ButtonBuilder:
        self.clicked.connect(callback)
        return self

    def default(self) -> ButtonBuilder:
        self.setDefault(True)
        return self


class SectionBox(QWidget):
    def __init__(
        self,
        name: str | None = None,
        content: QWidget | QLayout | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.frame.setObjectName("SectionBox")
        self.frame.setStyleSheet("""
        QFrame#SectionBox {
            border: 2px solid palette(mid); 
            border-radius: 6px;
        }
        """)
        self.currentContent = None
        self.frameLayout = QVBoxLayout()
        if isinstance(content, QLayout):
            self.frameLayout.addLayout(content)
        elif isinstance(content, QWidget):
            self.frameLayout.addWidget(content)
        elif content is not None:
            raise TypeError("SectionBox requires a QWidget or QLayout (or None)")
        self.frame.setLayout(self.frameLayout)

        self.setLayout(
            VBoxBuilder()
            .withWidget(QLabel(name) if name else None)
            .withWidget(self.frame)
        )

    def setContent(self, content: QWidget | QLayout | None):
        # clear existing items
        self._clearLayout(self.frameLayout)
        # now set new layout
        if content is None:
            return
        elif isinstance(content, QLayout):
            self.frameLayout.addLayout(content)
        elif isinstance(content, QWidget):
            self.frameLayout.addWidget(content)
        else:
            raise TypeError("SectionBox requires a QWidget or QLayout (or None)")

    def _clearLayout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if w := item.widget():
                w.setParent(None)
            elif l := item.layout():
                self._clearLayout(l)


class VardaDockWidget(QDockWidget):
    def __init__(self, title, widget=None, area=None, parent=None):
        super().__init__(title, parent)

        self.setObjectName("VardaDockWidget")
        self.setFeatures(
            self.DockWidgetFeature.DockWidgetMovable
            | self.DockWidgetFeature.DockWidgetFloatable
        )
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        if widget:
            self.setWidget(widget)

        if parent is not None and area is not None and isinstance(parent, QMainWindow):
            parent.addDockWidget(area, self)


class FilePathBox(QWidget):
    def __init__(
        self,
        defaultPath: str = "",
        fileFilter: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.fileFilter = fileFilter
        self.result: str | None

        # setup UI
        self.filePathText = QLineEdit(defaultPath)
        self.openFileSelectorButton = QPushButton("Browse Files...")
        layout = QHBoxLayout()
        layout.addWidget(self.filePathText)
        layout.addWidget(self.openFileSelectorButton)
        self.setLayout(layout)

        # connect signals
        self.openFileSelectorButton.clicked.connect(self.getFilePath)
        self.filePathText.textChanged.connect(self.onTextChanged)

    def getFilePath(self):
        filename, _ = QFileDialog.getOpenFileName(
            None,
            "Select Image File",
            "",
            self.fileFilter,
        )
        if filename:
            self.filePathText.setText(filename)

    def onTextChanged(self):
        self.result = self.filePathText.text()


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


class DetachableTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(self.DetachableTabBar(self))
        self.detachedWindows = {}

    def detachTab(self, index):
        widget = self.widget(index)
        if widget is None:
            return

        label = self.tabText(index)
        self.removeTab(index)

        detachedTabWindow = self.DetachedTabWindow(label, widget, self)
        detachedTabWindow.show()

        self.detachedWindows[widget] = detachedTabWindow

    def reattachTab(self, widget, label):
        del self.detachedWindows[widget]
        self.addTab(widget, label)
        self.setCurrentWidget(widget)

    class DetachableTabBar(QTabBar):
        def __init__(self, parentTabWidget):
            super().__init__()
            self.parentTabWidget = parentTabWidget

        def mouseDoubleClickEvent(self, event):
            index = self.tabAt(event.pos())
            if index != -1:
                self.parentTabWidget.detachTab(index)
            super().mouseDoubleClickEvent(event)

    class DetachedTabWindow(QMainWindow):
        def __init__(self, label, widget, tab_widget):
            super().__init__()
            self.setWindowTitle(label)
            self.tabWidget = tab_widget
            self.label = label
            self.widget = widget
            self.newTabWidget = QTabWidget()
            self.setCentralWidget(self.newTabWidget)
            self.newTabWidget.addTab(self.widget, self.label)
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        def closeEvent(self, event):
            # Reattach the widget back into the main tab widget
            self.tabWidget.reattachTab(self.widget, self.label)
            super().closeEvent(event)


class FloatSlider(QSlider):
    sigFloatValueChanged: pyqtSignal = pyqtSignal(float)

    def __init__(
        self, precision=3, range: tuple[float, float] | None = None, parent=None
    ):
        super().__init__(parent)
        self.precision = precision
        self.valueChanged.connect(self.onValueChanged)

        if range is not None:
            self.setRange(range[0], range[1])

    @override
    def setRange(self, min: float, max: float) -> None:
        min = min * pow(10, self.precision)
        max = max * pow(10, self.precision)
        super().setRange(int(min), int(max))

    @override
    def setValue(self, a0: float) -> None:
        super().setValue(int(a0 * pow(10, self.precision)))

    def onValueChanged(self, value):
        floatVal = value / pow(10, self.precision)
        self.sigFloatValueChanged.emit(floatVal)


class SpinBoxBuilder:
    """Convenience class for building QSpinBox widgets in a declarative style.

    Chain together methods to configure the QSpinBox, and call build() to get the final widget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self.widget = QSpinBox(parent)

    def sizePolicy(
        self, horizontal: QSizePolicy.Policy, vertical: QSizePolicy.Policy
    ) -> SpinBoxBuilder:
        self.widget.setSizePolicy(horizontal, vertical)
        return self

    def minimumSize(self, width: int, height: int) -> SpinBoxBuilder:
        self.widget.setMinimumSize(width, height)
        return self

    def range(self, range: tuple[int, int]) -> SpinBoxBuilder:
        self.widget.setRange(range[0], range[1])
        return self

    def default(self, value: int) -> SpinBoxBuilder:
        self.widget.setValue(value)
        return self

    def binding(self, onValueChanged: Callable[[int], None]) -> SpinBoxBuilder:
        self.widget.valueChanged.connect(onValueChanged)
        return self

    def build(self) -> QSpinBox:
        return self.widget


class SliderBuilder:
    """Convenience class for building QSlider widgets in a declarative style.

    Chain together methods to configure the QSlider, and call build() to get the final widget.
    """

    def __init__(self, parent=None):
        self.widget = QSlider(parent)

    def orientation(self, orientation: Qt.Orientation) -> SliderBuilder:
        self.widget.setOrientation(orientation)
        return self

    def range(self, range: tuple[int, int]) -> SliderBuilder:
        self.widget.setRange(range[0], range[1])
        return self

    def default(self, value: int) -> SliderBuilder:
        self.widget.setValue(value)
        return self

    def binding(self, onValueChanged: Callable[[int], None]) -> SliderBuilder:
        self.widget.valueChanged.connect(onValueChanged)
        return self

    def build(self) -> QSlider:
        return self.widget
