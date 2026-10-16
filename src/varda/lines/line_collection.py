"""Lines drawn on an image: straight lines, polylines and freehand lines, in
image pixel coordinates, with a name and color. No Qt."""

from __future__ import annotations

from pathlib import Path

import attrs
import geopandas as gpd
import numpy as np
import numpy.typing as npt
from psygnal import Signal
from shapely.geometry import LineString

from varda.common.entities import VardaRaster
from varda.common.parameter import LabeledEnum
from varda.common.palette import classColor
from varda.lines.profile import lineLength

EXPORT_FILE_FILTER = "GeoJSON (*.geojson);;GeoPackage (*.gpkg);;Shapefile (*.shp)"
_DRIVERS = {
    ".geojson": "GeoJSON",
    ".json": "GeoJSON",
    ".gpkg": "GPKG",
    ".shp": "ESRI Shapefile",
}


class LineKind(LabeledEnum):
    STRAIGHT = "Straight"
    POLYLINE = "Polyline"
    FREEHAND = "Freehand"


@attrs.frozen(eq=False)
class VardaLine:
    fid: int
    name: str
    color: str  # "#rrggbb"
    kind: LineKind
    vertices: np.ndarray  # (n, 2) image pixel coordinates: x (column), y (row)

    def length(self, image: VardaRaster | None) -> tuple[float, str]:
        """Its length and units (meters when ``image`` is georeferenced)."""
        if image is None or not image.hasGeospatialData:
            return lineLength(self.vertices, None, None)
        return lineLength(self.vertices, image.transform, image.crs)


class LineCollection:
    """Lines in the order they were drawn."""

    sigLineAdded = Signal(int)
    sigLineRemoved = Signal(int)
    sigLineChanged = Signal(int)
    sigCollectionChanged = Signal()

    def __init__(self) -> None:
        self._lines: dict[int, VardaLine] = {}
        self._nextFid = 0

    def addLine(
        self,
        vertices: npt.ArrayLike,
        kind: LineKind = LineKind.POLYLINE,
        *,
        name: str | None = None,
        color: str | None = None,
    ) -> int:
        vertices = np.asarray(vertices, dtype=float).reshape(-1, 2)
        if len(vertices) < 2:
            raise ValueError("A line needs at least two points.")
        fid = self._nextFid
        self._nextFid += 1
        self._lines[fid] = VardaLine(
            fid, name or f"Line {fid + 1}", color or classColor(fid), kind, vertices
        )
        self.sigLineAdded.emit(fid)
        self.sigCollectionChanged.emit()
        return fid

    def removeLine(self, fid: int) -> None:
        del self._lines[fid]
        self.sigLineRemoved.emit(fid)
        self.sigCollectionChanged.emit()

    def updateLine(self, fid: int, **changes) -> None:
        """Rename or recolor a line (``name=``, ``color=``)."""
        self._lines[fid] = attrs.evolve(self._lines[fid], **changes)
        self.sigLineChanged.emit(fid)
        self.sigCollectionChanged.emit()

    def get(self, fid: int) -> VardaLine:
        return self._lines[fid]

    def lines(self) -> list[VardaLine]:
        return list(self._lines.values())

    def __len__(self) -> int:
        return len(self._lines)

    def clear(self) -> None:
        for fid in list(self._lines):
            self.removeLine(fid)

    # --- sessions and files -------------------------------------------------------

    def toJson(self) -> list[dict]:
        return [
            {
                "name": line.name,
                "color": line.color,
                "kind": line.kind.name,
                "vertices": line.vertices.tolist(),
            }
            for line in self._lines.values()
        ]

    def addFromJson(self, entries: list[dict]) -> None:
        for entry in entries:
            self.addLine(
                np.asarray(entry["vertices"], dtype=float),
                LineKind[entry.get("kind", "POLYLINE")],
                name=entry.get("name"),
                color=entry.get("color"),
            )

    def toFile(self, path: str | Path, image: VardaRaster) -> None:
        """GIS lines: map coordinates (in the image's CRS) when it is
        georeferenced, pixel coordinates otherwise."""
        path = Path(path)
        driver = _DRIVERS.get(path.suffix.lower())
        if driver is None:
            raise ValueError(f"Unsupported file type: {path.suffix}")
        georeferenced = image.hasGeospatialData
        geometries = [
            LineString(
                image.imageToGeo(line.vertices.tolist())
                if georeferenced
                else line.vertices
            )
            for line in self._lines.values()
        ]
        lengths = [line.length(image) for line in self._lines.values()]
        frame = gpd.GeoDataFrame(
            {
                "name": [line.name for line in self._lines.values()],
                "kind": [line.kind.value for line in self._lines.values()],
                "color": [line.color for line in self._lines.values()],
                "length": [length for length, _ in lengths],
                "units": [units for _, units in lengths],
            },
            geometry=geometries,
            crs=image.crs if georeferenced else None,
        )
        frame.to_file(path, driver=driver)
