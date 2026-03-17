"""ViewportLinkController — synchronizes pan/zoom between two viewports."""

import logging
from enum import Enum

from PyQt6.QtCore import QObject, QRectF

from varda.image_rendering.raster_view.image_viewport import ImageViewport

logger = logging.getLogger(__name__)


class LinkMode(Enum):
    """How two viewports synchronize their pan/zoom."""

    PIXEL = 1
    GEO = 2


class ViewportLinkController(QObject):
    """Synchronize pan and zoom between two ImageViewport instances.

    Supports two link modes:
      - PIXEL: both viewports show the same pixel coordinate range.
      - GEO: both viewports show the same geospatial extent
             (requires georeferenced images sharing the same CRS).
    """

    def __init__(
        self,
        viewport1: ImageViewport,
        viewport2: ImageViewport,
        linkMode: LinkMode,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._viewport1 = viewport1
        self._viewport2 = viewport2
        self._linkMode = linkMode

        # sigRangeChangedManually only fires on user interaction (mouse drag,
        # scroll wheel), NOT on programmatic setRange() calls, so there is no
        # risk of infinite recursion.
        self._viewport1.viewBox.sigRangeChangedManually.connect(
            self._onViewport1Changed
        )
        self._viewport2.viewBox.sigRangeChangedManually.connect(
            self._onViewport2Changed
        )

    # --- Public API ---

    def setLinkMode(self, linkMode: LinkMode) -> None:
        self._linkMode = linkMode

    def cleanup(self) -> None:
        self._viewport1.viewBox.sigRangeChangedManually.disconnect(
            self._onViewport1Changed
        )
        self._viewport2.viewBox.sigRangeChangedManually.disconnect(
            self._onViewport2Changed
        )

    # --- Slots ---
    def _onViewport1Changed(self) -> None:
        self._syncRange(self._viewport1, self._viewport2)

    def _onViewport2Changed(self) -> None:
        self._syncRange(self._viewport2, self._viewport1)

    # --- Sync logic ---

    def _syncRange(self, source: ImageViewport, target: ImageViewport) -> None:
        if self._linkMode == LinkMode.PIXEL:
            self._syncRangePixel(source, target)
        elif self._linkMode == LinkMode.GEO:
            self._syncRangeGeo(source, target)

    def _syncRangePixel(self, source: ImageViewport, target: ImageViewport) -> None:
        sourceRect = source.viewBox.viewRect()
        target.viewBox.setRange(rect=sourceRect, padding=0)

    def _syncRangeGeo(self, source: ImageViewport, target: ImageViewport) -> None:
        sourceImage = source.imageEntity
        targetImage = target.imageEntity

        if not sourceImage.hasGeospatialData or not targetImage.hasGeospatialData:
            logger.warning(
                "GEO link mode requires georeferenced images; falling back to PIXEL."
            )
            self._syncRangePixel(source, target)
            return

        sourceRect = source.viewBox.viewRect()

        # Convert source rect corners: source pixels → geo → target pixels
        geoX1, geoY1 = sourceImage.pixelToGeo(
            int(sourceRect.left()), int(sourceRect.top())
        )
        geoX2, geoY2 = sourceImage.pixelToGeo(
            int(sourceRect.right()), int(sourceRect.bottom())
        )

        tCol1, tRow1 = targetImage.geoToPixel(geoX1, geoY1)
        tCol2, tRow2 = targetImage.geoToPixel(geoX2, geoY2)

        targetRect = QRectF(
            min(tCol1, tCol2),
            min(tRow1, tRow2),
            abs(tCol2 - tCol1),
            abs(tRow2 - tRow1),
        )
        target.viewBox.setRange(rect=targetRect, padding=0)
