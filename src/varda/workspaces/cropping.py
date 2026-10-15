"""Crop tool results: a box drawn with the Crop tool becomes a cropped copy
of the image, added to the project's image list (where any analysis or a
new workspace can use it)."""

from __future__ import annotations

from collections.abc import MutableSequence

from PyQt6.QtCore import QRect

from varda.analysis.geometry import crop
from varda.common.entities import VardaRaster


def addCrop(
    image: VardaRaster, box: QRect, projectImages: MutableSequence[VardaRaster]
) -> VardaRaster:
    """Crop ``image`` to ``box`` (full-image pixels), add it to the project
    and return it."""
    cropped = crop(
        image,
        box.top(),
        box.left(),
        box.height(),
        box.width(),
        name=f"{image.name} crop {box.width()}×{box.height()}",
    )
    projectImages.append(cropped)
    return cropped


def cropMessage(cropped: VardaRaster) -> str:
    return (
        f"Added {cropped.name} to the image list: run any analysis on it, or "
        "open a workspace (e.g. a Spectral Hourglass) for it."
    )
