# standard library
from dataclasses import dataclass
import logging

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal

# local imports
from .observablelist import ObservableList

logger = logging.getLogger(__name__)


class Parameter(QObject):
    def __init__(self, name, values):
        super().__init__()
        self._name = name
        self._values = values

    parameterChanged = pyqtSignal(str, dict)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self.parameterChanged.emit()

    @property
    def values(self):
        return self._values

    @values.setter
    def values(self, value):
        self._values = value
        self.parameterChanged.emit()

    def __str__(self):
        return f"{self.name}: {self.values}"


class ParameterModel(QObject):
    """
    A model to hold a list of parameter configurations.
    """

    dataChanged = pyqtSignal()  # signal to emit when data is changed

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self._header = data.keys()

        self._data = ObservableList()

        for name, values in data.items():
            parameter = Parameter(name, values)
            logger.debug(f"Created parameter. {parameter}")
            self._data.append(parameter)
            parameter.parameterChanged.connect(self.dataChanged.emit)

    def rowCount(self) -> int:
        return len(self._data)

    @property
    def data(self):
        return self._data

    def __iter__(self):
        """
        magic method to allow iterating over the data
        Returns:
        """
        for param in self._data.items():
            yield param
