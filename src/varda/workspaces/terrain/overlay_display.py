"""The Overlay Display dock: the selected overlay's render settings (mode,
bands, stretch, color map) and its histograms, whose stretch ranges can be
dragged, as in the image views. The overlay is drawn again once the changes
settle (sigChanged), as each one rebuilds its texture."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QScrollArea, QSplitter, QVBoxLayout, QWidget

from varda.common.ui import MutedLabel
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.new_histogram_view import NewHistogramView
from varda.workspaces.terrain.overlay_panel import TerrainOverlay

SETTLE_MS = 400  # changes this close together draw the overlay once


class OverlayDisplay(QWidget):
    sigChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.overlay: TerrainOverlay | None = None
        self._renderer: ImageRenderer | None = None
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(SETTLE_MS)
        self._settle.timeout.connect(self.sigChanged)
        self.title = MutedLabel("Select an overlay to set how it's drawn.")
        self.title.setWordWrap(True)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.splitter, 1)

    def setOverlay(self, overlay: TerrainOverlay | None) -> None:
        if overlay is self.overlay:
            return
        if self._renderer is not None:
            self._renderer.sigShouldRefresh.disconnect(self._settle.start)
        while self.splitter.count():
            widget = self.splitter.widget(0)
            assert widget is not None
            widget.setParent(None)
            widget.deleteLater()
        self.overlay, self._renderer = overlay, None
        if overlay is None:
            self.title.setText("Select an overlay to set how it's drawn.")
            return
        self.title.setText(f"<b>{overlay.image.name}</b>")
        renderer = overlay.renderer
        settings = QScrollArea()
        # the overlay's opacity is set in the Overlays panel
        settings.setWidget(renderer.getSettingsPanel(opacity=False))
        settings.setWidgetResizable(True)
        self.splitter.addWidget(settings)
        self.splitter.addWidget(NewHistogramView(renderer))
        self.splitter.setSizes([300, 220])
        renderer.sigShouldRefresh.connect(self._settle.start)
        self._renderer = renderer
