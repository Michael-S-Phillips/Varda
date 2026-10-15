"""A catalog's login, and the list of STAC APIs the STAC catalog searches
(saved in Varda's settings)."""

from __future__ import annotations

import json

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from varda.catalogs.catalog import Catalog, CatalogError
from varda.catalogs.credentials import forgetCredentials, isSecret, saveCredentials
from varda.catalogs.stac import DEFAULT_APIS, StacApi, StacCatalog
from varda.common.ui import MutedLabel

STAC_APIS_KEY = "catalogs/stacApis"


def savedStacApis() -> tuple[StacApi, ...]:
    try:
        saved = json.loads(str(QSettings().value(STAC_APIS_KEY, "") or "null"))
        return tuple(StacApi(a["name"], a["url"]) for a in saved)
    except (TypeError, KeyError, ValueError):
        return DEFAULT_APIS


def applySavedStacApis() -> None:
    StacCatalog.apis = savedStacApis()


def saveStacApis(apis: tuple[StacApi, ...]) -> None:
    QSettings().setValue(
        STAC_APIS_KEY, json.dumps([{"name": a.name, "url": a.url} for a in apis])
    )
    StacCatalog.apis = apis


class CredentialsDialog(QDialog):
    """Asks for a catalog's login fields; Save keeps them in the keychain."""

    def __init__(self, catalog: Catalog, parent: QWidget | None = None):
        super().__init__(parent)
        self.catalog = catalog
        self.setWindowTitle(f"Log In to {catalog.name}")
        self.edits: dict[str, QLineEdit] = {}
        form = QFormLayout()
        for field in catalog.credentialFields:
            edit = QLineEdit(catalog.credentials.get(field, ""))
            if isSecret(field):
                edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.edits[field] = edit
            form.addRow(f"{field.replace('_', ' ').capitalize()}:", edit)
        note = MutedLabel(
            "Kept in your system's keychain, and sent only to this catalog."
        )
        note.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        forget = buttons.addButton("Forget", QDialogButtonBox.ButtonRole.ResetRole)
        assert forget is not None
        forget.clicked.connect(self._forget)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {field: edit.text() for field, edit in self.edits.items()}

    def accept(self) -> None:
        try:
            saveCredentials(self.catalog, self.values())
        except CatalogError as error:
            QMessageBox.warning(self, "Log In", str(error))
            return
        super().accept()

    def _forget(self) -> None:
        try:
            forgetCredentials(self.catalog)
        except CatalogError as error:
            QMessageBox.warning(self, "Log In", str(error))
            return
        for edit in self.edits.values():
            edit.clear()


class StacApisDialog(QDialog):
    """Edit the STAC APIs that the STAC catalog searches."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("STAC APIs")
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Name", "URL (the API's root)"])
        header = self.table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.setApis(StacCatalog.apis)
        add = QPushButton("Add")
        add.clicked.connect(lambda: self._addRow("", "https://"))
        remove = QPushButton("Remove")
        remove.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        reset = QPushButton("Restore Defaults")
        reset.clicked.connect(lambda: self.setApis(DEFAULT_APIS))
        row = QHBoxLayout()
        for button in (add, remove, reset):
            row.addWidget(button)
        row.addStretch()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(
            MutedLabel("Any STAC API with /collections and /search works.")
        )
        layout.addWidget(self.table)
        layout.addLayout(row)
        layout.addWidget(buttons)
        self.resize(640, 320)

    def setApis(self, apis: tuple[StacApi, ...]) -> None:
        self.table.setRowCount(0)
        for api in apis:
            self._addRow(api.name, api.url)

    def _addRow(self, name: str, url: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(url))

    def apis(self) -> tuple[StacApi, ...]:
        found = []
        for row in range(self.table.rowCount()):
            name, url = (
                (item.text().strip() if (item := self.table.item(row, c)) else "")
                for c in (0, 1)
            )
            if url.startswith(("http://", "https://")) and len(url) > len("https://"):
                found.append(StacApi(name or url, url))
        return tuple(found)

    def accept(self) -> None:
        saveStacApis(self.apis())
        super().accept()
