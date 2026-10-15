"""Choose a spectral library: one bundled with Varda or one loaded from a file."""

from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QWidget,
)

from varda.analysis.spectral_library import (
    LIBRARY_FORMAT_HELP,
    MICA_LIBRARY_NAME,
    USGS_LIBRARY_NAME,
    LibrarySpectrum,
    loadBundledLibraries,
    loadLibrary,
)

# CRISM product IDs start with the observation type (FRT, HRL, HRS, FRS, ATO, ...)
CRISM_PREFIXES = ("frt", "hrl", "hrs", "frs", "ato", "ats", "msp", "hsp", "fft")


class LibraryPicker(QWidget):
    """A library chooser with Load Library… and a help button on the format."""

    sigLibraryChanged = pyqtSignal()

    def __init__(
        self,
        library: list[LibrarySpectrum] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._libraries: dict[str, list[LibrarySpectrum]] = {}
        self.box = QComboBox()
        self.box.currentIndexChanged.connect(lambda _: self.sigLibraryChanged.emit())
        if library is not None:
            self.addLibrary("Library", library)
        else:
            for name, spectra in loadBundledLibraries().items():
                self.addLibrary(name, spectra)
        loadButton = QPushButton("Load Library…")
        loadButton.setToolTip(
            "An ENVI spectral library (.sli), a CSV, or a folder of USGS spectra"
        )
        loadButton.clicked.connect(self._load)
        self.helpButton = QPushButton("?")
        self.helpButton.setFixedWidth(28)
        self.helpButton.setToolTip("How to prepare a spectral library to load")
        self.helpButton.clicked.connect(self._showHelp)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.box, stretch=1)
        layout.addWidget(loadButton)
        layout.addWidget(self.helpButton)

    def addLibrary(self, name: str, spectra: list[LibrarySpectrum]) -> None:
        """Add a library and make it current (without signaling)."""
        self._libraries[name] = spectra
        with QSignalBlocker(self.box):
            self.box.addItem(f"{name} ({len(spectra)})", name)
            self.box.setCurrentIndex(self.box.count() - 1)

    def selectDefaultFor(self, imageName: str) -> None:
        """MICA for CRISM products (by their product-ID prefix), USGS otherwise."""
        isCrism = imageName.lower().startswith(CRISM_PREFIXES)
        index = self.box.findData(MICA_LIBRARY_NAME if isCrism else USGS_LIBRARY_NAME)
        if index >= 0:
            self.box.setCurrentIndex(index)

    def libraryName(self) -> str:
        return self.box.currentData() or ""

    def library(self) -> list[LibrarySpectrum]:
        return self._libraries.get(self.box.currentData(), [])

    def _showHelp(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Preparing a spectral library")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(LIBRARY_FORMAT_HELP)
        box.open()

    def _load(self) -> None:
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
        self.addLibrary(path.rsplit("/", 1)[-1], spectra)
        self.sigLibraryChanged.emit()
