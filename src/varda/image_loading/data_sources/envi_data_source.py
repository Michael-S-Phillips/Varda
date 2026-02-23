"""
ENVIDataSource: extends RasterioDataSource with ENVI-specific metadata parsing.

Reads ENVI namespace tags to extract wavelengths, band names, wavelength units,
default bands, and parameter image detection. Consolidates the metadata parsing
logic that was previously in envi_image_loader.py.
"""

from __future__ import annotations

import logging
from functools import cached_property

import numpy as np

from .rasterio_data_source import RasterioDataSource
from .registry import register_data_source

logger = logging.getLogger(__name__)


@register_data_source("ENVI Image", (".hdr", ".img"))
class ENVIDataSource(RasterioDataSource):
    """DataSource for ENVI format images.

    Opens the ``.img`` file via rasterio and reads ENVI-specific metadata
    from the ``ENVI`` namespace tags.
    """

    def __init__(self, filePath: str):
        # Ensure we open the .img file, not the .hdr
        path = filePath.replace(".hdr", ".img")
        super().__init__(path)
        # Keep the original path the user provided (could be .hdr)
        self._userFilePath = filePath
        self._enviTags: dict[str, str] = self._src.tags(ns="ENVI")

    @property
    def filePath(self) -> str:
        return self._userFilePath

    @cached_property
    def wavelengths(self) -> np.ndarray:
        wavelengthUnitsLower = self._enviTags.get("wavelength_units", "").lower()

        if "wavelength" in self._enviTags:
            wlStrings = [
                w.strip() for w in self._enviTags["wavelength"].strip("{}").split(",")
            ]

            # Check if units indicate parameter names
            if wavelengthUnitsLower in ("parameters", "parameter"):
                logger.debug("Using spectral parameter names as wavelengths")
                return np.asarray(wlStrings, dtype="U50")

            # Try numeric parse
            try:
                return np.asarray([float(w) for w in wlStrings])
            except ValueError:
                # Fall back to string labels
                logger.debug("Falling back to parameter names for wavelengths")
                return np.asarray(wlStrings, dtype="U50")

        # Try to extract from band names
        bn = self._rawBandNames
        if bn is not None:
            try:
                return np.asarray([float(name) for name in bn])
            except ValueError:
                return np.asarray(bn, dtype="U50")

        # Last resort: band indices
        logger.debug("No wavelength information found, using band indices")
        return np.arange(self.bandCount)

    @cached_property
    def wavelengthsType(self) -> type:
        wl = self.wavelengths
        if wl.dtype.kind == "f":
            return float
        elif wl.dtype.kind == "i":
            return int
        return str

    @cached_property
    def wavelengthUnits(self) -> str:
        return self._enviTags.get("wavelength_units", "Unknown")

    @cached_property
    def _rawBandNames(self) -> list[str] | None:
        """Raw band names from ENVI tags, or None if not present."""
        if "band_names" in self._enviTags:
            return [
                name.strip()
                for name in self._enviTags["band_names"].strip("{}").split(",")
            ]
        return None

    @cached_property
    def bandNames(self) -> list[str]:
        raw = self._rawBandNames
        if raw is not None:
            return raw
        # Fall back to wavelength strings or generic names
        if "wavelength" in self._enviTags:
            return [
                w.strip() for w in self._enviTags["wavelength"].strip("{}").split(",")
            ]
        return [f"Band {i + 1}" for i in range(self.bandCount)]

    @cached_property
    def isParameterImage(self) -> bool:
        """True if this is a parameter image (band names represent parameters, not wavelengths)."""
        wlUnits = self._enviTags.get("wavelength_units", "").lower()
        if wlUnits in ("parameters", "parameter"):
            return True
        # Also consider it parameterized if band_names present but no numeric wavelengths
        if self._rawBandNames is not None and self.wavelengthsType is str:
            return True
        return False

    @cached_property
    def defaultBands(self) -> np.ndarray:
        """Default RGB band indices for display (zero-based)."""
        defaultBandsStr = self._enviTags.get("default_bands")
        if defaultBandsStr:
            bandTokens = [
                band.strip() for band in defaultBandsStr.strip("{}").split(",")
            ]
            try:
                # Try as numeric indices (ENVI uses 1-based, convert to 0-based)
                indices = [int(band) - 1 for band in bandTokens]
            except ValueError:
                # Try to match by band name
                raw = self._rawBandNames
                if raw:
                    indices = []
                    for name in bandTokens:
                        try:
                            indices.append(raw.index(name))
                        except ValueError:
                            logger.warning(
                                f"Default band '{name}' not found in band names"
                            )
                else:
                    indices = [0, 1, 2] if self.bandCount >= 3 else [0, 0, 0]

            # Ensure at least 3 indices
            while len(indices) < 3:
                indices.append(0)

            # Clamp to valid range
            maxBand = self.bandCount - 1
            indices = [min(max(idx, 0), maxBand) for idx in indices[:3]]
            return np.array(indices, dtype=np.uint)

        # Default: first 3 bands or band 0 repeated
        if self.bandCount >= 3:
            return np.array([0, 1, 2], dtype=np.uint)
        return np.array([0, 0, 0], dtype=np.uint)

    @cached_property
    def extraMetadata(self) -> dict[str, str]:
        """Extra ENVI metadata not captured by standard properties."""
        skip = {
            "description",
            "default_bands",
            "wavelength_units",
            "band_names",
            "wavelength",
            "geospatial_info",
        }
        return {k: v for k, v in self._enviTags.items() if k not in skip}

    @cached_property
    def description(self) -> str:
        return self._enviTags.get("description", "").strip("{}")

    def __repr__(self) -> str:
        return f"ENVIDataSource({self._userFilePath!r}, {self.width}x{self.height}x{self.bandCount})"
