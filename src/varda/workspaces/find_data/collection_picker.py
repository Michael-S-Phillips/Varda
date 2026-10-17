"""The collection picker: a combo box whose drop-down is a search field over
a tree of the collections, by body and then by group (mission and
instrument, for ODE). Every word typed must appear in a collection's body,
group, title, id or description ("mars crism", "kaguya dtm")."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from attrs import evolve

from PyQt6.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QPoint,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QKeyEvent, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLineEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from varda.catalogs.catalog import Collection
from varda.common.ui import ElidingComboBox, MutedLabel

SEARCH_ROLE = Qt.ItemDataRole.UserRole + 1  # the text words are matched in
INDEX_ROLE = Qt.ItemDataRole.UserRole + 2  # the collection's index in the combo
POPUP_WIDTH, POPUP_HEIGHT = 520, 440


def distinctTitles(collections: Sequence[Collection]) -> list[Collection]:
    """The collections, with the id's last part added to any title its body
    shares with another collection (a catalog's test copy, say), so they can
    be told apart."""
    counts = Counter((c.body, c.title) for c in collections)
    return [
        evolve(c, title=f"{c.title} [{c.id.rsplit('#', 1)[-1]}]")
        if counts[(c.body, c.title)] > 1
        else c
        for c in collections
    ]


def searchText(collection: Collection) -> str:
    return " ".join(
        (
            collection.body,
            collection.group,
            collection.title,
            collection.id,
            collection.description,
        )
    ).lower()


def _leafCount(item: QStandardItem) -> int:
    children = [item.child(r) for r in range(item.rowCount())]
    return sum(
        _leafCount(c) if c.data(INDEX_ROLE) is None else 1 for c in children if c
    )


class _WordFilter(QSortFilterProxyModel):
    """Keeps the collections whose text holds every word (groups show while
    any collection in them does)."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.words: list[str] = []
        self.setRecursiveFilteringEnabled(True)

    def setWords(self, text: str) -> None:
        self.words = text.lower().split()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N803 (Qt's names)
        model = self.sourceModel()
        assert model is not None
        text = model.index(source_row, 0, source_parent).data(SEARCH_ROLE)
        if text is None:  # a body or group: shown for its collections
            return not self.words
        return all(word in text for word in self.words)


class CollectionPopup(QFrame):
    """The drop-down: a search field over the collection tree."""

    sigChosen = pyqtSignal(int)  # the collection's index in the combo

    def __init__(
        self, collections: Sequence[Collection], current: int, parent: QWidget
    ):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search body, mission, instrument, product…")
        self.search.setClearButtonEnabled(True)
        self.model = QStandardItemModel(self)
        self.proxy = _WordFilter(self)
        self.proxy.setSourceModel(self.model)
        self.tree = QTreeView()
        self.tree.setModel(self.proxy)
        self.tree.setHeaderHidden(True)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setUniformRowHeights(True)
        self.count = MutedLabel("")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.search)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.count)
        self._fill(collections, current)
        self.search.textChanged.connect(self._onSearch)
        self.search.installEventFilter(self)
        self.tree.activated.connect(self._choose)
        self.tree.clicked.connect(self._choose)
        self._onSearch("")

    def _fill(self, collections: Sequence[Collection], current: int) -> None:
        nodes: dict[tuple[str, ...], QStandardItem] = {}

        def node(*path: str) -> QStandardItem:
            if path not in nodes:
                item = QStandardItem(path[-1])
                item.setSelectable(False)
                parent = (
                    node(*path[:-1])
                    if len(path) > 1
                    else self.model.invisibleRootItem()
                )
                parent.appendRow(item)
                nodes[path] = item
            return nodes[path]

        self.currentItem: QStandardItem | None = None
        for index, collection in enumerate(collections):
            body = collection.body or "Other"
            parent = node(body, collection.group) if collection.group else node(body)
            title = collection.title
            if collection.group and title.startswith(collection.group + " "):
                title = title[len(collection.group) + 1 :]  # "MRO CRISM" says it
            item = QStandardItem(title)
            item.setData(searchText(collection), SEARCH_ROLE)
            item.setData(index, INDEX_ROLE)
            item.setToolTip(collection.description or collection.title)
            parent.appendRow(item)
            if index == current:
                self.currentItem = item
        self.total = len(collections)
        for item in nodes.values():  # "MRO CRISM (8)"
            item.setText(f"{item.text()} ({_leafCount(item)})")

    def _leaves(self, parent: QModelIndex = QModelIndex()) -> list[QModelIndex]:
        found = []
        for row in range(self.proxy.rowCount(parent)):
            index = self.proxy.index(row, 0, parent)
            if index.data(INDEX_ROLE) is not None:
                found.append(index)
            else:
                found += self._leaves(index)
        return found

    def _onSearch(self, text: str) -> None:
        self.proxy.setWords(text)
        leaves = self._leaves()
        if text.strip():
            self.tree.expandAll()
            if leaves:
                self.tree.setCurrentIndex(leaves[0])
        else:
            self.tree.collapseAll()
            if self.currentItem is not None:
                current = self.proxy.mapFromSource(self.currentItem.index())
                self.tree.setCurrentIndex(current)
                self.tree.scrollTo(current)
        shown = len(leaves)
        self.count.setText(
            f"{self.total} collections"
            if shown == self.total
            else f"{shown} of {self.total} collections"
        )

    def _choose(self, index: QModelIndex) -> None:
        chosen = index.data(INDEX_ROLE)
        if chosen is None:  # a body or group opens and closes
            self.tree.setExpanded(index, not self.tree.isExpanded(index))
            return
        self.sigChosen.emit(int(chosen))
        self.close()

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        """Up, Down and Enter in the search field move through the tree."""
        if (
            watched is self.search
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
        ):
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._choose(self.tree.currentIndex())
                return True
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                leaves = self._leaves() if self.search.text().strip() else []
                if leaves:
                    rows = [i.data(INDEX_ROLE) for i in leaves]
                    current = self.tree.currentIndex().data(INDEX_ROLE)
                    at = rows.index(current) if current in rows else -1
                    at = max(
                        0,
                        min(
                            len(leaves) - 1, at + (1 if key == Qt.Key.Key_Down else -1)
                        ),
                    )
                    self.tree.setCurrentIndex(leaves[at])
                else:
                    self.tree.keyPressEvent(event)
                return True
        return super().eventFilter(watched, event)


class CollectionCombo(ElidingComboBox):
    """A combo box of collections (``setCollections``) that drops down the
    searchable tree instead of a plain list. A long name is elided, and
    shown in full in the tooltip."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.collections: list[Collection] = []
        self.popup: CollectionPopup | None = None

    def setCollections(
        self, collections: Sequence[Collection], select: str = ""
    ) -> None:
        """Fill it ("Body: title" items holding the ids), choosing ``select``
        (or the first), without signals until the end."""
        self.collections = distinctTitles(collections)
        self.blockSignals(True)
        self.clear()
        for c in self.collections:
            self.addItem(f"{c.body}: {c.title}", c.id)
            self.setItemData(
                self.count() - 1, c.description, Qt.ItemDataRole.ToolTipRole
            )
        index = self.findData(select) if select else -1
        self.setCurrentIndex(max(index, 0))
        self.blockSignals(False)

    def showPopup(self) -> None:
        if not self.collections:
            return
        self.popup = CollectionPopup(self.collections, self.currentIndex(), self)
        self.popup.sigChosen.connect(self.setCurrentIndex)
        width = max(self.width(), POPUP_WIDTH)
        self.popup.resize(width, POPUP_HEIGHT)
        self.popup.move(self.mapToGlobal(QPoint(0, self.height())))
        self.popup.show()
        self.popup.search.setFocus()

    def hidePopup(self) -> None:
        if self.popup is not None:
            self.popup.close()
            self.popup = None
