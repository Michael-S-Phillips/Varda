from typing import Generic
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QSignalBlocker, Qt, QObject
from PyQt6.QtWidgets import (
    QCheckBox,
    QLineEdit,
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

from varda.common.entities import Image


class Parameter[T](QObject):
    sigValueChanged: pyqtSignal = pyqtSignal(object)
    name: str
    value: T

    def __init__(
        self, name: str, default: T, description: str | None = None, parent=None
    ):
        super().__init__(parent)
        self.name = name
        self.value = default
        self.description = description

    def set(self, value: T) -> None:
        self.value = value
        self.sigValueChanged.emit(self.value)

    def get(self) -> T:
        return self.value

    def getWidget(self, parent=None) -> QWidget:
        raise NotImplementedError("Subclasses must implement getWidget")


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
            label = QLabel(param.name)
            widget = param.getWidget(self)
            if param.description is not None:
                label.setToolTip(param.description)
                widget.setToolTip(param.description)
            formLayout.addRow(label, widget)
            param.sigValueChanged.connect(self.sigParameterChanged)
        self.setLayout(formLayout)

    def __repr__(self):
        return f"ParameterGroup({[p.get() for p in self.params]})"


def paramLayoutDefault():
    paramLayout = QHBoxLayout()
    paramLayout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    paramLayout.setContentsMargins(0, 0, 0, 0)
    return paramLayout


class IntParameter(Parameter[int]):
    def __init__(
        self,
        name,
        default=0,
        description=None,
        units=None,
        valueRange=None,
        parent=None,
    ):
        self.units = units
        self.valueRange = valueRange
        if valueRange is not None:  # clamp default to range
            default = max(valueRange[0], min(valueRange[1], default))
        super().__init__(name, default, description=description, parent=parent)

    def getWidget(self, parent=None) -> QWidget:
        return self.IntParameterWidget(self, parent)

    class IntParameterWidget(QWidget):
        def __init__(self, param: "IntParameter", parent=None):
            super().__init__(parent)
            self.param = param
            # init UI
            paramLayout = paramLayoutDefault()

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

            if self.param.units is not None:
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


class FloatParameter(Parameter[float]):
    def __init__(
        self,
        name: str,
        default=0.0,
        description=None,
        units=None,
        valueRange=None,
        parent=None,
    ):
        self.units = units
        self.valueRange = valueRange
        if self.valueRange is not None:  # clamp default to range
            default = max(self.valueRange[0], min(self.valueRange[1], default))
        super().__init__(name, default, description, parent)

    def getWidget(self, parent=None) -> QWidget:
        return self.FloatParameterWidget(self, parent)

    class FloatParameterWidget(QWidget):
        def __init__(self, param: "FloatParameter", parent=None):
            super().__init__(parent)
            self.param = param
            # initialize widget

            paramLayout = paramLayoutDefault()

            self.spinBox = QDoubleSpinBox(parent=self)
            if self.param.valueRange is not None:
                self.spinBox.setRange(
                    self.param.valueRange[0], self.param.valueRange[1]
                )
            else:
                self.spinBox.setRange(-100000, 100000)
            self.spinBox.setValue(self.param.get())
            self.spinBox.valueChanged.connect(self.valueChanged)
            paramLayout.addWidget(self.spinBox)

            if self.param.units is not None:
                self.unitLabel = QLabel(self.param.units)
                paramLayout.addWidget(self.unitLabel)

            if self.param.valueRange is not None:
                self.slider = self.FloatSlider(parent=self)
                self.slider.setOrientation(Qt.Orientation.Horizontal)
                self.slider.setRange(self.param.valueRange[0], self.param.valueRange[1])
                self.slider.setValue(self.param.get())
                self.slider.sigFloatValueChanged.connect(self.valueChanged)
                paramLayout.addWidget(self.slider)

            self.setLayout(paramLayout)

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


class StringParameter(Parameter[str]):
    def __init__(self, name: str, default: str = "", description=None, parent=None):
        super().__init__(name, default, description, parent)

    def getWidget(self, parent=None) -> QWidget:
        return self.StringParameterWidget(self, parent)

    class StringParameterWidget(QWidget):
        def __init__(self, param: "StringParameter", parent=None):
            super().__init__(parent)
            self.param = param

            self.lineEdit = QLineEdit(self)
            self.lineEdit.setText(self.param.get())
            self.lineEdit.textChanged.connect(self.textChanged)

            paramLayout = paramLayoutDefault()
            paramLayout.addWidget(self.lineEdit)
            self.setLayout(paramLayout)

        @pyqtSlot(str)
        def textChanged(self, text):
            self.param.set(text)


class BoolParameter(Parameter[bool]):
    def __init__(self, name, default=False, description=None, parent=None):
        super().__init__(name, default, description, parent)

    def getWidget(self, parent=None) -> QWidget:
        return self.BoolParameterWidget(self, parent)

    class BoolParameterWidget(QWidget):
        def __init__(self, param: "BoolParameter", parent=None):
            super().__init__(parent)
            self.param = param

            self.checkBox = QCheckBox(self)
            self.checkBox.setChecked(self.param.get())
            self.checkBox.checkStateChanged.connect(self.stateChanged)
            paramLayout = paramLayoutDefault()
            paramLayout.addWidget(self.checkBox)
            self.setLayout(paramLayout)

        @pyqtSlot(Qt.CheckState)
        def stateChanged(self, state):
            self.param.set(state == Qt.CheckState.Checked)


class ImageParameter(Parameter[Image]):
    def __init__(
        self, name: str, imageList: list[Image], description=None, parent=None
    ) -> None:
        self.imageList = imageList
        if len(self.imageList) == 0:
            raise ValueError("ImageParameter requires a non-empty imageList")
        default = self.imageList[0]
        super().__init__(name, default, description, parent)

    def getWidget(self, parent=None) -> QWidget:
        return self.ImageParameterWidget(self, parent)

    class ImageParameterWidget(QWidget):
        def __init__(self, param: "ImageParameter", parent=None):
            super().__init__(parent)
            self.param = param
            self.imageList = param.imageList
            self.comboBox = QComboBox(self)
            if len(self.imageList) == 0:
                self.comboBox.addItem("No Images Available!")
            else:
                self.comboBox.addItems(
                    [image.metadata.name for image in self.imageList]
                )
            self.comboBox.currentIndexChanged.connect(self.imageSelectionChanged)

            paramLayout = paramLayoutDefault()
            paramLayout.addWidget(self.comboBox)
            self.setLayout(paramLayout)

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
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
    from varda.utilities import debug

    qapp = QApplication([])

    layout = QVBoxLayout()

    intParam0 = IntParameter("test", 10, "A test int parameter", "test units", (0, 100))
    floatParam0 = FloatParameter(
        "FloatVal", 15.15, "A test float parameter", "floating units", (0, 100)
    )
    boolParam0 = BoolParameter("BoolVal", True, "A test bool parameter")
    stringParam0 = StringParameter(
        "StringVal", "default text", "A test string parameter"
    )
    imageParam0 = ImageParameter(
        "ImageVal",
        [debug.generate_random_image(), debug.generate_random_image()],
        "A test image parameter",
    )
    paramGroup = ParameterGroup(
        [intParam0, floatParam0, boolParam0, stringParam0, imageParam0]
    )
    layout.addWidget(paramGroup)

    w = QWidget()
    w.setLayout(layout)
    w.show()
    sys.exit(qapp.exec())
