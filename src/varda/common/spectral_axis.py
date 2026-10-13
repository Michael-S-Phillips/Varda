"""The spectral axis of a raster.

Unit strings are parsed here, once, and every calculation works in
nanometres. ``BandModel`` carries what a spectral analysis needs about the
bands: centres in nm (or None when the bands aren't a spectral axis, e.g.
band indices, labels or parameter images), FWHM in nm, the bad-band mask
(ENVI ``bbl``), the reflectance scale factor and the no-data value.

When a file declares no unit, ``bandModelFor`` infers one from the values and
logs that it did; nothing else in Varda guesses units.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from enum import Enum

import attrs
import numpy as np
import numpy.typing as npt

logger = logging.getLogger(__name__)


class SpectralUnit(Enum):
    NANOMETRE = "nm"
    MICROMETRE = "µm"
    WAVENUMBER = "cm⁻¹"


_ALIASES = {
    SpectralUnit.NANOMETRE: {
        "nm",
        "nanometer",
        "nanometers",
        "nanometre",
        "nanometres",
    },
    SpectralUnit.MICROMETRE: {
        "um",
        "µm",
        "μm",
        "micron",
        "microns",
        "micrometer",
        "micrometers",
        "micrometre",
        "micrometres",
    },
    SpectralUnit.WAVENUMBER: {
        "wavenumber",
        "wavenumbers",
        "cm-1",
        "cm^-1",
        "1/cm",
        "cm⁻¹",
    },
}
_LOOKUP = {alias: unit for unit, aliases in _ALIASES.items() for alias in aliases}

# Keys under which readers expose ENVI band metadata (GDAL's ENVI domain uses
# underscores); derived rasters carry the same keys in extraMetadata.
FWHM_KEY = "fwhm"
BBL_KEY = "bbl"
SCALE_KEY = "reflectance_scale_factor"
BAND_METADATA_KEYS = (FWHM_KEY, BBL_KEY, SCALE_KEY)

MAX_MICROMETRES = 30.0  # undeclared values below this are taken as µm (to thermal IR)


def parseUnit(text: str | None) -> SpectralUnit | None:
    """The unit named by ``text``, or None (unknown, parameters, indices...)."""
    if not text:
        return None
    return _LOOKUP.get(text.strip().lower())


def unitInText(text: str) -> SpectralUnit | None:
    """A unit named anywhere in ``text``, e.g. ``wavelength_um`` or
    ``Wavelength (nm)`` or ``# units: micrometers``."""
    for token in re.split(r"[^\w µμ⁻^/-]+|[_\s]+", text.lower()):
        unit = parseUnit(token.strip("()[]"))
        if unit is not None:
            return unit
    return None


def nanometresFrom(values: npt.ArrayLike, unit: SpectralUnit | None) -> np.ndarray:
    """Wavelengths in nm; an undeclared unit is inferred from the values (logged)."""
    array = np.asarray(values, dtype=np.float64)
    if unit is None:
        unit = _inferUnit(array)
    return toNanometres(array, unit)


def toNanometres(values: npt.ArrayLike, unit: SpectralUnit) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if unit is SpectralUnit.MICROMETRE:
        return array * 1000.0
    if unit is SpectralUnit.WAVENUMBER:
        with np.errstate(divide="ignore"):
            return 1e7 / array
    return array.copy()


def fromNanometres(values: npt.ArrayLike, unit: SpectralUnit) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if unit is SpectralUnit.MICROMETRE:
        return array / 1000.0
    if unit is SpectralUnit.WAVENUMBER:
        with np.errstate(divide="ignore"):
            return 1e7 / array
    return array.copy()


def unitLabel(unit: SpectralUnit | None, declared: str = "") -> str:
    """Short label for axes and band names: nm, µm or cm⁻¹ (or the declared text)."""
    return unit.value if unit is not None else declared


def parseEnviList(value) -> list[float] | None:
    """An ENVI ``{ a , b , c }`` list (or a sequence already) as floats."""
    if value is None:
        return None
    if isinstance(value, str):
        items = [item for item in re.split(r"[\s,{}]+", value) if item]
        return [float(item) for item in items]
    return [float(item) for item in value]


def _inferUnit(values: np.ndarray) -> SpectralUnit:
    unit = (
        SpectralUnit.MICROMETRE
        if np.nanmax(values) < MAX_MICROMETRES
        else SpectralUnit.NANOMETRE
    )
    logger.warning(
        "Wavelength units not declared; assuming %s from the values (%.4g-%.4g)",
        unit.value,
        np.nanmin(values),
        np.nanmax(values),
    )
    return unit


def _isNumeric(wavelengths: np.ndarray) -> bool:
    return wavelengths.dtype.kind in "fiu" and wavelengths.size > 0


def _isBandIndexList(wavelengths: np.ndarray) -> bool:
    return bool(np.array_equal(wavelengths, np.arange(wavelengths.size)))


@attrs.frozen
class BandModel:
    bandCount: int
    centers: np.ndarray | None = None  # nm; None: not a spectral axis
    unit: SpectralUnit | None = None  # the unit of the source's own values
    declaredUnits: str = ""
    unitWasInferred: bool = False
    fwhm: np.ndarray | None = None  # nm
    badBands: np.ndarray = attrs.field(factory=lambda: np.zeros(0, dtype=bool))
    scaleFactor: float | None = None
    noData: float | None = None

    @classmethod
    def empty(cls, bandCount: int) -> BandModel:
        return cls(bandCount, badBands=np.zeros(bandCount, dtype=bool))

    @property
    def isSpectral(self) -> bool:
        return self.centers is not None

    def native(self, nanometres: npt.ArrayLike) -> np.ndarray:
        """Nanometres in the source's own unit (for labels and settings)."""
        if self.unit is None:
            return np.asarray(nanometres, dtype=np.float64)
        return fromNanometres(nanometres, self.unit)

    @property
    def label(self) -> str:
        return unitLabel(self.unit, self.declaredUnits)


def bandModelFor(
    wavelengths: npt.ArrayLike,
    wavelengthUnits: str | None,
    noData: float | None,
    extraMetadata: Mapping,
    bandCount: int,
) -> BandModel:
    """The band model of a raster from what every data source exposes."""
    values = np.asarray(wavelengths)
    declared = wavelengthUnits or ""
    unit = parseUnit(declared)
    inferred = False
    centers = None
    if _isNumeric(values) and values.size == bandCount:
        if unit is None and declared.strip().lower() not in ("parameter", "parameters"):
            if not _isBandIndexList(values):
                unit, inferred = _inferUnit(values.astype(np.float64)), True
        if unit is not None:
            centers = toNanometres(values, unit)

    def bandList(key: str) -> np.ndarray | None:
        try:
            parsed = parseEnviList(extraMetadata.get(key))
        except ValueError:
            parsed = None
        if parsed is None:
            return None
        if len(parsed) != bandCount:
            logger.warning(
                "Ignoring %s: %d values for %d bands", key, len(parsed), bandCount
            )
            return None
        return np.asarray(parsed, dtype=np.float64)

    fwhm = bandList(FWHM_KEY)
    if fwhm is not None and unit is SpectralUnit.WAVENUMBER and centers is not None:
        # a width in cm⁻¹ around a centre, in nm
        native = np.asarray(values, dtype=np.float64)
        fwhm = np.abs(
            toNanometres(native - fwhm / 2, unit)
            - toNanometres(native + fwhm / 2, unit)
        )
    elif fwhm is not None and unit is not None:
        fwhm = toNanometres(fwhm, unit)
    bbl = bandList(BBL_KEY)
    scale = extraMetadata.get(SCALE_KEY)
    try:
        scaleFactor = float(scale) if scale not in (None, "") else None
    except (TypeError, ValueError):
        scaleFactor = None
    return BandModel(
        bandCount=bandCount,
        centers=centers,
        unit=unit,
        declaredUnits=declared,
        unitWasInferred=inferred,
        fwhm=fwhm if centers is not None else None,
        badBands=(bbl == 0) if bbl is not None else np.zeros(bandCount, dtype=bool),
        scaleFactor=scaleFactor,
        noData=noData,
    )
