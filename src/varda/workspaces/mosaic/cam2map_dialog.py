"""Processing > Geometry > Map-Project with ISIS (cam2map): map-project a
raw, spiceinit-ed camera cube so it can be mosaicked; the result opens in
Varda."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from varda.common.ui import MutedLabel
from varda.mosaicking.backends.isis import IsisError, IsisInstall, cam2map
from varda.optional_features.isis_section import currentIsis, describeIsis
from varda.utilities.background import runInBackground

INTERPOLATIONS = {
    "Nearest neighbor (keeps spectra exact)": "nearestneighbor",
    "Bilinear": "bilinear",
    "Cubic convolution (ISIS's default)": "cubicconvolution",
}


class Cam2mapDialog(QDialog):
    sigProjected = pyqtSignal(str)  # the output cube's path

    def __init__(
        self, install: IsisInstall | None = None, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.setWindowTitle("Map-Project with ISIS (cam2map)")
        self.setMinimumWidth(560)
        self.install = install if install is not None else currentIsis()

        self.source = QLineEdit()
        self.source.setPlaceholderText("A level 1 cube, after spiceinit")
        self.source.textChanged.connect(self._suggestTarget)
        self.target = QLineEdit()
        self.mapDefault = QRadioButton("ISIS's default (sinusoidal)")
        self.mapMatch = QRadioButton("Match a map-projected cube")
        self.mapFile = QRadioButton("A map template (.map)")
        self.mapDefault.setChecked(True)
        self.mapGroup = QButtonGroup(self)
        for button in (self.mapDefault, self.mapMatch, self.mapFile):
            self.mapGroup.addButton(button)
            button.toggled.connect(lambda _: self._updateState())
        self.mapPath = QLineEdit()
        self.resolution = QDoubleSpinBox()
        self.resolution.setRange(0.0, 1e6)
        self.resolution.setDecimals(3)
        self.resolution.setSuffix(" m/pixel")
        self.resolution.setSpecialValueText("The camera's")
        self.interpolation = QComboBox()
        for label, value in INTERPOLATIONS.items():
            self.interpolation.addItem(label, value)
        self.status = MutedLabel(describeIsis(self.install))
        self.status.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Raw cube:", self._withBrowse(self.source, self._browseSource))
        form.addRow("Output:", self._withBrowse(self.target, self._browseTarget))
        maps = QVBoxLayout()
        for button in (self.mapDefault, self.mapMatch, self.mapFile):
            maps.addWidget(button)
        maps.addLayout(self._withBrowse(self.mapPath, self._browseMap))
        form.addRow("Projection:", maps)
        form.addRow("Resolution:", self.resolution)
        form.addRow("Interpolation:", self.interpolation)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Close
        )
        self.runButton = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert self.runButton is not None
        self.runButton.setText("Map-Project")
        self.buttons.accepted.connect(self._run)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(self.buttons)
        self._updateState()

    def _withBrowse(self, edit: QLineEdit, browse) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(edit, 1)
        button = QPushButton("Browse…")
        button.clicked.connect(browse)
        row.addWidget(button)
        return row

    def _browseSource(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Raw Cube", "", "ISIS cubes (*.cub)"
        )
        if path:
            self.source.setText(path)

    def _browseTarget(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Output Cube", self.target.text(), "ISIS cubes (*.cub)"
        )
        if path:
            self.target.setText(path)

    def _browseMap(self) -> None:
        filter = (
            "ISIS cubes (*.cub)"
            if self.mapMatch.isChecked()
            else "Map templates (*.map)"
        )
        path, _ = QFileDialog.getOpenFileName(self, "Projection", "", filter)
        if path:
            self.mapPath.setText(path)

    def _suggestTarget(self, text: str) -> None:
        if text and not self.target.text():
            source = Path(text)
            self.target.setText(str(source.with_name(source.stem + "_map.cub")))

    def _updateState(self) -> None:
        self.mapPath.setEnabled(not self.mapDefault.isChecked())
        self.resolution.setEnabled(not self.mapMatch.isChecked())
        self.runButton.setEnabled(self.install is not None)

    def options(self) -> dict:
        resolution = self.resolution.value()
        mapPath = self.mapPath.text().strip()
        return {
            "mapTemplate": None
            if self.mapDefault.isChecked() or not mapPath
            else Path(mapPath),
            "matchMap": self.mapMatch.isChecked(),
            "resolution": resolution if resolution > 0 else None,
            "interpolation": self.interpolation.currentData(),
        }

    def _run(self) -> None:
        if self.install is None:
            return
        source, target = self.source.text().strip(), self.target.text().strip()
        if not source or not target:
            self.status.setText("Choose the raw cube and where to write the result.")
            return
        if not self.mapDefault.isChecked() and not self.mapPath.text().strip():
            self.status.setText("Choose the cube or map template to project to.")
            return
        install, options = self.install, self.options()
        self.runButton.setEnabled(False)
        self.status.setText("Map-projecting…")
        runInBackground(
            lambda: cam2map(install, Path(source), Path(target), **options),
            self._finished,
            self._failed,
            description="Map-projecting with cam2map",
        )

    def _finished(self, path: Path) -> None:
        self.runButton.setEnabled(True)
        self.status.setText(f"Wrote {path}; it's added to the image list.")
        self.sigProjected.emit(str(path))

    def _failed(self, error: Exception) -> None:
        self.runButton.setEnabled(True)
        message = str(error)
        if (
            isinstance(error, IsisError)
            and self.install is not None
            and self.install.data is None
        ):
            message += "\n(ISISDATA isn't set; camera models need it.)"
        self.status.setText(message)
