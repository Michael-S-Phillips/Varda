"""Write a VardaRaster to disk as ENVI (.img + .hdr) or GeoTIFF.

The metadata written is what Varda's own data sources read back: ENVI header
items (wavelength, wavelength units, band names, default bands, description)
for ENVI, and the equivalent GDAL tags plus band descriptions for GeoTIFF.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from varda.common.entities import VardaRaster

ENVI_SUFFIXES = frozenset({".img", ".hdr"})
GEOTIFF_SUFFIXES = frozenset({".tif", ".tiff"})
SAVE_FILE_FILTER = "ENVI image (*.img *.hdr);;GeoTIFF (*.tif *.tiff)"


def suggestedOutputPath(image: VardaRaster, stem: str | None = None) -> Path:
    """An ENVI path next to the image's file (or in the home directory)."""
    folder = Path(image.filePath).parent if image.filePath else Path.home()
    return folder / f"{stem or image.name}.img"


def writeRaster(image: VardaRaster, path: str | Path) -> Path:
    """Write ``image`` to ``path``; the format follows the suffix (ENVI when
    there is none). Returns the path of the data file written (for ENVI the
    ``.img``; its ``.hdr`` sits beside it)."""
    target = Path(path)
    suffix = target.suffix.lower()
    if suffix == "":
        target, suffix = target.with_suffix(".img"), ".img"
    if suffix in ENVI_SUFFIXES:
        target, driver = target.with_suffix(".img"), "ENVI"
    elif suffix in GEOTIFF_SUFFIXES:
        driver = "GTiff"
    else:
        raise ValueError(
            f"Cannot write '{suffix}' files; use ENVI (.img/.hdr) or GeoTIFF (.tif)."
        )

    data = np.asarray(image.getData())
    if data.ndim == 2:
        data = data[:, :, np.newaxis]
    names = [str(name) for name in image.bandNames]
    wavelengths = [str(w) for w in image.wavelengths]
    displayBands = [str(int(b) + 1) for b in image.defaultBands]  # ENVI is 1-based

    profile = {
        "driver": driver,
        "height": data.shape[0],
        "width": data.shape[1],
        "count": data.shape[2],
        "dtype": data.dtype.name,
        "crs": rasterio.CRS.from_wkt(image.crs.to_wkt()) if image.crs else None,
        "transform": image.transform,
        "nodata": image.nodata,
    }
    if driver == "GTiff":
        profile["BIGTIFF"] = "IF_SAFER"

    with rasterio.open(target, "w", **profile) as dst:
        dst.write(np.moveaxis(data, 2, 0))
        for i, name in enumerate(names, start=1):
            dst.set_band_description(i, name)
        if driver == "ENVI":
            dst.update_tags(
                ns="ENVI",
                wavelength=_enviList(wavelengths),
                wavelength_units=image.wavelengthUnits,
                band_names=_enviList(names),
                default_bands=_enviList(displayBands),
                description=image.dataSource.description,
            )
        else:
            dst.update_tags(
                wavelength=", ".join(wavelengths),
                wavelength_units=image.wavelengthUnits,
                description=image.dataSource.description,
            )
            for i, name in enumerate(names, start=1):
                dst.update_tags(i, name=name)
    return target


def _enviList(items: list[str]) -> str:
    return "{" + ", ".join(items) + "}"
