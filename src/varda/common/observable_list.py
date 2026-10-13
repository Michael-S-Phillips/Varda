from abc import ABCMeta
from collections.abc import Iterable, Iterator, MutableSequence
from typing import overload

from PyQt6.QtCore import QObject, pyqtSignal


class _QObjectSequenceMeta(ABCMeta, type(QObject)):
    """Lets a QObject also be a ``MutableSequence``."""


class ObservableList[T](QObject, MutableSequence[T], metaclass=_QObjectSequenceMeta):
    """A list that emits ``sigDataChanged`` (with a copy of its items) on
    every change. It is a ``MutableSequence``, so it can go wherever a
    sequence of items is expected."""

    sigDataChanged: pyqtSignal = pyqtSignal(list)

    def __init__(self, items: Iterable[T] | None = None):
        super().__init__()
        self._items: list[T] = list(items) if items else []

    def _changed(self) -> None:
        self.sigDataChanged.emit(self._items.copy())

    @overload
    def __getitem__(self, index: int) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> list[T]: ...
    def __getitem__(self, index: int | slice) -> T | list[T]:
        return self._items[index]

    @overload
    def __setitem__(self, index: int, item: T) -> None: ...
    @overload
    def __setitem__(self, index: slice, item: Iterable[T]) -> None: ...
    def __setitem__(self, index, item) -> None:
        self._items[index] = item
        self._changed()

    def __delitem__(self, index: int | slice) -> None:
        del self._items[index]
        self._changed()

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def insert(self, index: int, item: T) -> None:
        self._items.insert(index, item)
        self._changed()

    def append(self, item: T) -> None:
        self._items.append(item)
        self._changed()

    def extend(self, items: Iterable[T]) -> None:
        self._items.extend(items)
        self._changed()

    def remove(self, item: T) -> None:
        self._items.remove(item)
        self._changed()

    def pop(self, index: int = -1) -> T:
        item = self._items.pop(index)
        self._changed()
        return item

    def clear(self) -> None:
        self._items.clear()
        self._changed()
