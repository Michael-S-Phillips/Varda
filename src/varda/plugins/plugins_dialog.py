"""Plugins → Manage Plugins: what's installed, what each adds, and why one
didn't load; enable, disable, reload, remove and install."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from varda.analysis.analysis import categoryTitle
from varda.common.ui import MutedLabel
from varda.plugins.manifest import PluginError
from varda.plugins.plugin_manager import INSTALLED, PluginRecord, VardaPluginManager

COLUMNS = ("Plugin", "Version", "Status", "Adds", "Source")
TRUST_NOTE = (
    "Plugins are Python code that runs inside Varda with your permissions. "
    "Install only plugins you trust, and read a plugin's code if unsure."
)


def describeContributions(record: PluginRecord) -> str:
    analyses = record.contributions.analyses
    formats = record.contributions.dataSources
    parts = []
    if analyses:
        parts.append(
            ", ".join(
                f"{a.name.rstrip(' .…')} (Processing → {categoryTitle(a.category)})"
                for a in analyses
            )
        )
    if formats:
        parts.append(", ".join(f"{name} files" for name, _exts, _cls in formats))
    return "; ".join(parts)


def status(record: PluginRecord) -> str:
    if record.error:
        return f"Not loaded: {record.error}"
    if not record.enabled:
        return "Disabled"
    return "Enabled" if record.loaded else "Not loaded"


def installPlugin(
    manager: VardaPluginManager, path: Path, parent: QWidget | None
) -> PluginRecord | None:
    """Install from a folder or zip, offering to replace an existing copy, and
    tell the user what it added or why it failed."""
    try:
        try:
            record = manager.install(path)
        except PluginError as error:
            if "already installed" not in str(error):
                raise
            answer = QMessageBox.question(
                parent, "Replace Plugin", f"{error}\n\nReplace it with this copy?"
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None
            record = manager.install(path, replace=True)
    except PluginError as error:
        QMessageBox.warning(parent, "Install Plugin", str(error))
        return None
    if record.error:
        QMessageBox.warning(
            parent,
            "Install Plugin",
            f"{record.name} was installed but didn't load:\n{record.error}",
        )
    else:
        adds = describeContributions(record) or "nothing visible yet"
        QMessageBox.information(
            parent,
            "Install Plugin",
            f"Installed {record.name} {record.version}.\nAdds: {adds}\n\n"
            "Plugin features are also listed at the bottom of the Plugins menu.",
        )
    return record


def chooseFolder(parent: QWidget | None) -> Path | None:
    folder = QFileDialog.getExistingDirectory(parent, "Install Plugin from Folder")
    return Path(folder) if folder else None


def chooseZip(parent: QWidget | None) -> Path | None:
    path, _ = QFileDialog.getOpenFileName(
        parent, "Install Plugin from Zip", "", "Plugin zip (*.zip)"
    )
    return Path(path) if path else None


class ManagePluginsDialog(QDialog):
    def __init__(self, manager: VardaPluginManager, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Manage Plugins")
        self.resize(820, 380)
        self.manager = manager

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._updateButtons)

        self.toggleButton = QPushButton("Disable")
        self.reloadButton = QPushButton("Reload")
        self.removeButton = QPushButton("Remove…")
        self.folderButton = QPushButton("Open Folder")
        installFolder = QPushButton("Install from Folder…")
        installZip = QPushButton("Install from Zip…")
        self.toggleButton.clicked.connect(self._toggle)
        self.reloadButton.clicked.connect(self._reload)
        self.removeButton.clicked.connect(self._remove)
        self.folderButton.clicked.connect(self._openFolder)
        installFolder.clicked.connect(lambda: self._install(chooseFolder(self)))
        installZip.clicked.connect(lambda: self._install(chooseZip(self)))

        buttons = QHBoxLayout()
        for button in (
            self.toggleButton,
            self.reloadButton,
            self.removeButton,
            self.folderButton,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(installFolder)
        buttons.addWidget(installZip)
        note = MutedLabel(TRUST_NOTE)
        note.setWordWrap(True)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        layout.addWidget(note)
        layout.addWidget(close)
        self.refresh()

    def refresh(self) -> None:
        selected = self.selectedRecord()
        records = self.manager.records
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = (
                record.name,
                record.version,
                status(record),
                describeContributions(record),
                record.source,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        if selected is not None and selected in records:
            self.table.selectRow(records.index(selected))
        self._updateButtons()

    def selectedRecord(self) -> PluginRecord | None:
        rows = {index.row() for index in self.table.selectedIndexes()}
        if len(rows) != 1:
            return None
        row = rows.pop()
        records = self.manager.records
        return records[row] if row < len(records) else None

    def _updateButtons(self) -> None:
        record = self.selectedRecord()
        installed = record is not None and record.source == INSTALLED
        self.toggleButton.setEnabled(installed)
        self.toggleButton.setText(
            "Enable" if record is not None and not record.enabled else "Disable"
        )
        self.reloadButton.setEnabled(installed)
        self.removeButton.setEnabled(installed)
        self.folderButton.setEnabled(record is not None and record.folder is not None)

    def _toggle(self) -> None:
        record = self.selectedRecord()
        if record is not None:
            self.manager.setEnabled(record.name, not record.enabled)
            self.refresh()

    def _reload(self) -> None:
        record = self.selectedRecord()
        if record is not None:
            self.manager.reload(record.name)
            self.refresh()

    def _remove(self) -> None:
        record = self.selectedRecord()
        if record is None:
            return
        answer = QMessageBox.question(
            self, "Remove Plugin", f"Remove {record.name} and delete its folder?"
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.manager.remove(record.name)
            self.refresh()

    def _openFolder(self) -> None:
        record = self.selectedRecord()
        if record is not None and record.folder is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(record.folder)))

    def _install(self, path: Path | None) -> None:
        if path is not None and installPlugin(self.manager, path, self) is not None:
            self.refresh()
