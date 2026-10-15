"""A mosaic's recipe: its inputs in priority order (the first is on top),
each with a correction (a transform of its map coordinates), and the tie
points the corrections are fitted to. Nothing is resampled until rendering,
so every choice stays editable."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from attrs import define, field

from varda.common.entities import VardaRaster
from varda.mosaicking.transforms import (
    TransformModel,
    applyMatrix,
    fitTransform,
    translation,
)


@define(eq=False)
class MosaicInput:
    image: VardaRaster
    key: int  # stable across reordering; tie points refer to it
    correction: np.ndarray = field(factory=lambda: np.eye(3))  # map → corrected map
    model: TransformModel = TransformModel.TRANSLATION
    visible: bool = True

    def toMap(self, pixels: np.ndarray, corrected: bool = True) -> np.ndarray:
        """Pixel (col, row) coordinates to map coordinates, corrected or not."""
        pixels = np.atleast_2d(np.asarray(pixels, float))
        x, y = self.image.transform * (pixels[:, 0], pixels[:, 1])
        mapped = np.column_stack([x, y])
        return applyMatrix(self.correction, mapped) if corrected else mapped

    def footprint(self) -> np.ndarray:
        """The corrected map coordinates of the image's four corners."""
        w, h = self.image.width, self.image.height
        return self.toMap(np.array([[0, 0], [w, 0], [w, h], [0, h]]))


@define(eq=False)
class TiePoint:
    """A point on the moving image and the same feature on the reference."""

    movingKey: int
    movingPixel: tuple[float, float]
    referenceKey: int
    referencePixel: tuple[float, float]
    enabled: bool = True
    residual: float = float("nan")  # map units, after the last fit


class MosaicError(ValueError):
    """The inputs can't be mosaicked as they are; the message is for the user."""


class MosaicProject:
    def __init__(self, images: Sequence[VardaRaster]):
        if len(images) < 2:
            raise MosaicError("A mosaic needs at least two images.")
        crs = {str(image.crs) if image.crs is not None else None for image in images}
        if len(crs) > 1:
            raise MosaicError(
                "The images are in different map projections; reproject them to "
                "one first (Varda doesn't yet reproject while mosaicking)."
            )
        bands = {image.bandCount for image in images}
        if len(bands) > 1:
            raise MosaicError(
                "The images have different numbers of bands ("
                + ", ".join(str(b) for b in sorted(bands))
                + "); a mosaic needs the same bands in every image."
            )
        self.inputs = [MosaicInput(image, key) for key, image in enumerate(images)]
        self.tiePoints: list[TiePoint] = []

    # --- inputs ------------------------------------------------------------

    def input(self, key: int) -> MosaicInput:
        return next(i for i in self.inputs if i.key == key)

    def move(self, key: int, steps: int) -> None:
        """Move an input up (negative) or down the priority order."""
        item = self.input(key)
        index = self.inputs.index(item)
        target = int(np.clip(index + steps, 0, len(self.inputs) - 1))
        self.inputs.insert(target, self.inputs.pop(index))

    def nudge(self, key: int, dx: float, dy: float) -> None:
        """Shift an input by (dx, dy) map units."""
        item = self.input(key)
        item.correction = translation(dx, dy) @ item.correction

    def resetAlignment(self, key: int) -> None:
        self.input(key).correction = np.eye(3)

    # --- tie points ----------------------------------------------------------

    def addTiePoint(
        self, movingKey: int, movingPixel, referenceKey: int, referencePixel
    ) -> TiePoint:
        if movingKey == referenceKey:
            raise MosaicError("A tie point joins two different images.")
        point = TiePoint(
            movingKey,
            (float(movingPixel[0]), float(movingPixel[1])),
            referenceKey,
            (float(referencePixel[0]), float(referencePixel[1])),
        )
        self.tiePoints.append(point)
        return point

    def tiePointsOf(self, key: int) -> list[TiePoint]:
        return [p for p in self.tiePoints if p.movingKey == key]

    def fit(self, key: int) -> np.ndarray:
        """Fit the input's correction to its enabled tie points (its pixels
        onto the references' current positions); returns the residuals."""
        moving = self.input(key)
        points = [p for p in self.tiePointsOf(key) if p.enabled]
        src = moving.toMap(
            np.array([p.movingPixel for p in points]).reshape(-1, 2), corrected=False
        )
        dst = np.array(
            [
                self.input(p.referenceKey).toMap(np.array([p.referencePixel]))[0]
                for p in points
            ]
        ).reshape(-1, 2)
        matrix, residuals = fitTransform(moving.model, src, dst)
        moving.correction = matrix
        for point, residual in zip(points, residuals):
            point.residual = float(residual)
        return residuals

    # --- saving ----------------------------------------------------------------

    def state(self) -> dict:
        """The recipe as plain data; images are referred to by position in the
        list the project was made from."""
        order = sorted(self.inputs, key=lambda i: i.key)
        return {
            "order": [i.key for i in self.inputs],
            "inputs": [
                {
                    "correction": i.correction.tolist(),
                    "model": i.model.name,
                    "visible": i.visible,
                }
                for i in order
            ],
            "tiePoints": [
                {
                    "moving": p.movingKey,
                    "movingPixel": list(p.movingPixel),
                    "reference": p.referenceKey,
                    "referencePixel": list(p.referencePixel),
                    "enabled": p.enabled,
                }
                for p in self.tiePoints
            ],
        }

    def restore(self, state: dict) -> None:
        for item, saved in zip(
            sorted(self.inputs, key=lambda i: i.key), state.get("inputs", [])
        ):
            item.correction = np.asarray(saved["correction"], float)
            item.model = TransformModel[saved.get("model", "TRANSLATION")]
            item.visible = bool(saved.get("visible", True))
        order = state.get("order")
        if order and sorted(order) == sorted(i.key for i in self.inputs):
            self.inputs.sort(key=lambda i: order.index(i.key))
        self.tiePoints = [
            TiePoint(
                p["moving"],
                tuple(p["movingPixel"]),
                p["reference"],
                tuple(p["referencePixel"]),
                p.get("enabled", True),
            )
            for p in state.get("tiePoints", [])
        ]
