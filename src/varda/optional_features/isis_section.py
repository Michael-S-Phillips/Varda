"""ISIS in Optional Features: detected only (never downloaded: its mission
data runs to tens of GB). Mosaicking and cam2map ask ``currentIsis``."""

from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from varda.mosaicking.backends.isis import IsisInstall, findIsis

_cache: dict[str, IsisInstall | None] = {}


def currentIsis(redetect: bool = False) -> IsisInstall | None:
    """The ISIS to use (detected once per session unless asked again)."""
    if redetect or "isis" not in _cache:
        _cache["isis"] = findIsis()
    return _cache["isis"]


def describeIsis(install: IsisInstall | None) -> str:
    if install is None:
        return (
            "Not found. Install ISIS with conda (see the USGS ISIS guide) and set "
            "ISISROOT, then Re-detect."
        )
    version = f"ISIS {install.version}" if install.version else "ISIS"
    data = (
        f"ISISDATA: {install.data}"
        if install.data is not None
        else "ISISDATA isn't set: cam2map needs it (with the mission's SPICE kernels)."
    )
    return f"{version} found ({install.source}):\n{install.root}\n{data}"


class IsisSection(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        title = QLabel("ISIS")
        font = QFont(title.font())
        font.setBold(True)
        title.setFont(font)
        about = QLabel(
            "Optional, detected only: with ISIS, Varda can map-project raw camera "
            "cubes (Processing → Geometry → Map-Project with ISIS) and compare "
            "its mosaic radiometry with ISIS equalizer."
        )
        about.setWordWrap(True)
        self.status = QLabel()
        self.status.setWordWrap(True)
        redetect = QPushButton("Re-detect")
        redetect.clicked.connect(lambda: self.refresh(redetect=True))
        buttons = QHBoxLayout()
        buttons.addWidget(redetect)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(title)
        layout.addWidget(about)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self, redetect: bool = False) -> None:
        self.status.setText(describeIsis(currentIsis(redetect)))
