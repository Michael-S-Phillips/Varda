"""The download list: each product with its files (the essential ones
checked), the total size, the folder, and the queue that downloads them one
product after another. Finished products open in Varda when asked."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from pathlib import Path

from attrs import define, field
from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from varda.catalogs.catalog import Catalog, CatalogError, Product, RemoteFile
from varda.catalogs.downloads import (
    IncompleteDownload,
    downloadProduct,
    exportList,
    productFolder,
)
from varda.image_loading.data_sources.registry import datasource_registry
from varda.utilities.background import onMainThread, runInBackground

FOLDER_KEY = "catalogs/downloadFolder"
ROLE_ORDER = ("data", "label", "auxiliary", "browse")
ROLE_NAMES = {
    "data": "Data files",
    "label": "Labels",
    "auxiliary": "Auxiliary files",
    "browse": "Browse images",
}
NAME_WIDTH = 360  # the file column's starting width (it can be dragged wider)
WAITING, LISTING, DOWNLOADING, DONE, FAILED = (
    "Waiting",
    "Listing files…",
    "Downloading",
    "Done",
    "Failed",
)


def defaultFolder() -> Path:
    return Path(str(QSettings().value(FOLDER_KEY, "") or Path.home() / "Varda Data"))


def formatBytes(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1000:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1000
    return f"{size:.1f} TB"


def openableFiles(paths: Sequence[Path]) -> list[Path]:
    """The downloaded files Varda can open, one per file stem: where a
    reader takes several extensions (ENVI's .hdr and .img), the one it lists
    first. A file its reader declines is skipped, so a PDS product opens
    through its label rather than its raw data file."""
    best: dict[str, tuple[int, Path]] = {}
    for path in paths:
        rank = _openRank(path)
        if rank is None:
            continue
        stem = str(path.with_suffix("")).lower()
        if stem not in best or rank < best[stem][0]:
            best[stem] = (rank, path)
    return [path for _, path in best.values()]


def _openRank(path: Path) -> int | None:
    """Where ``path``'s extension sits in the first reader that takes it, or
    None if no reader does."""
    extension = path.suffix.lower()
    for entry in datasource_registry:
        if extension not in entry.fileExtensions:
            continue
        canOpen = getattr(entry.dataSourceClass, "canOpen", None)
        if canOpen is None or canOpen(str(path)):
            return entry.fileExtensions.index(extension)
    return None


@define(eq=False)
class Queued:
    catalog: Catalog
    product: Product
    files: list[RemoteFile] = field(factory=list)
    chosen: set[str] = field(factory=set)  # file names to download
    status: str = LISTING
    item: QTreeWidgetItem | None = None


class DownloadsPanel(QWidget):
    sigOpen = pyqtSignal(list)  # paths of finished downloads to open

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.queue: list[Queued] = []
        self._cancel: threading.Event | None = None
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Product / file", "Size", "Status"])
        header = self.tree.header()
        assert header is not None
        # every column can be dragged wider; long names scroll sideways
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.resizeSection(0, NAME_WIDTH)
        self.tree.setTextElideMode(Qt.TextElideMode.ElideMiddle)  # keep the suffix
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.itemChanged.connect(self._onItemChanged)
        self.total = QLabel()
        self.folder = QLineEdit(str(defaultFolder()))
        self.folder.editingFinished.connect(
            lambda: QSettings().setValue(FOLDER_KEY, self.folder.text())
        )
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        self.openWhenDone = QCheckBox("Open in Varda when done")
        self.openWhenDone.setChecked(True)
        self.downloadButton = QPushButton("Download")
        self.downloadButton.setToolTip(
            "Download the selected products, or every one not downloaded yet"
        )
        self.downloadButton.clicked.connect(self.download)
        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.clicked.connect(self.cancel)
        self.cancelButton.setEnabled(False)
        checkButton = QToolButton()
        checkButton.setText("Check")
        checkButton.setToolTip(
            "Check files in the selected products (or in all of them): all, the "
            "essential ones, none, or every file of a type"
        )
        checkButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        checkMenu = QMenu(checkButton)
        checkMenu.addAction("All Files", lambda: self.checkFiles(lambda f: True))
        checkMenu.addAction(
            "Essential Files Only", lambda: self.checkFiles(lambda f: f.essential)
        )
        checkMenu.addAction("None", lambda: self.checkFiles(lambda f: False))
        checkMenu.addSection("Add every file of a type")
        for role, name in ROLE_NAMES.items():
            checkMenu.addAction(
                name,
                lambda role=role: self.checkFiles(lambda f: f.role == role, add=True),
            )
        checkButton.setMenu(checkMenu)
        selectButton = QToolButton()
        selectButton.setText("Select")
        selectButton.setToolTip("Select products, e.g. the failed ones to retry")
        selectButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        selectMenu = QMenu(selectButton)
        selectMenu.addAction(
            "All Products", lambda: self.selectProducts(lambda s: True)
        )
        selectMenu.addSection("By status")
        for status in (WAITING, DONE, FAILED):
            selectMenu.addAction(
                status,
                lambda status=status: self.selectProducts(
                    lambda s: s.startswith(status)
                ),
            )
        selectButton.setMenu(selectMenu)
        remove = QPushButton("Remove")
        remove.setToolTip("Take the selected products off the list")
        remove.clicked.connect(self._removeSelected)
        export = QPushButton("Export List…")
        export.setToolTip(
            "Save the list as a CSV, or as a script of resumable curl commands"
        )
        export.clicked.connect(self._export)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.status = QLabel()
        self.status.setWordWrap(True)

        folderRow = QHBoxLayout()
        folderRow.addWidget(QLabel("Folder:"))
        folderRow.addWidget(self.folder, 1)
        folderRow.addWidget(browse)
        buttons = QHBoxLayout()
        for button in (
            self.downloadButton,
            self.cancelButton,
            checkButton,
            selectButton,
            remove,
            export,
        ):
            buttons.addWidget(button)
        buttons.addStretch()
        totalRow = QHBoxLayout()
        totalRow.addWidget(self.total, 1)
        totalRow.addWidget(self.openWhenDone)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tree, 1)
        layout.addLayout(totalRow)
        layout.addLayout(folderRow)
        layout.addLayout(buttons)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        self._showTotal()

    # --- the list ------------------------------------------------------------------------

    def add(self, catalog: Catalog, products: Sequence[Product]) -> None:
        """Queue products; their files are listed in the background."""
        known = {(q.catalog.catalogId, q.product.id) for q in self.queue}
        for product in products:
            if (catalog.catalogId, product.id) in known:
                continue
            queued = Queued(catalog, product)
            queued.item = QTreeWidgetItem(self.tree, [product.id, "", LISTING])
            self.queue.append(queued)
            runInBackground(
                lambda queued=queued: queued.catalog.files(queued.product),
                lambda files, queued=queued: self._listed(queued, files),
                lambda error, queued=queued: self._setStatus(
                    queued, f"{FAILED}: {error}"
                ),
                description="Listing a product's files",
                owner=self,
            )

    def _listed(self, queued: Queued, files: list[RemoteFile]) -> None:
        if queued not in self.queue or queued.item is None:
            return
        queued.files = files
        queued.chosen = {f.name for f in files if f.essential}
        self.tree.blockSignals(True)
        # what's checked first, then by role (data, label, …)
        for file in sorted(
            files,
            key=lambda f: (
                not f.essential,
                ROLE_ORDER.index(f.role) if f.role in ROLE_ORDER else len(ROLE_ORDER),
            ),
        ):
            child = QTreeWidgetItem(
                queued.item, [file.name, self._size(file), file.role]
            )
            child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            child.setCheckState(
                0,
                Qt.CheckState.Checked
                if file.name in queued.chosen
                else Qt.CheckState.Unchecked,
            )
            child.setData(0, Qt.ItemDataRole.UserRole, file.name)
            child.setToolTip(0, file.name)
        self.tree.blockSignals(False)
        self._setStatus(queued, WAITING)

    def _scope(self) -> list[Queued]:
        """The selected products (a selected file counts for its product), or
        all of them."""
        tops = {
            id(item if item.parent() is None else item.parent())
            for item in self.tree.selectedItems()
        }
        chosen = [q for q in self.queue if id(q.item) in tops]
        return chosen or list(self.queue)

    def checkFiles(self, which, add: bool = False) -> None:
        """Check the files ``which`` accepts in the selected products (or
        all); with ``add``, the others keep their checks."""
        for queued in self._scope():
            if queued.status.startswith(DOWNLOADING) or queued.item is None:
                continue
            picked = {f.name for f in queued.files if which(f)}
            queued.chosen = queued.chosen | picked if add else picked
            self.tree.blockSignals(True)
            for row in range(queued.item.childCount()):
                child = queued.item.child(row)
                if child is not None:
                    name = child.data(0, Qt.ItemDataRole.UserRole)
                    child.setCheckState(
                        0,
                        Qt.CheckState.Checked
                        if name in queued.chosen
                        else Qt.CheckState.Unchecked,
                    )
            self.tree.blockSignals(False)
            self._setStatus(queued, queued.status)

    def selectProducts(self, which) -> None:
        """Select the products whose status ``which`` accepts."""
        self.tree.clearSelection()
        for queued in self.queue:
            if queued.item is not None and which(queued.status):
                queued.item.setSelected(True)

    def _size(self, file: RemoteFile) -> str:
        if file.size is None:
            return "?"
        return ("≈ " if not file.exactSize else "") + formatBytes(file.size)

    def _onItemChanged(self, item: QTreeWidgetItem, column: int) -> None:
        parent = item.parent()
        if parent is None or column != 0:
            return
        queued = next((q for q in self.queue if q.item is parent), None)
        if queued is None:
            return
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if item.checkState(0) == Qt.CheckState.Checked:
            queued.chosen.add(name)
        else:
            queued.chosen.discard(name)
        self._showTotal()

    def _setStatus(self, queued: Queued, status: str) -> None:
        queued.status = status
        if queued.item is not None:
            queued.item.setText(2, status)
            queued.item.setToolTip(2, status)  # a failure's whole reason
            chosen = [f for f in queued.files if f.name in queued.chosen]
            sizes = [f.size for f in chosen if f.size is not None]
            queued.item.setText(1, formatBytes(sum(sizes)) if sizes else "")
        self._showTotal()

    def chosenFiles(self, queued: Queued) -> list[RemoteFile]:
        return [f for f in queued.files if f.name in queued.chosen]

    def _showTotal(self) -> None:
        files = [f for q in self.queue if q.status != DONE for f in self.chosenFiles(q)]
        sizes = [f.size for f in files if f.size is not None]
        approximate = any(not f.exactSize for f in files) or len(sizes) < len(files)
        unknown = len(files) - len(sizes)
        text = f"{len(files)} files, {'about ' if approximate else ''}{formatBytes(sum(sizes))}"
        if unknown:
            text += f" ({unknown} of unknown size)"
        if not files:
            text = (
                "Everything on the list is downloaded."
                if self.queue and all(q.status == DONE for q in self.queue)
                else "Nothing to download yet: check products in the results and add them."
            )
        self.total.setText(text)

    def _removeSelected(self) -> None:
        for item in self.tree.selectedItems():
            top = item if item.parent() is None else item.parent()
            queued = next((q for q in self.queue if q.item is top), None)
            if queued is not None and not queued.status.startswith(DOWNLOADING):
                self.queue.remove(queued)
                self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(top))
        self._showTotal()

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Download Folder", self.folder.text()
        )
        if folder:
            self.folder.setText(folder)
            QSettings().setValue(FOLDER_KEY, folder)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Download List",
            "varda-downloads.csv",
            "CSV (*.csv);;Shell script (*.sh)",
        )
        if path:
            self.exportTo(Path(path))

    def exportTo(self, path: Path) -> None:
        entries = [
            (q.catalog.catalogId, q.product, self.chosenFiles(q)) for q in self.queue
        ]
        try:
            exportList(entries, path, Path(self.folder.text()))
        except OSError as error:
            self.status.setText(f"Varda couldn't save the list: {error}")
            return
        self.status.setText(f"Saved the list to {path}.")

    # --- downloading -------------------------------------------------------------------------

    def download(self) -> None:
        """The selected products, or every one still to download."""
        todo = [
            (q, self.chosenFiles(q))
            for q in self._scope()
            if q.chosen and (q.status == WAITING or q.status.startswith(FAILED))
        ]
        if not todo:
            self.status.setText("Nothing to download: check some files first.")
            return
        root = Path(self.folder.text())
        self._cancel = cancel = threading.Event()
        self.downloadButton.setEnabled(False)
        self.cancelButton.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        report = onMainThread(self._progress)
        finished = onMainThread(self._finishedOne)

        def task() -> int:
            done = 0
            for index, (queued, files) in enumerate(todo):
                if cancel.is_set():
                    break
                report(queued, index, len(todo), 0.0, "starting")
                try:
                    paths = downloadProduct(
                        files,
                        productFolder(root, queued.catalog.catalogId, queued.product),
                        lambda fraction, message, queued=queued, index=index: report(
                            queued, index, len(todo), fraction, message
                        ),
                        cancel,
                        queued.catalog.requestHeaders(),
                        catalog=queued.catalog.name,
                        product=queued.product,
                    )
                except IncompleteDownload as error:
                    # the files that exist were downloaded; say which didn't
                    finished(queued, [], str(error), error.failures)
                    continue
                except CatalogError as error:
                    # a cancel stops mid-file: the product just waits again
                    finished(queued, [], WAITING if cancel.is_set() else str(error), [])
                    continue
                # only data files open (not browse images, which Varda could
                # read), and only with every essential file (a header needs its cube)
                complete = all(f in files for f in queued.files if f.essential)
                dataNames = {f.name for f in files if f.role == "data"}
                data = [p for p in paths if p.name in dataNames]
                finished(queued, data if complete else [], "", [])
                done += 1
            return done

        runInBackground(
            task,
            self._allDone,
            self._failed,
            description="Downloading data",
            owner=self,
        )

    def _progress(
        self, queued: Queued, index: int, count: int, fraction: float, message: str
    ) -> None:
        self._setStatus(queued, f"{DOWNLOADING} {int(100 * fraction)}%")
        self.progress.setValue(int(100 * (index + fraction) / count))
        self.status.setText(f"{queued.product.id}: {message}")

    def _finishedOne(
        self, queued: Queued, paths: list[Path], error: str, failures: list[str]
    ) -> None:
        if queued.item is not None:
            for row in range(queued.item.childCount()):
                child = queued.item.child(row)
                if child is None:
                    continue
                name = child.data(0, Qt.ItemDataRole.UserRole)
                reason = next((f for f in failures if f.startswith(f"{name}:")), "")
                role = next((f.role for f in queued.files if f.name == name), "")
                child.setText(2, f"{role}: not downloaded" if reason else role)
                child.setToolTip(2, reason)
        if error:
            self._setStatus(queued, error if error == WAITING else f"{FAILED}: {error}")
            return
        self._setStatus(queued, DONE)
        if self.openWhenDone.isChecked():
            openable = openableFiles(paths)
            if openable:
                self.sigOpen.emit(openable)

    def _allDone(self, done: int) -> None:
        canceled = self._cancel is not None and self._cancel.is_set()
        self.downloadButton.setEnabled(True)
        self.cancelButton.setEnabled(False)
        self.progress.setVisible(False)
        self._cancel = None
        failed = sum(q.status.startswith(FAILED) for q in self.queue)
        if canceled:
            text = f"Canceled after {done} products; a partial file resumes next time."
        else:
            text = f"{done} products downloaded to {self.folder.text()}."
        if failed:
            text += f" {failed} failed: see their status, then Download to retry."
        self.status.setText(text)

    def _failed(self, error: Exception) -> None:
        self._allDone(0)
        self.status.setText(f"The downloads stopped: {error}")

    def cancel(self) -> None:
        if self._cancel is not None:
            self._cancel.set()
            self.status.setText("Canceling after the current file…")
