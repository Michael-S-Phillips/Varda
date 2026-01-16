from __future__ import annotations
import re
from enum import Enum
from typing import Type, Callable
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QSignalBlocker, Qt, QObject
from PyQt6.QtGui import QColor

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
    QColorDialog,
    QPushButton,
)

from varda.common.ui import FloatSlider, VBoxBuilder
from varda.common.entities import Image
from varda.common.vec2 import Vec2


class ParameterGroup(QObject):
    """Class that does some magic to let you define a class similarly to a dataclass, but specifically for Parameters.

    Usage:
    class MyParameters(ParameterGroup):
        intParam: IntParameter = IntParameter("My Integer", 10, (0, 10), "int units", "An integer parameter")
        floatParam: FloatParameter = FloatParameter("Float Parameter", 5.0, (0.0, 10.0), "float units", "A float parameter")
    """

    sigParameterChanged: pyqtSignal = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # used to store all parameters in a list, for generating UI later.
        self.params: dict[str, Parameter | ParameterGroup] = {}

        # find all Parameter attributes defined in the class and create unique copies of them for this instance
        for name, attr in self.__class__.__dict__.items():
            if isinstance(attr, Parameter) or isinstance(attr, ParameterGroup):
                instanceParam = attr.clone(parent=self)
                # link the parameter's change signal to the collection's change signal. lambda is to discard the value sent by the parameter
                instanceParam.sigParameterChanged.connect(
                    lambda _: self.sigParameterChanged.emit()
                )
                setattr(
                    self, name, instanceParam
                )  # create an instance attribute for this parameter.
                self.params[name] = instanceParam

    def createWidget(self, parent=None) -> QWidget:
        def createForm(baseLayout: QFormLayout, paramGroup: ParameterGroup):
            for param in paramGroup.params.values():
                if isinstance(param, Parameter):
                    label = QLabel(param.name)
                    widget = param.getWidget()
                    label.setToolTip(param.description)
                    widget.setToolTip(param.description)
                    formLayout.addRow(label, widget)
                elif isinstance(param, ParameterGroup):
                    # recursive call to create ui for subgroup
                    createForm(baseLayout, param)

        formLayout = QFormLayout()
        formLayout.setContentsMargins(0, 0, 0, 0)
        formLayout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        formLayout.setFieldGrowthPolicy(
            formLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        createForm(formLayout, self)

        widget = QWidget(parent)
        widget.setLayout(formLayout)
        return widget

    def clone(self, parent: QObject | None = None) -> ParameterGroup:
        """
        Instantiates a new ParameterGroup based on the current group's state.
        """
        newGroup = self.__class__(parent)
        for name, param in self.params.items():
            setattr(newGroup, name, param.clone(parent=newGroup))
        return newGroup


class Parameter[T](QObject):
    sigParameterChanged: pyqtSignal = pyqtSignal(object)

    def __init__(
        self, name: str, default: T, description: str | None = None, parent=None
    ):
        super().__init__(parent)
        self.name = name
        self.default = default
        self.value: T = default
        self.description = description

    def set(self, value: T) -> None:
        self.value = value
        self.sigParameterChanged.emit(self.value)

    def get(self) -> T:
        return self.value

    def resetToDefault(self) -> None:
        self.set(self.default)

    def getWidget(self, parent=None) -> QWidget:
        raise NotImplementedError("Subclasses must implement getWidget")

    def clone(self, parent=None) -> Parameter[T]:
        """
        Instantiates a new Parameter based on the current parameter's state.
        """
        raise NotImplementedError(
            f"Subclass {self.__class__.__name__} must implement clone()"
        )


class ParameterGroupWidget(QWidget):
    sigParameterChanged: pyqtSignal = pyqtSignal()

    def __init__(self, params: list[Parameter], parent=None):
        super().__init__(parent)
        self.params = params
        formLayout = QFormLayout()
        formLayout.setContentsMargins(0, 0, 0, 0)
        formLayout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        # formLayout.setSpacing(0)
        formLayout.setFieldGrowthPolicy(
            formLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        for param in self.params:
            label = QLabel(param.name)
            widget = param.getWidget(self)
            if param.description is not None:
                label.setToolTip(param.description)
                widget.setToolTip(param.description)
            formLayout.addRow(label, widget)
            param.sigParameterChanged.connect(self.sigParameterChanged)
        self.setLayout(formLayout)

    def __repr__(self):
        return f"ParameterGroup({[p.get() for p in self.params]})"

    def editParams(self):
        """
        returns a context manager that blocks signals on the param group while editing multiple parameters within the group.
        Once you're done editing, exiting the context will emit a single sigParameterChanged event.
        Usage:
            with paramGroup.editParams():
                param1.set(value1)
                param2.set(value2)
        """
        return self.ParamGroupEditContext(self)

    def resetToDefaults(self) -> None:
        """
        Resets all parameters in the group to their default values.
        """
        with self.editParams():
            for param in self.params:
                param.resetToDefault()

    class ParamGroupEditContext:
        def __init__(self, group: "ParameterGroupWidget"):
            self.group = group

        def __enter__(self):
            self.group.blockSignals(True)

        def __exit__(self, exc_type, exc_value, traceback):
            self.group.blockSignals(False)
            self.group.sigParameterChanged.emit()


def paramLayoutDefault():
    paramLayout = QHBoxLayout()
    paramLayout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    paramLayout.setContentsMargins(0, 0, 0, 0)
    return paramLayout


class IntParameter(Parameter[int]):
    def __init__(
        self,
        name,
        default: int = 0,
        range: tuple[int, int] | None = None,
        units: str | None = None,
        description: str | None = None,
        parent: QObject | None = None,
    ):
        self.units = units
        self.range = range
        if range is not None:
            default = max(range[0], min(range[1], default))  # clamp default to range
        super().__init__(name, default, description=description, parent=parent)

    def getWidget(self, parent=None) -> QWidget:
        return self.IntParameterWidget(self, parent)

    def clone(self, parent=None) -> IntParameter:
        return IntParameter(
            name=self.name,
            default=self.default,
            range=self.range,
            units=self.units,
            description=self.description,
            parent=parent,
        )

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
            if self.param.range is not None:
                self.spinBox.setRange(self.param.range[0], self.param.range[1])
            else:
                self.spinBox.setRange(-100000, 100000)
            self.spinBox.setValue(self.param.get())
            self.spinBox.valueChanged.connect(self.valueChanged)

            paramLayout.addWidget(self.spinBox)

            if self.param.units is not None:
                self.unitLabel = QLabel(self.param.units)
                paramLayout.addWidget(self.unitLabel)

            if self.param.range is not None:
                self.slider = QSlider(parent=self)
                self.slider.setOrientation(Qt.Orientation.Horizontal)
                # self.slider.setSizePolicy(
                #     QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                # )
                self.slider.setRange(self.param.range[0], self.param.range[1])
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
        range: tuple[float, float] | None = None,
        units: str | None = None,
        description: str | None = None,
        parent: QObject | None = None,
    ):
        self.units = units
        self.range = range
        if range is not None:
            default = max(range[0], min(range[1], default))  # clamp default to range
        super().__init__(name, default, description, parent)

    def getWidget(self, parent=None) -> QWidget:
        return self.FloatParameterWidget(self, parent)

    def clone(self, parent=None) -> FloatParameter:
        return FloatParameter(
            name=self.name,
            default=self.default,
            range=self.range,
            units=self.units,
            description=self.description,
            parent=parent,
        )

    class FloatParameterWidget(QWidget):
        def __init__(self, param: "FloatParameter", parent=None):
            super().__init__(parent)
            self.param = param
            self.param.sigParameterChanged.connect(self.onParamChanged)
            # initialize widget

            paramLayout = paramLayoutDefault()

            self.spinBox = QDoubleSpinBox(parent=self)
            if self.param.range is not None:
                self.spinBox.setRange(self.param.range[0], self.param.range[1])
            else:
                self.spinBox.setRange(-100000.0, 100000.0)
            self.spinBox.setValue(self.param.get())
            self.spinBox.valueChanged.connect(self.onWidgetChanged)
            paramLayout.addWidget(self.spinBox)

            if self.param.units is not None:
                self.unitLabel = QLabel(self.param.units)
                paramLayout.addWidget(self.unitLabel)

            if self.param.range is not None:
                self.slider = FloatSlider(parent=self)
                self.slider.setOrientation(Qt.Orientation.Horizontal)
                self.slider.setRange(self.param.range[0], self.param.range[1])
                self.slider.setValue(self.param.get())
                self.slider.sigFloatValueChanged.connect(self.onWidgetChanged)
                paramLayout.addWidget(self.slider)
            else:
                self.slider = None
            self.setLayout(paramLayout)

        def onWidgetChanged(self, value):
            # update parameter value -- this will trigger onParamChanged to run, which will synchronize the slider and spinbox
            self.param.set(value)

        @pyqtSlot(object)
        def onParamChanged(self, value: float):
            if self.spinBox.value() != value:
                with QSignalBlocker(self.spinBox):
                    self.spinBox.setValue(value)
            if self.slider is not None and self.slider.value() != value:
                with QSignalBlocker(self.slider):
                    self.slider.setValue(value)


class Vec2Parameter(Parameter[Vec2]):
    def __init__(
        self,
        name: str,
        default: Vec2 | None = None,
        valueNames: tuple[str, str] = ("X", "Y"),
        description=None,
        parent=None,
    ):
        if default is None:
            default = Vec2.zero()
        super().__init__(name, default, description, parent)
        self.valueNames = valueNames

    def getWidget(self, parent=None) -> QWidget:
        return self.Vec2ParameterWidget(self, parent)

    def clone(self, parent=None) -> Vec2Parameter:
        return Vec2Parameter(
            self.name,
            self.default,
            self.valueNames,
            self.description,
            parent,
        )

    class Vec2ParameterWidget(QWidget):
        def __init__(self, param: "Vec2Parameter", parent=None):
            super().__init__(parent)
            self.param = param

            paramLayout = paramLayoutDefault()
            paramLayout.addWidget(QLabel(self.param.name))
            self.xSpinBox = QDoubleSpinBox(parent=self)
            self.xSpinBox.setRange(-100000, 100000)

            self.xSpinBox.setValue(self.param.get().x)
            self.xSpinBox.valueChanged.connect(self.onXChanged)
            paramLayout.addWidget(QLabel(self.param.valueNames[0]))
            paramLayout.addWidget(self.xSpinBox)

            self.ySpinBox = QDoubleSpinBox(parent=self)
            self.ySpinBox.setRange(-100000, 100000)
            self.ySpinBox.setValue(self.param.get().y)
            self.ySpinBox.valueChanged.connect(self.onYChanged)
            paramLayout.addWidget(QLabel(self.param.valueNames[1]))
            paramLayout.addWidget(self.ySpinBox)

            self.setLayout(paramLayout)

        def onXChanged(self, value):
            vec = self.param.get()
            vec.x = value
            self.param.set(vec)

        def onYChanged(self, value):
            vec = self.param.get()
            vec.y = value
            self.param.set(vec)


class StringParameter(Parameter[str]):
    def __init__(self, name: str, default: str = "", description=None, parent=None):
        super().__init__(name, default, description, parent)

    def getWidget(self, parent=None) -> QWidget:
        return self.StringParameterWidget(self, parent)

    def clone(self, parent=None) -> StringParameter:
        return StringParameter(
            name=self.name,
            default=self.default,
            description=self.description,
            parent=parent,
        )

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

    def clone(self, parent=None) -> BoolParameter:
        return BoolParameter(
            name=self.name,
            default=self.default,
            description=self.description,
            parent=parent,
        )

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


class EnumParameter(Parameter[Enum]):
    def __init__(
        self,
        name: str,
        enumType: Type[Enum],
        default: Enum | None = None,
        description=None,
        parent=None,
    ):
        # store the enum type so we can derive members and validation at runtime
        self.enumType = enumType
        if default is None:
            # pick the first enum member as default
            default = list(enumType)[0]
        if default not in enumType:
            raise ValueError("Default value must be a member of the enum")

        super().__init__(name, default, description, parent)

        self.enumNames: list[str] = []

        def makeUpper(match: re.Match[str]) -> str:
            return match.group().upper() if match.group() is not None else ""

        for enum in enumType:
            name = enum.name
            # convert snake_case and/or camelCase notation into space-seperated words.
            name = re.sub(r"_", r" ", name)
            name = re.sub(r"(?<=[a-z])(?=[A-Z]|[0-9])", r" ", name)
            # Make only the start of words be uppercase
            name = name.lower()
            name = re.sub(r"(?<=[ ])([a-z])", makeUpper, name)
            name = re.sub(r"^([a-z])", makeUpper, name)
            self.enumNames.append(name)

    def getWidget(self, parent=None) -> QWidget:
        return self.EnumParameterWidget(self, parent)

    def clone(self, parent=None) -> EnumParameter:
        return EnumParameter(
            self.name,
            self.enumType,
            self.default,
            self.description,
            parent,
        )

    class EnumParameterWidget(QWidget):
        def __init__(self, param: "EnumParameter", parent=None):
            super().__init__(parent)
            self.param = param
            self.comboBox = QComboBox(self)

            self.comboBox.addItems(param.enumNames)

            self.comboBox.setCurrentIndex(
                list(self.param.enumType).index(self.param.get())
            )
            self.comboBox.currentIndexChanged.connect(self.enumSelectionChanged)
            paramLayout = paramLayoutDefault()
            paramLayout.addWidget(self.comboBox)
            self.setLayout(paramLayout)

        def enumSelectionChanged(self, index):
            enumMember = list(self.param.enumType)[index]
            self.param.set(enumMember)


class ColorParameter(Parameter[QColor]):
    def __init__(
        self,
        name: str,
        default: QColor | str = QColor(255, 255, 255),
        description=None,
        parent=None,
    ):
        # convert string to QColor if needed, This way we can input hex strings like "#ff0000"
        if isinstance(default, str):
            default = QColor(default)
        super().__init__(name, default, description, parent)

    def getWidget(self, parent=None) -> QWidget:
        return self.ColorParameterWidget(self, parent)

    def clone(self, parent=None) -> ColorParameter:
        return ColorParameter(
            name=self.name,
            default=self.default,
            description=self.description,
            parent=parent,
        )

    class ColorParameterWidget(QWidget):
        def __init__(self, param: "ColorParameter", parent=None):
            super().__init__(parent)
            self.param = param
            self.param.sigParameterChanged.connect(self.onParamChanged)
            self.colorButton = QPushButton(self)
            self.colorButton.setFixedSize(40, 40)
            self.updateColorDisplay()
            self.colorButton.clicked.connect(self.openColorDialog)

            paramLayout = paramLayoutDefault()
            paramLayout.addWidget(self.colorButton)
            self.setLayout(paramLayout)

        def updateColorDisplay(self):
            color = self.param.get()
            self.colorButton.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid #000000; border-radius: 4px;"
            )

        def openColorDialog(self):
            color = QColorDialog.getColor(self.param.get(), self, "Select Color")
            if color.isValid():
                self.param.set(color)
                self.updateColorDisplay()

        @pyqtSlot(object)
        def onParamChanged(self, color: QColor):
            self.updateColorDisplay()


class ImageParameter(Parameter[Image]):
    """
    Parameter that allows selection from a list of images.
    For now it just displays the name, but in the future it could potentially show image previews or maybe filtering options.

    This parameter works different, because it needs a list of images to work with, which is only known at runtime.
    So, the parameter must be manually given a callable "image provider" after initialization, but before use.
    """

    def __init__(self, name: str, description=None, parent=None) -> None:
        self.imageProvider: Callable[[], list[Image]] = lambda: []
        default = None
        super().__init__(name, default, description, parent)

    def setProvider(self, imageProvider: Callable[[], list[Image]]) -> None:
        """
        Sets the callable image provider that returns the list of images to choose from.
        This must be set before using the parameter for anything else.
        """
        self.imageProvider = imageProvider
        images = imageProvider()
        if len(images) > 0:
            self.set(images[0])

    def getWidget(self, parent=None) -> QWidget:
        return self.ImageParameterWidget(self, parent)

    def clone(self, parent=None) -> ImageParameter:
        newParam = ImageParameter(self.name, self.description, parent)
        newParam.setProvider(self.imageProvider)
        return newParam

    class ImageParameterWidget(QWidget):
        def __init__(self, param: "ImageParameter", parent=None):
            super().__init__(parent)
            self.param = param
            self.imageList = param.imageProvider()
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
            if len(self.imageList) == 0:
                # do nothing if the list is empty. This might happen if user selects the "No Images Available!" item.
                return
            self.param.set(self.imageList[index])


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
    from varda.utilities import debug

    qapp = QApplication([])

    layout = QVBoxLayout()

    intParam0 = IntParameter("test", 10, (0, 100), "test units", "A test int parameter")
    floatParam0 = FloatParameter(
        "FloatVal",
        15.15,
        (0, 100),
        "floating units",
        "A test float parameter",
    )
    boolParam0 = BoolParameter("BoolVal", True, "A test bool parameter")
    stringParam0 = StringParameter(
        "StringVal", "default text", "A test string parameter"
    )
    imageParam0 = ImageParameter(
        "ImageVal",
        lambda: [debug.generate_random_image(), debug.generate_random_image()],
        "A test image parameter",
    )

    class TestEnum(Enum):
        OPTION_A = 1
        OPTION_B = 2
        OPTION_C = 3

    class TestEnum2(Enum):
        OPTION_X = "x"
        OPTION_Y = "y"
        OPTION_Z = "z"

    enumParam0 = EnumParameter(
        "EnumVal",
        TestEnum,
        TestEnum.OPTION_C,
        "A test enum parameter",
    )

    paramGroup = ParameterGroupWidget(
        [intParam0, floatParam0, boolParam0, stringParam0, imageParam0, enumParam0]
    )
    paramGroup.sigParameterChanged.connect(
        lambda: print("Parameter Group Changed:", paramGroup)
    )
    layout.addWidget(paramGroup)

    w = QWidget()
    w.setLayout(layout)
    w.show()
    sys.exit(qapp.exec())
