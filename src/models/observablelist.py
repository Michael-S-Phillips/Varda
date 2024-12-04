from PyQt6.QtCore import QObject, pyqtSignal


class ObservableList(QObject):
    listChanged = pyqtSignal()

    def __init__(self, initial=None):
        super().__init__()
        self._data = list(initial) if initial else []

    def __getitem__(self, index):
        return self._data[index]

    def __setitem__(self, index, value):
        self._data[index] = value
        self.listChanged.emit()

    def __len__(self):
        return len(self._data)

    def append(self, value):
        self._data.append(value)
        self.listChanged.emit()

    def remove(self, value):
        self._data.remove(value)
        self.listChanged.emit()

    # Add other list-like methods as needed...
