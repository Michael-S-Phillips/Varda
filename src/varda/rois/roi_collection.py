"""roi_collection.py: GeoPandas-backed ROI collection for Varda."""

from __future__ import annotations

import logging
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio.features
from affine import Affine
from psygnal import Signal
from pyproj import CRS
from shapely.geometry import mapping as shapely_mapping
from shapely.geometry.base import BaseGeometry

from varda.common.entities import ROIMode, Spectrum, VardaROI

logger = logging.getLogger(__name__)

# Core columns in the GeoDataFrame (besides the geometry column)
_CORE_COLUMNS = ("name", "color", "roi_type")


class ROICollection:
    """A collection of ROIs backed by a GeoDataFrame.

    Each row is an ROI feature. Geometry is stored in CRS coordinates when the
    source image is georeferenced, or in pixel coordinates otherwise.

    Signals (psygnal, Qt-free):
        sigROIAdded(int): emitted with fid after an ROI is added.
        sigROIRemoved(int): emitted with fid after an ROI is removed.
        sigROIUpdated(int): emitted with fid after an ROI is updated.
        sigCollectionChanged(): emitted on any structural change.
    """

    sigROIAdded = Signal(int)
    sigROIRemoved = Signal(int)
    sigROIUpdated = Signal(int)
    sigCollectionChanged = Signal()

    def __init__(
        self,
        crs: CRS | None = None,
        transform: Affine = Affine.identity(),
    ) -> None:
        self._crs = crs
        self._transform = transform
        self._nextFid: int = 0
        self._gdf = gpd.GeoDataFrame(
            columns=["name", "color", "roi_type", "geometry"],
            geometry="geometry",
        )
        self._gdf.index.name = "fid"
        if crs is not None:
            self._gdf = self._gdf.set_crs(crs)

    # --- Core CRUD ---

    def addROI(
        self,
        geometry: BaseGeometry,
        name: str,
        color: tuple[int, int, int, int],
        roiType: ROIMode,
        **properties: Any,
    ) -> int:
        """Add an ROI to the collection and return its fid."""
        fid = self._nextFid
        self._nextFid += 1

        row: dict[str, Any] = {
            "name": name,
            "color": color,
            "roi_type": roiType,
            "geometry": geometry,
        }
        row.update(properties)

        new_row = gpd.GeoDataFrame(
            [row],
            index=pd.Index([fid], name="fid"),
            geometry="geometry",
            crs=self._crs,
        )
        self._gdf = pd.concat([self._gdf, new_row])

        self.sigROIAdded.emit(fid)
        self.sigCollectionChanged.emit()
        return fid

    def removeROI(self, fid: int) -> None:
        """Remove an ROI by fid."""
        if fid not in self._gdf.index:
            raise KeyError(f"No ROI with fid={fid}")
        self._gdf = self._gdf.drop(index=fid)

        self.sigROIRemoved.emit(fid)
        self.sigCollectionChanged.emit()

    def getROI(self, fid: int) -> VardaROI:
        """Return an immutable VardaROI snapshot for the given fid."""
        if fid not in self._gdf.index:
            raise KeyError(f"No ROI with fid={fid}")
        row = self._gdf.loc[fid]
        return self._rowToVardaROI(fid, row)

    def getAllROIs(self) -> list[VardaROI]:
        """Return all ROIs as a list of immutable snapshots."""
        return [self._rowToVardaROI(fid, row) for fid, row in self._gdf.iterrows()]

    def updateROI(self, fid: int, **kwargs: Any) -> None:
        """Update core properties of an ROI (name, color, roi_type, geometry)."""
        if fid not in self._gdf.index:
            raise KeyError(f"No ROI with fid={fid}")
        for key, value in kwargs.items():
            if key not in (*_CORE_COLUMNS, "geometry"):
                raise ValueError(
                    f"'{key}' is not a core ROI property. "
                    "Use setProperty() for user columns."
                )
            self._gdf.at[fid, key] = value

        self.sigROIUpdated.emit(fid)
        self.sigCollectionChanged.emit()

    def __len__(self) -> int:
        return len(self._gdf)

    # --- User metadata columns ---

    def addColumn(self, name: str, default: Any = None) -> None:
        """Add a user-defined metadata column to all ROIs."""
        if name in self._gdf.columns:
            raise ValueError(f"Column '{name}' already exists")
        self._gdf[name] = default

    def setProperty(self, fid: int, column: str, value: Any) -> None:
        """Set a user-defined property on an ROI."""
        if fid not in self._gdf.index:
            raise KeyError(f"No ROI with fid={fid}")
        if column in (*_CORE_COLUMNS, "geometry"):
            raise ValueError(f"'{column}' is a core column. Use updateROI() instead.")
        self._gdf.at[fid, column] = value
        self.sigROIUpdated.emit(fid)
        self.sigCollectionChanged.emit()

    def getProperty(self, fid: int, column: str) -> Any:
        """Get a user-defined property from an ROI."""
        if fid not in self._gdf.index:
            raise KeyError(f"No ROI with fid={fid}")
        if column not in self._gdf.columns:
            raise KeyError(f"No column '{column}'")
        return self._gdf.at[fid, column]

    # --- Properties ---

    @property
    def crs(self) -> CRS | None:
        return self._crs

    @property
    def transform(self) -> Affine:
        return self._transform

    @property
    def gdf(self) -> gpd.GeoDataFrame:
        """Direct access to the underlying GeoDataFrame (read-only intent)."""
        return self._gdf

    @property
    def fids(self) -> list[int]:
        """Return all feature IDs."""
        return list(self._gdf.index)

    # --- Coordinate conversion & masks ---

    def getPixelCoordinates(self, fid: int, image: Any = None) -> np.ndarray:
        """Convert ROI geometry to pixel coordinates.

        If the collection has a CRS (georeferenced), converts each vertex
        via the image's ``geoToPixel()``. Otherwise the geometry is already
        in pixel space.

        Args:
            fid: Feature ID.
            image: A VardaRaster. Required when the collection has a CRS.

        Returns:
            Nx2 array of (col, row) pixel coordinates.
        """
        if fid not in self._gdf.index:
            raise KeyError(f"No ROI with fid={fid}")
        geom = self._gdf.at[fid, "geometry"]
        coords = np.array(geom.exterior.coords)  # Nx2 (x, y)

        if self._crs is not None:
            if image is None:
                raise ValueError(
                    "An image is required to convert CRS geometry to pixel coords"
                )
            pixel_coords = np.array([image.geoToPixel(x, y) for x, y in coords])
            return pixel_coords
        else:
            # Already pixel coords: (col, row)
            return coords[:, :2].astype(np.float64)

    def getMask(self, fid: int, image: Any) -> np.ndarray:
        """Create a binary mask for an ROI in the image's pixel space.

        Uses ``rasterio.features.rasterize`` for robust polygon rasterization.

        Args:
            fid: Feature ID.
            image: A VardaRaster providing height, width, and coordinate transform.

        Returns:
            Boolean array of shape (height, width).
        """
        pixel_coords = self.getPixelCoordinates(fid, image)
        from shapely.geometry import Polygon as ShapelyPolygon

        pixel_polygon = ShapelyPolygon(pixel_coords)
        mask = rasterio.features.rasterize(
            [(shapely_mapping(pixel_polygon), 1)],
            out_shape=(image.height, image.width),
            fill=0,
            dtype=np.uint8,
        )
        return mask.astype(bool)

    # --- Spectral statistics ---

    def getMeanSpectrum(self, fid: int, image: Any) -> Spectrum:
        """Compute per-band mean spectrum for pixels within an ROI.

        Uses a bounding-box window read to avoid loading the full image.

        Args:
            fid: Feature ID.
            image: A VardaRaster.

        Returns:
            Spectrum with per-band mean values.
        """
        stats = self.getROIStatistics(fid, image)
        return Spectrum(
            values=stats["mean"],
            wavelengths=image.wavelengths,
        )

    def getStdDeviation(self, fid: int, image: Any) -> np.ndarray:
        """Per-band standard deviation of pixels within an ROI."""
        stats = self.getROIStatistics(fid, image)
        return stats["std"]

    def getROIStatistics(self, fid: int, image: Any) -> dict[str, Any]:
        """Compute combined statistics for an ROI over an image.

        Returns:
            Dict with keys: mean, std, min, max, pixel_count — all per-band
            numpy arrays except pixel_count (int).
        """
        mask = self.getMask(fid, image)

        # Compute bounding box of the mask to read a small window
        rows, cols = np.where(mask)
        if len(rows) == 0:
            nbands = image.bandCount
            return {
                "mean": np.zeros(nbands),
                "std": np.zeros(nbands),
                "min": np.zeros(nbands),
                "max": np.zeros(nbands),
                "pixel_count": 0,
            }

        r_min, r_max = int(rows.min()), int(rows.max())
        c_min, c_max = int(cols.min()), int(cols.max())
        win_h = r_max - r_min + 1
        win_w = c_max - c_min + 1

        # Read windowed data: (win_h, win_w, bands)
        data = image.getData(bandIndices=None, window=(r_min, c_min, win_h, win_w))

        # Crop mask to the same window
        sub_mask = mask[r_min : r_max + 1, c_min : c_max + 1]

        # Extract pixels: (n_pixels, bands)
        pixels = data[sub_mask]

        # Handle nodata
        nodata = image.nodata
        if nodata is not None:
            valid = ~np.all(pixels == nodata, axis=1)
            pixels = pixels[valid]

        if len(pixels) == 0:
            nbands = data.shape[2] if data.ndim == 3 else 1
            return {
                "mean": np.zeros(nbands),
                "std": np.zeros(nbands),
                "min": np.zeros(nbands),
                "max": np.zeros(nbands),
                "pixel_count": 0,
            }

        return {
            "mean": np.mean(pixels, axis=0).astype(np.float64),
            "std": np.std(pixels, axis=0).astype(np.float64),
            "min": np.min(pixels, axis=0),
            "max": np.max(pixels, axis=0),
            "pixel_count": len(pixels),
        }

    # --- Convenience ---

    # Default colors cycle for auto-assigned ROI colors
    _DEFAULT_COLORS = [
        (255, 0, 0, 128),
        (0, 255, 0, 128),
        (0, 0, 255, 128),
        (255, 255, 0, 128),
        (255, 0, 255, 128),
        (0, 255, 255, 128),
    ]

    def addROIFromDrawing(
        self,
        geometry: BaseGeometry,
        roiType: ROIMode,
    ) -> int:
        """Add an ROI from a drawing tool result, auto-generating name and color."""
        idx = len(self) % len(self._DEFAULT_COLORS)
        color = self._DEFAULT_COLORS[idx]
        name = f"ROI {self._nextFid + 1}"
        return self.addROI(geometry=geometry, name=name, color=color, roiType=roiType)

    # --- File I/O ---

    def toFile(self, path: str, driver: str | None = None) -> None:
        """Export the collection to a geospatial file.

        Driver is auto-detected from extension if not given.
        Supports: .geojson (GeoJSON), .gpkg (GeoPackage), .shp (Shapefile).
        """
        if len(self._gdf) == 0:
            logger.warning("No ROIs to export")
            return

        gdf = self._gdf.copy()

        # Serialize color tuples to hex strings for file compatibility
        gdf["color"] = gdf["color"].apply(
            lambda c: "#{:02x}{:02x}{:02x}{:02x}".format(*c)
        )
        # Serialize ROIMode enum to string
        gdf["roi_type"] = gdf["roi_type"].apply(lambda m: m.name)

        if driver is None:
            ext = path.rsplit(".", 1)[-1].lower()
            driver = {
                "geojson": "GeoJSON",
                "gpkg": "GPKG",
                "shp": "ESRI Shapefile",
            }.get(ext)
            if driver is None:
                raise ValueError(f"Cannot determine driver for extension '.{ext}'")

        if self._crs is None:
            logger.warning(
                "Exporting ROIs without CRS — pixel-space geometries have no "
                "geospatial meaning in the output file."
            )

        gdf.to_file(path, driver=driver)

    @classmethod
    def fromFile(
        cls,
        path: str,
        crs: CRS | None = None,
        transform: Affine | None = None,
    ) -> ROICollection:
        """Import ROIs from a geospatial file.

        Args:
            path: Path to .geojson, .gpkg, or .shp file.
            crs: Override CRS (if None, uses the file's CRS).
            transform: Affine transform for the collection.
        """
        gdf = gpd.read_file(path)

        file_crs = crs or (CRS(gdf.crs) if gdf.crs is not None else None)
        file_transform = transform or Affine.identity()
        collection = cls(crs=file_crs, transform=file_transform)

        for _, row in gdf.iterrows():
            # Deserialize color from hex string
            hex_color = row.get("color", "#ff000080")
            if isinstance(hex_color, str) and hex_color.startswith("#"):
                hex_color = hex_color.lstrip("#")
                color = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4, 6))
            else:
                color = (255, 0, 0, 128)

            # Deserialize ROIMode from string
            roi_type_str = row.get("roi_type", "POLYGON")
            try:
                roi_type = ROIMode[roi_type_str]
            except (KeyError, TypeError):
                roi_type = ROIMode.POLYGON

            name = row.get("name", "Imported ROI")
            geometry = row["geometry"]

            # Collect extra properties
            skip = {"name", "color", "roi_type", "geometry"}
            extra = {k: row[k] for k in row.index if k not in skip}

            collection.addROI(geometry, name, color, roi_type, **extra)

        return collection

    # --- Cross-image ---

    def applyToImage(self, targetImage: Any) -> ROICollection:
        """Create a new collection with ROIs mapped to the target image.

        If both source and target have a CRS, geometries are reprojected.
        If CRS is the same, geometries transfer directly.

        Args:
            targetImage: A VardaRaster with crs and transform properties.

        Returns:
            A new ROICollection in the target image's CRS/transform.

        Raises:
            ValueError: If either the source or target lacks a CRS.
        """
        if self._crs is None:
            raise ValueError(
                "Cannot apply pixel-space ROIs to another image. "
                "Source collection has no CRS."
            )
        target_crs = targetImage.crs
        if target_crs is None:
            raise ValueError("Cannot apply ROIs to an image without a CRS.")

        target_collection = ROICollection(
            crs=target_crs, transform=targetImage.transform
        )

        # Reproject if CRS differs, otherwise copy geometries directly
        if self._crs != target_crs:
            reprojected_gdf = self._gdf.to_crs(target_crs)
        else:
            reprojected_gdf = self._gdf

        for fid, row in reprojected_gdf.iterrows():
            extra = {
                k: row[k] for k in row.index if k not in (*_CORE_COLUMNS, "geometry")
            }
            target_collection.addROI(
                geometry=row["geometry"],
                name=row["name"],
                color=row["color"],
                roiType=row["roi_type"],
                **extra,
            )

        return target_collection

    # --- Factory ---

    @classmethod
    def fromImage(cls, image: Any) -> ROICollection:
        """Create an empty collection with CRS/transform from a VardaRaster."""
        return cls(crs=image.crs, transform=image.transform)

    # --- Internal helpers ---

    def _rowToVardaROI(self, fid: int, row: pd.Series) -> VardaROI:
        """Convert a GeoDataFrame row to an immutable VardaROI."""
        # Collect user-defined properties (non-core columns)
        props = {k: row[k] for k in row.index if k not in (*_CORE_COLUMNS, "geometry")}
        return VardaROI(
            fid=fid,
            name=row["name"],
            color=row["color"],
            geometry=row["geometry"],
            roiType=row["roi_type"],
            properties=props,
        )
