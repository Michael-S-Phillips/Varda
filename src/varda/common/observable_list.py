from PyQt6.QtCore import QObject, pyqtSignal


class ObservableList(QObject):
    sigDataChanged: pyqtSignal = pyqtSignal(list)

    def __init__(self, items=None):
        super().__init__()
        self._items = list(items) if items else []

    def __getitem__(self, index):
        return self._items[index]

    def __setitem__(self, index, item):
        self._items[index] = item
        self.sigDataChanged.emit(self._items.copy())

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def append(self, item):
        self._items.append(item)
        self.sigDataChanged.emit(self._items.copy())

    def extend(self, items):
        items = list(items)
        self._items.extend(items)
        self.sigDataChanged.emit(self._items.copy())

    def insert(self, index, item):
        self._items.insert(index, item)
        self.sigDataChanged.emit(self._items.copy())

    def remove(self, item):
        index = self._items.index(item)
        del self._items[index]
        self.sigDataChanged.emit(self._items.copy())

    def pop(self, index=-1):
        item = self._items.pop(index)
        self.sigDataChanged.emit(self._items.copy())
        return item

    def clear(self):
        self._items.clear()
        self.sigDataChanged.emit(self._items.copy())


class ImageList(ObservableList):
    """Typed ObservableList for VardaRaster images, used as DI injection type."""

    pass
