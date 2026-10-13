"""Which images share a pixel grid (so masks, overlays and statistics line up)."""

from __future__ import annotations

from collections.abc import Sequence

from varda.common.entities import VardaRaster


def sameGrid(a: VardaRaster, b: VardaRaster) -> bool:
    if (a.height, a.width) != (b.height, b.width):
        return False
    if a.hasGeospatialData and b.hasGeospatialData:
        return a.crs == b.crs and a.transform.almost_equals(b.transform)
    return a.hasGeospatialData == b.hasGeospatialData


def compatibleImages(
    images: Sequence[VardaRaster], base: VardaRaster
) -> list[VardaRaster]:
    """The other images on ``base``'s pixel grid."""
    return [image for image in images if image is not base and sameGrid(image, base)]
