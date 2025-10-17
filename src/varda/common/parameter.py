from PyQt6.QtCore import pyqtSignal, pyqtSlot, QSignalBlocker, Qt
from PyQt6.QtWidgets import (
    QSpinBox,
    QWidget,
    QSlider,
    QHBoxLayout,
    QApplication,
    QVBoxLayout,
    QLabel,
    QDoubleSpinBox,
)
from typing_extensions import override


class FloatSlider(QSlider):
    sigFloatValueChanged = pyqtSignal(float)

    def __init__(self, precision=3, parent=None):
        super().__init__(parent)
        self.precision = precision
        self.valueChanged.connect(self.onValueChanged)

    @override
    def setRange(self, min, max):
        min = min * pow(10, self.precision)
        max = max * pow(10, self.precision)
        super().setRange(min, max)

    @override
    def setValue(self, a0):
        super().setValue(a0 * pow(10, self.precision))

    def onValueChanged(self, value):
        floatVal = value / pow(10, self.precision)
        self.sigFloatValueChanged.emit(floatVal)


class Parameter(QWidget):
    sigValueChanged = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

    def name(self): ...

    def units(self): ...

    def set(self, value): ...

    def get(self): ...


class IntParameter(QWidget):

    def __init__(self, name, units, default=0, valueRange=None, parent=None):
        super().__init__()
        self.name = name
        self.units = units
        self.valueRange = valueRange
        if self.valueRange is not None:  # clamp default to range
            default = max(self.valueRange[0], min(self.valueRange[1], default))
        self.value = default
        self.spinBox = None
        self.slider = None

    def _initUI(self):
        # initialize widget
        layout = QHBoxLayout(self)
        self.spinBox = QSpinBox(parent=self)
        if self.valueRange is not None:
            self.spinBox.setRange(self.valueRange[0], self.valueRange[1])
        else:
            self.spinBox.setRange(-100000, 100000)
        self.spinBox.setValue(self.value)
        self.spinBox.valueChanged.connect(self.valueChanged)
        layout.addWidget(self.spinBox)

        self.unitLabel = QLabel(self.units)
        layout.addWidget(self.unitLabel)

        if self.valueRange is not None:
            self.slider = QSlider(parent=self)
            self.slider.setOrientation(Qt.Orientation.Horizontal)
            self.slider.setRange(self.valueRange[0], self.valueRange[1])
            self.slider.setValue(self.value)
            self.slider.valueChanged.connect(self.valueChanged)
            layout.addWidget(self.slider)

        self.setLayout(layout)

    @pyqtSlot(int)
    def valueChanged(self, value):
        self.value = value

        if self.spinBox.value() != value:
            with QSignalBlocker(self.spinBox):
                self.spinBox.setValue(value)
        if self.slider is not None and self.slider.value() != value:
            with QSignalBlocker(self.slider):
                self.slider.setValue(value)

        self.sigValueChanged.emit(value)

    def name(self):
        return self.name

    def units(self):
        return self.units

    def set(self, value):
        self.valueChanged(value)

    def get(self):
        return self.value


class FloatParameter(Parameter):

    def __init__(self, name, units, default=0.0, valueRange=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.units = units
        self.valueRange = valueRange
        if self.valueRange is not None:  # clamp default to range
            default = max(self.valueRange[0], min(self.valueRange[1], default))
        self.value = default
        self.spinBox = None
        self.slider = None

    def _initUI(self):
        # initialize widget
        layout = QHBoxLayout(self)
        self.spinBox = QDoubleSpinBox(parent=self)
        if self.valueRange is not None:
            self.spinBox.setRange(self.valueRange[0], self.valueRange[1])
        else:
            self.spinBox.setRange(-100000, 100000)
        self.spinBox.setValue(self.value)
        self.spinBox.valueChanged.connect(self.valueChanged)
        layout.addWidget(self.spinBox)

        self.unitLabel = QLabel(self.units)
        layout.addWidget(self.unitLabel)

        if self.valueRange is not None:
            self.slider = FloatSlider(parent=self)
            self.slider.setOrientation(Qt.Orientation.Horizontal)
            self.slider.setRange(self.valueRange[0], self.valueRange[1])
            self.slider.setValue(self.value)
            self.slider.valueChanged.connect(self.valueChanged)
            layout.addWidget(self.slider)

        self.setLayout(layout)

    @pyqtSlot(float)
    def valueChanged(self, value):
        self.value = value

        if self.spinBox.value() != value:
            with QSignalBlocker(self.spinBox):
                self.spinBox.setValue(value)
        if self.slider is not None and self.slider.value() != value:
            with QSignalBlocker(self.slider):
                self.slider.setValue(value)

        self.sigValueChanged.emit(value)

    def name(self):
        return self.name

    def units(self):
        return self.units

    def set(self, value):
        self.valueChanged(value)

    def get(self):
        return self.value


class StringParameter:
    def __init__(self, name, default):
        self.name = name
        self.default = default
        self.value = default

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class BoolParameter:
    def __init__(self, name, default):
        self.name = name
        self.default = default
        self.value = default


if __name__ == "__main__":
    import sys

    qapp = QApplication([])

    layout = QVBoxLayout()

    intParam0 = IntParameter("test", "test units", 10, (0, 100))
    # intParam1 = IntParameter("test4", "test units", 10)
    # floatParam0 = FloatParameter("FloatVal", "floating units", 15.15, (0, 100))

    layout.addWidget(intParam0)
    # layout.addWidget(intParam1)
    # layout.addWidget(floatParam0)

    w = QWidget()
    w.setLayout(layout)
    w.show()
    sys.exit(qapp.exec())
