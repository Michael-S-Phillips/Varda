from PyQt6.QtCore import pyqtSignal, pyqtSlot, QSignalBlocker, Qt, QObject
from PyQt6.QtWidgets import (
    QComboBox,
    QSpinBox,
    QWidget,
    QSlider,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QFormLayout,
    QSizePolicy,
)

from typing_extensions import override


class Parameter(QObject):
    sigValueChanged: pyqtSignal = pyqtSignal(object)
    name: str
    value: object

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name = name

    def set(self, value): ...

    def get(self): ...

    def getWidget(self, parent=None): ...


class ParameterGroup(QWidget):
    sigParameterChanged: pyqtSignal = pyqtSignal()

    def __init__(self, params: list[Parameter], parent=None):
        super().__init__(parent)
        self.params = params
        formLayout = QFormLayout()
        # formLayout.setSpacing(0)
        # formLayout.setFieldGrowthPolicy(
        #     formLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        # )
        for param in self.params:
            formLayout.addRow(param.name, param.getWidget(self))
            param.sigValueChanged.connect(self.sigParameterChanged)
        self.setLayout(formLayout)

    def __repr__(self):
        return f"ParameterGroup({[p.get() for p in self.params]})"


class IntParameter(Parameter):
    def __init__(self, name, units, default=0, valueRange=None, parent=None):
        super().__init__(name, parent)
        self.units = units
        self.valueRange = valueRange
        if self.valueRange is not None:  # clamp default to range
            default = max(self.valueRange[0], min(self.valueRange[1], default))
        self._value = default

    def set(self, value):
        self._value = value
        super().sigValueChanged.emit(self._value)

    def get(self):
        return self._value

    def getWidget(self, parent=None):
        return self.IntParameterWidget(self, parent)

    class IntParameterWidget(QWidget):
        def __init__(self, param: "IntParameter", parent=None):
            super().__init__(parent)
            self.param = param
            # init UI
            paramLayout = QHBoxLayout(self)
            paramLayout.setAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
            )
            paramLayout.setContentsMargins(0, 0, 0, 0)

            self.spinBox = QSpinBox(parent=self)
            self.spinBox.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
            )
            self.spinBox.setMinimumSize(60, 30)
            if self.param.valueRange is not None:
                self.spinBox.setRange(
                    self.param.valueRange[0], self.param.valueRange[1]
                )
            else:
                self.spinBox.setRange(-100000, 100000)
            self.spinBox.setValue(self.param.get())
            self.spinBox.valueChanged.connect(self.valueChanged)

            paramLayout.addWidget(self.spinBox)

            self.unitLabel = QLabel(self.param.units)
            paramLayout.addWidget(self.unitLabel)

            if self.param.valueRange is not None:
                self.slider = QSlider(parent=self)
                self.slider.setOrientation(Qt.Orientation.Horizontal)
                # self.slider.setSizePolicy(
                #     QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                # )
                self.slider.setRange(self.param.valueRange[0], self.param.valueRange[1])
                self.slider.setValue(self.param.get())
                self.slider.valueChanged.connect(self.valueChanged)
                paramLayout.addWidget(self.slider)

            self.setLayout(paramLayout)

        @pyqtSlot(int)
        def valueChanged(self, value):
            if self.spinBox.value() != value:
                with QSignalBlocker(self.spinBox):
                    self.spinBox.setValue(value)
            if self.slider is not None and self.slider.value() != value:
                with QSignalBlocker(self.slider):
                    self.slider.setValue(value)

            self.param.set(value)


class FloatParameter(Parameter):
    def __init__(
        self, name: str, units: str, default=0.0, valueRange=None, parent=None
    ):
        super().__init__(name, parent)
        self.name = name
        self.units = units
        self.valueRange = valueRange
        if self.valueRange is not None:  # clamp default to range
            default = max(self.valueRange[0], min(self.valueRange[1], default))
        self._value = default

    def set(self, value):
        self._value = value
        super().sigValueChanged.emit(self._value)

    def get(self):
        return self._value

    class FloatParameterWidget(QWidget):
        def __init__(self, param: "FloatParameter", parent=None):
            super().__init__(parent)
            self.param = param
            # initialize widget
            layout = QHBoxLayout(self)
            self.spinBox = QDoubleSpinBox(parent=self)
            if self.param.valueRange is not None:
                self.spinBox.setRange(
                    self.param.valueRange[0], self.param.valueRange[1]
                )
            else:
                self.spinBox.setRange(-100000, 100000)
            self.spinBox.setValue(self.param.get())
            self.spinBox.valueChanged.connect(self.valueChanged)
            layout.addWidget(self.spinBox)

            self.unitLabel = QLabel(self.param.units)
            layout.addWidget(self.unitLabel)

            if self.param.valueRange is not None:
                self.slider = self.FloatSlider(parent=self)
                self.slider.setOrientation(Qt.Orientation.Horizontal)
                self.slider.setRange(self.param.valueRange[0], self.param.valueRange[1])
                self.slider.setValue(self.param.get())
                self.slider.sigFloatValueChanged.connect(self.valueChanged)
                layout.addWidget(self.slider)

            self.setLayout(layout)

        @pyqtSlot(float)
        def valueChanged(self, value):
            if self.spinBox.value() != value:
                with QSignalBlocker(self.spinBox):
                    self.spinBox.setValue(value)
            if self.slider is not None and self.slider.value() != value:
                with QSignalBlocker(self.slider):
                    self.slider.setValue(value)

            self.param.set(value)

        class FloatSlider(QSlider):
            sigFloatValueChanged: pyqtSignal = pyqtSignal(float)

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
                super().setValue(int(a0 * pow(10, self.precision)))

            def onValueChanged(self, value):
                floatVal = value / pow(10, self.precision)
                self.sigFloatValueChanged.emit(floatVal)


class StringParameter(Parameter):
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


class ImageParameter(Parameter):
    def __init__(self, name: str, imageList, parent=None) -> None:
        super().__init__(name, parent)
        self.imageList = imageList
        self._image = imageList[0] if len(self.imageList) != 0 else None

    def set(self, image):
        self._image = image
        super().sigValueChanged.emit(self._image)

    def get(self):
        return self._image

    def getWidget(self, parent=None):
        return self.ImageParameterWidget(self, self.imageList, parent)

    class ImageParameterWidget(QWidget):
        def __init__(self, param: "ImageParameter", imageList, parent=None):
            super().__init__(parent)
            self.param = param
            self.imageList = imageList
            self.comboBox = QComboBox(self)
            if len(imageList) == 0:
                self.comboBox.addItem("No Images Available!")
            else:
                self.comboBox.addItems(
                    [image.metadata.name for image in self.imageList]
                )
            self.comboBox.currentIndexChanged.connect(self.imageSelectionChanged)

        def imageSelectionChanged(self, index):
            self.param.set(self.imageList[index])


# if __name__ == "__main__":
#     q_app = pg.mkQApp()
#     paramGroup = ParameterGroup(
#         [
#             IntParameter("test", "test units", 10, (0, 100)),
#             IntParameter("test2", "test units", 7, (0, 10)),
#         ]
#     )
#     paramGroup.show()
#     q_app.exec()
#
#
# if __name__ == "__main__":
#     import sys
#
#     qapp = QApplication([])
#
#     layout = QVBoxLayout()
#
#     intParam0 = IntParameter("test", "test units", 10, (0, 100)).getWidget()
#     # intParam1 = IntParameter("test4", "test units", 10)
#     # floatParam0 = FloatParameter("FloatVal", "floating units", 15.15, (0, 100))
#
#     layout.addWidget(intParam0)
#     # layout.addWidget(intParam1)
#     # layout.addWidget(floatParam0)
#
#     w = QWidget()
#     w.setLayout(layout)
#     w.show()
#     sys.exit(qapp.exec())
