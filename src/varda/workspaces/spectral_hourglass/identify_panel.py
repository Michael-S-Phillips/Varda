"""Identify: rank library spectra against the active endmember and name it."""

from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QMenu,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from varda.analysis.spectral_library import (
    LIBRARY_FORMAT_HELP,
    MICA_LIBRARY_NAME,
    USGS_LIBRARY_NAME,
    LibraryMatch,
    LibrarySpectrum,
    loadBundledLibraries,
    loadLibrary,
    rankLibrary,
)
from varda.workspaces.spectral_hourglass.hourglass_model import HourglassModel

_COLUMNS = ["#", "Library spectrum", "Score", "Angle", "Fit RMS"]
_FLAG_COLORS = {"best": "#2e7d32", "close": "#9e9d24", "far": "#00000000"}
# CRISM product IDs start with the observation type (FRT, HRL, HRS, FRS, ATO, ...)
_CRISM_PREFIXES = ("frt", "hrl", "hrs", "frs", "ato", "ats", "msp", "hsp", "fft")


class IdentifyPanel(QWidget):
    sigPreviewMatch = pyqtSignal(object)  # LibrarySpectrum

    def __init__(
        self,
        model: HourglassModel,
        library: list[LibrarySpectrum] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self._libraries: dict[str, list[LibrarySpectrum]] = {}
        self._endmemberId: int | None = None
        self._matches: list[LibraryMatch] = []
        self._excluded: set[str] = set()  # library spectra left out of matching

        self.libraryBox = QComboBox()
        self.libraryBox.currentIndexChanged.connect(lambda _: self.refresh())
        if library is not None:
            self._addLibrary("Library", library)
        else:
            for name, spectra in loadBundledLibraries().items():
                self._addLibrary(name, spectra)
        loadButton = QPushButton("Load Library…")
        loadButton.setToolTip(
            "An ENVI spectral library (.sli), a CSV, or a folder of USGS spectra"
        )
        loadButton.clicked.connect(self._loadLibrary)
        self.excludedButton = QPushButton("Excluded (0)")
        self.excludedButton.setToolTip(
            "Library spectra left out of matching; right-click a match to exclude it"
        )
        self.excludedButton.clicked.connect(self._showExcludedMenu)
        self.helpButton = QPushButton("?")
        self.helpButton.setFixedWidth(28)
        self.helpButton.setToolTip("How to prepare a spectral library to load")
        self.helpButton.clicked.connect(self._showLibraryHelp)

        self.windowBox = QCheckBox("Only")
        self.windowBox.setToolTip("Compare only within this wavelength window")
        self.windowLow = QDoubleSpinBox()
        self.windowHigh = QDoubleSpinBox()
        for spin, value in ((self.windowLow, 2000.0), (self.windowHigh, 2500.0)):
            spin.setRange(0.0, 100000.0)
            spin.setDecimals(0)
            spin.setSuffix(" nm")
            spin.setValue(value)
            spin.valueChanged.connect(lambda _: self.refresh())
        self.windowBox.toggled.connect(lambda _: self.refresh())

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        vertical, header = self.table.verticalHeader(), self.table.horizontalHeader()
        assert vertical is not None and header is not None
        vertical.setVisible(False)
        for column in range(len(_COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.cellDoubleClicked.connect(self._onDoubleClicked)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._showMatchMenu)
        self.table.currentCellChanged.connect(lambda row, *_: self._preview(row))

        self.useNameButton = QPushButton("Use as Name")
        self.useNameButton.setToolTip("Name the endmember after the selected match")
        self.useNameButton.clicked.connect(self._useSelectedName)
        self.identifyAllButton = QPushButton("Identify All")
        self.identifyAllButton.setToolTip("Record each endmember's best match")
        self.identifyAllButton.clicked.connect(self.identifyAll)
        self.titleLabel = QLabel()

        libraryRow = QHBoxLayout()
        libraryRow.addWidget(self.libraryBox, stretch=1)
        libraryRow.addWidget(loadButton)
        libraryRow.addWidget(self.excludedButton)
        libraryRow.addWidget(self.helpButton)
        window = QHBoxLayout()
        window.addWidget(self.windowBox)
        window.addWidget(self.windowLow)
        window.addWidget(QLabel("–"))
        window.addWidget(self.windowHigh)
        window.addStretch()
        buttons = QHBoxLayout()
        buttons.addWidget(self.useNameButton)
        buttons.addStretch()
        buttons.addWidget(self.identifyAllButton)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(libraryRow)
        layout.addLayout(window)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(buttons)

        model.sigEndmembersChanged.connect(self.refresh)
        if library is None:
            self._selectDefaultLibrary()

    # --- libraries --------------------------------------------------------------------

    def _addLibrary(self, name: str, spectra: list[LibrarySpectrum]) -> None:
        """Add a library and make it current (without refreshing)."""
        self._libraries[name] = spectra
        with QSignalBlocker(self.libraryBox):
            self.libraryBox.addItem(f"{name} ({len(spectra)})", name)
            self.libraryBox.setCurrentIndex(self.libraryBox.count() - 1)

    def _selectDefaultLibrary(self) -> None:
        """MICA for CRISM products (by their product-ID prefix), USGS otherwise."""
        isCrism = self.model.image.name.lower().startswith(_CRISM_PREFIXES)
        wanted = MICA_LIBRARY_NAME if isCrism else USGS_LIBRARY_NAME
        index = self.libraryBox.findData(wanted)
        if index >= 0:
            self.libraryBox.setCurrentIndex(index)

    def _showLibraryHelp(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Preparing a spectral library")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(LIBRARY_FORMAT_HELP)
        box.open()

    def _loadLibrary(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Spectral Library",
            "",
            "Spectral libraries (*.sli *.hdr *.csv *.txt)",
        )
        if not path:
            return
        try:
            spectra = loadLibrary(path)
        except (OSError, ValueError, KeyError) as error:
            QMessageBox.warning(
                self, "Load Library", f"Could not read {path}:\n{error}"
            )
            return
        self._addLibrary(path.rsplit("/", 1)[-1], spectra)
        self.refresh()

    def library(self) -> list[LibrarySpectrum]:
        """The current library minus the excluded spectra."""
        spectra = self._libraries.get(self.libraryBox.currentData(), [])
        return [s for s in spectra if s.name not in self._excluded]

    # --- exclusions -------------------------------------------------------------------

    def excludedNames(self) -> list[str]:
        return sorted(self._excluded)

    def setExcluded(self, names) -> None:
        self._excluded = set(names)
        self._exclusionsChanged()

    def excludeMatch(self, name: str) -> None:
        self._excluded.add(name)
        self._exclusionsChanged()

    def restoreMatch(self, name: str) -> None:
        self._excluded.discard(name)
        self._exclusionsChanged()

    def restoreAll(self) -> None:
        self._excluded.clear()
        self._exclusionsChanged()

    def _exclusionsChanged(self) -> None:
        self.excludedButton.setText(f"Excluded ({len(self._excluded)})")
        self.refresh()

    def _showMatchMenu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if not 0 <= row < len(self._matches):
            return
        name = self._matches[row].name
        menu = QMenu(self)
        menu.addAction(
            f"Exclude “{name}” from matching", lambda: self.excludeMatch(name)
        )
        viewport = self.table.viewport()
        if viewport is not None:
            menu.exec(viewport.mapToGlobal(pos))

    def _showExcludedMenu(self) -> None:
        menu = QMenu(self)
        if not self._excluded:
            hint = menu.addAction("Nothing excluded: right-click a match to exclude it")
            if hint is not None:
                hint.setEnabled(False)
        for name in self.excludedNames():
            menu.addAction(f"Restore “{name}”", lambda n=name: self.restoreMatch(n))
        if self._excluded:
            menu.addSeparator()
            menu.addAction("Restore all", self.restoreAll)
        menu.popup(
            self.excludedButton.mapToGlobal(self.excludedButton.rect().bottomLeft())
        )

    # --- matching -----------------------------------------------------------------------

    def setEndmember(self, endmemberId: int | None) -> None:
        self._endmemberId = endmemberId
        self.refresh()

    def _rank(self, endmemberId: int) -> list[LibraryMatch]:
        if self.model.prepared is None or self.model.wavelengthsNm is None:
            return []
        spectrum = self.model.endmemberSpectrum(endmemberId)
        window = (
            (self.windowLow.value(), self.windowHigh.value())
            if self.windowBox.isChecked()
            else None
        )
        return rankLibrary(
            self.model.wavelengthsNm, spectrum, self.library(), wavelengthRange=window
        )

    def refresh(self) -> None:
        ids = [e.id for e in self.model.usableEndmembers()]
        if self._endmemberId not in ids:
            self._matches = []
            self.titleLabel.setText("Pick an endmember with pixels to see its matches.")
        else:
            endmember = self.model.endmember(self._endmemberId)
            self._matches = self._rank(endmember.id)
            self.titleLabel.setText(f"Best matches for <b>{endmember.name}</b>")
            prepared = self.model.prepared
            if prepared is None:
                self.titleLabel.setText(
                    "Run Prepare to compare endmembers with the library."
                )
            elif prepared.wavelengths is None:
                self.titleLabel.setText("Identification needs numeric wavelengths.")
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(self._matches))
            for row, match in enumerate(self._matches):
                values = [
                    str(row + 1),
                    match.name,
                    f"{match.score:.2f}",
                    f"{match.angle:.3f}",
                    f"{match.featureRms:.4f}",
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if column == 1:
                        item.setToolTip(match.name)
                    if column == 2:
                        item.setBackground(QBrush(QColor(_FLAG_COLORS[match.flag])))
                    if column != 1:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                    self.table.setItem(row, column, item)

    def _selectedMatch(self) -> LibraryMatch | None:
        row = self.table.currentRow()
        return self._matches[row] if 0 <= row < len(self._matches) else None

    def _preview(self, row: int) -> None:
        if 0 <= row < len(self._matches):
            self.sigPreviewMatch.emit(self._matches[row].spectrum)

    def _onDoubleClicked(self, row: int, column: int) -> None:
        self._preview(row)

    def _useSelectedName(self) -> None:
        match = self._selectedMatch()
        if match is None or self._endmemberId is None:
            return
        endmemberId = self._endmemberId
        self.model.renameEndmember(endmemberId, match.name)
        self.model.setIdentification(endmemberId, f"{match.name} ({match.score:.2f})")
        self.model.markIdentified()

    def identifyAll(self) -> None:
        for endmember in self.model.usableEndmembers():
            matches = self._rank(endmember.id)
            if matches:
                best = matches[0]
                self.model.setIdentification(
                    endmember.id, f"{best.name} ({best.score:.2f})"
                )
        self.model.markIdentified()
