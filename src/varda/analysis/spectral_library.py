"""Spectral libraries and matching unknown spectra against them.

Matching follows ENVI's Spectral Analyst: each library spectrum is resampled
to the unknown's wavelengths and compared three ways, each mapped to a 0-1
score by a linear ramp and combined by weights:

- Spectral angle (radians; 0 is identical shape, brightness ignored)
- Spectral feature fit: continuum-removed absorption depths of the unknown
  fitted by a scaled reference; scored by how well the absorption shapes
  correlate (depth-independent), with the RMS misfit reported
- Binary encoding: the fraction of bands where both spectra are on the same
  side of their own mean

Pure numpy; wavelengths are in nm. Library files declare their unit (ENVI
``wavelength units``, a CSV column name such as ``wavelength_um``, or a
``# units:`` comment); otherwise it is inferred once, with a warning.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

import attrs
import numpy as np
import spectral.io.envi as envi

from varda.analysis import _spy
from varda.common.spectral_axis import nanometresFrom, parseUnit, unitInText
from varda.plotting.library_spectra import (
    DEFAULT_LIBRARY_PATH,
    listSpectra,
    loadSpectrum,
)
from varda.utilities.resources import resource_path

MICA_LIBRARY_NAME = "CRISM MICA numerators"
USGS_LIBRARY_NAME = "USGS minerals"
MICA_LIBRARY_PATH = Path(
    resource_path("resources/spectral_libraries/crism_mica_numerators.csv")
)

LIBRARY_FORMAT_HELP = """\
<p>Load Library accepts three formats. Wavelengths may be in nm, µm or cm⁻¹:
name the unit in the wavelength column (e.g. <code>wavelength_um</code>) or in a
<code># units: µm</code> comment; otherwise Varda infers it. The library is resampled to your image's bands, and
it must overlap at least five of them. Matching ignores overall brightness,
so reflectance, I/F or scaled values all work.</p>

<p><b>CSV</b> (.csv or .txt): the first column is wavelength, every other column
is one spectrum, and the first non-comment row holds the names, e.g.</p>
<pre>
# optional comment lines start with #
wavelength_um,Kaolinite,Nontronite
1.0010,0.512,0.430
1.0075,0.515,0.431
</pre>
<p>Leave a cell empty where a value is missing.</p>

<p><b>ENVI spectral library</b> (.sli with its .hdr): the header needs
<code>spectra names</code>, <code>wavelength</code> and <code>wavelength units</code>,
as written by ENVI or by <code>spectral.envi.SpectralLibrary.save</code>.</p>

<p><b>USGS splib07 folder</b>: pick a folder with one sub-folder per spectrum, each
holding the spectrum's .txt file and its <i>*Wavelengths*.txt</i> file, as
downloaded from the USGS Spectral Library.</p>

<p>For CRISM, compare unratioed I/F endmembers with the <b>MICA numerators</b>
(bundled); ratioed type spectra only match ratioed data.</p>
"""

# Score ramps: a value at "best" scores 1, at "worst" 0, linear between
SAM_RAMP = (0.0, 0.25)  # radians
# Absorptions shallower than this (continuum-removed depth) count as featureless
FEATURELESS_DEPTH = 0.01
BINARY_RAMP = (1.0, 0.5)  # fraction of bands matching (0.5 = chance)
DEFAULT_WEIGHTS = {"angle": 1.0, "featureFit": 1.0, "binary": 1.0}
# Within this fraction of the best score a match is flagged "close"
CLOSE_FRACTION = 0.10


@attrs.frozen
class LibrarySpectrum:
    name: str
    wavelengths: np.ndarray  # nm (the loaders convert declared units)
    reflectance: np.ndarray
    source: str = ""


@attrs.frozen
class LibraryMatch:
    name: str
    score: float  # weighted 0-1, higher is better
    angle: float  # radians
    featureRms: float
    featureScale: float
    binary: float  # fraction of bands matching
    flag: str  # "best", "close" (within 10% of the best score) or "far"
    spectrum: LibrarySpectrum


# --- loading ---------------------------------------------------------------------


def loadUsgsLibrary(path: Path = DEFAULT_LIBRARY_PATH) -> list[LibrarySpectrum]:
    """The USGS splib07a spectra bundled with Varda (one folder per spectrum)."""
    library = []
    for folder in listSpectra(path):
        try:
            name, wavelengths, reflectance = loadSpectrum(path, folder)
        except (FileNotFoundError, ValueError):
            continue
        library.append(LibrarySpectrum(name, wavelengths, reflectance, "USGS splib07a"))
    return library


def loadEnviLibrary(header: str | Path) -> list[LibrarySpectrum]:
    """An ENVI spectral library (.sli + .hdr)."""
    header = Path(header)
    if header.suffix.lower() != ".hdr":
        header = header.with_suffix(".hdr")
    library = envi.open(str(header))
    names = list(library.names)
    unit = parseUnit(library.metadata.get("wavelength units"))
    wavelengths = nanometresFrom(library.bands.centers, unit)
    spectra = np.asarray(library.spectra, dtype=np.float64)
    return [
        LibrarySpectrum(name, wavelengths, spectra[i], header.stem)
        for i, name in enumerate(names)
    ]


def loadCsvLibrary(path: str | Path) -> list[LibrarySpectrum]:
    """A CSV whose first column is wavelength and each other column a spectrum
    (named by its header)."""
    path = Path(path)
    with open(path, newline="") as f:
        allLines = list(f)
    comments = [line for line in allLines if line.lstrip().startswith("#")]
    lines = [line for line in allLines if not line.lstrip().startswith("#")]
    rows = list(csv.reader(lines))
    header, body = rows[0], [r for r in rows[1:] if r]
    values = np.array([[float(v) if v.strip() else np.nan for v in r] for r in body])
    # The unit from the wavelength column's name (e.g. wavelength_um), else a
    # "# units: ..." comment, else inferred from the values
    unitComments = [c for c in comments if "unit" in c.lower()]
    unit = unitInText(header[0]) or next(
        (u for c in unitComments if (u := unitInText(c)) is not None), None
    )
    wavelengths = nanometresFrom(values[:, 0], unit)
    return [
        LibrarySpectrum(name.strip(), wavelengths, values[:, i + 1], path.stem)
        for i, name in enumerate(header[1:])
    ]


def loadBundledLibraries() -> dict[str, list[LibrarySpectrum]]:
    """The spectral libraries shipped with Varda, by display name."""
    libraries = {}
    if MICA_LIBRARY_PATH.is_file():
        libraries[MICA_LIBRARY_NAME] = loadCsvLibrary(MICA_LIBRARY_PATH)
    libraries[USGS_LIBRARY_NAME] = loadUsgsLibrary()
    return libraries


def loadLibrary(path: str | Path) -> list[LibrarySpectrum]:
    """Load a library file by extension (.sli/.hdr ENVI, .csv), or a folder of
    USGS spectra."""
    path = Path(path)
    if path.is_dir():
        return loadUsgsLibrary(path)
    if path.suffix.lower() in {".sli", ".hdr"}:
        return loadEnviLibrary(path)
    if path.suffix.lower() in {".csv", ".txt"}:
        return loadCsvLibrary(path)
    raise ValueError(f"Unsupported spectral library: {path.name}")


# --- comparison ------------------------------------------------------------------


def resampleTo(
    spectrum: LibrarySpectrum,
    wavelengthsNm: np.ndarray,
    fwhmNm: np.ndarray | None = None,
) -> np.ndarray:
    """The library spectrum at the image's bands; NaN outside its range.

    With the bands' FWHM (``bandModel.fwhm``), each band is the library
    weighted by a Gaussian band response (SPy's resampling matrix), so a
    narrow feature is diluted as a wide band would see it; gaps in the
    library are left out of each band's average. Without it, the library is
    linearly interpolated at the band centres. Library wavelengths are in nm.
    """
    x = np.asarray(spectrum.wavelengths, dtype=np.float64)
    y = np.asarray(spectrum.reflectance, dtype=np.float64)
    order = np.argsort(x)
    x, y = x[order], y[order]
    targets = np.asarray(wavelengthsNm, dtype=np.float64)
    if fwhmNm is None:
        keep = np.isfinite(x) & np.isfinite(y)
        return np.interp(targets, x[keep], y[keep], left=np.nan, right=np.nan)
    keepX = np.isfinite(x)
    x, y = x[keepX], y[keepX]
    librarySpacing = np.gradient(x) if x.size > 1 else np.ones_like(x)
    matrix = _spy.resamplingMatrix(
        x, librarySpacing, targets, np.asarray(fwhmNm, float)
    )
    matrix = np.nan_to_num(matrix)
    finite = np.isfinite(y)
    weight = matrix @ finite.astype(np.float64)
    total = matrix.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        values = (matrix @ np.where(finite, y, 0.0)) / weight
    covered = (
        (total > 0) & (weight > 0.5 * total) & (targets >= x[0]) & (targets <= x[-1])
    )
    return np.where(covered, values, np.nan)


def continuumRemoved(wavelengths: np.ndarray, spectrum: np.ndarray) -> np.ndarray:
    """``spectrum`` divided by its upper convex hull (1 on the hull, < 1 in
    absorptions)."""
    x = np.asarray(wavelengths, dtype=np.float64)
    y = np.asarray(spectrum, dtype=np.float64)
    hull: list[int] = []
    for i in range(x.size):  # upper hull, monotone chain
        while len(hull) >= 2:
            a, b = hull[-2], hull[-1]
            cross = (x[b] - x[a]) * (y[i] - y[a]) - (y[b] - y[a]) * (x[i] - x[a])
            if cross >= 0:
                hull.pop()
            else:
                break
        hull.append(i)
    continuum = np.interp(x, x[hull], y[hull])
    with np.errstate(divide="ignore", invalid="ignore"):
        return y / continuum


def featureFit(
    wavelengths: np.ndarray, unknown: np.ndarray, reference: np.ndarray
) -> tuple[float, float]:
    """Spectral feature fitting: least-squares scale of the reference's
    continuum-removed depths onto the unknown's, and the RMS misfit."""
    du = 1.0 - continuumRemoved(wavelengths, unknown)
    dr = 1.0 - continuumRemoved(wavelengths, reference)
    denominator = float(dr @ dr)
    if denominator <= 0:
        return 0.0, float(np.sqrt(np.mean(du**2)))
    scale = float(dr @ du) / denominator
    return scale, float(np.sqrt(np.mean((du - scale * dr) ** 2)))


def featureScore(
    wavelengths: np.ndarray, unknown: np.ndarray, reference: np.ndarray
) -> float:
    """0-1 similarity of the absorption features: the correlation of the
    continuum-removed depth profiles (negative counts as 0). Two featureless
    spectra match; a featureless and a featured one do not."""
    du = 1.0 - continuumRemoved(wavelengths, unknown)
    dr = 1.0 - continuumRemoved(wavelengths, reference)
    flatU = np.nanmax(du) < FEATURELESS_DEPTH
    flatR = np.nanmax(dr) < FEATURELESS_DEPTH
    if flatU or flatR:
        return 1.0 if flatU and flatR else 0.0
    correlation = np.corrcoef(du, dr)[0, 1]
    return float(max(0.0, correlation)) if np.isfinite(correlation) else 0.0


def binaryEncodingMatch(a: np.ndarray, b: np.ndarray) -> float:
    """Fraction of bands where ``a`` and ``b`` are on the same side of their
    own means."""
    return float(np.mean((a > np.mean(a)) == (b > np.mean(b))))


def _ramp(value: float, best: float, worst: float) -> float:
    return float(np.clip((value - worst) / (best - worst), 0.0, 1.0))


def rankLibrary(
    wavelengths: np.ndarray,
    spectrum: np.ndarray,
    library: Sequence[LibrarySpectrum],
    *,
    weights: dict[str, float] | None = None,
    wavelengthRange: tuple[float, float] | None = None,
    fwhm: np.ndarray | None = None,
) -> list[LibraryMatch]:
    """Library spectra ranked by weighted similarity to ``spectrum`` (best
    first). Comparison uses the bands both cover, within ``wavelengthRange``
    (nm) if given; spectra overlapping fewer than five bands are skipped.
    ``wavelengths`` are the unknown's band centres in nm (``bandModel.centers``);
    with their FWHM (nm) the library is resampled through each band's response."""
    weights = DEFAULT_WEIGHTS if weights is None else weights
    total = sum(weights.values()) or 1.0
    x = np.asarray(wavelengths, dtype=np.float64)
    unknown = np.asarray(spectrum, dtype=np.float64)
    inRange = np.isfinite(x) & np.isfinite(unknown)
    if wavelengthRange is not None:
        inRange &= (x >= wavelengthRange[0]) & (x <= wavelengthRange[1])
    matches = []
    for entry in library:
        reference = resampleTo(entry, x, fwhm)
        use = inRange & np.isfinite(reference)
        if np.count_nonzero(use) < 5:
            continue
        u, r, xu = unknown[use], reference[use], x[use]
        cosine = float(u @ r / (np.linalg.norm(u) * np.linalg.norm(r)))
        angle = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
        scale, rms = featureFit(xu, u, r)
        binary = binaryEncodingMatch(u, r)
        score = (
            weights.get("angle", 0.0) * _ramp(angle, *SAM_RAMP)
            + weights.get("featureFit", 0.0) * featureScore(xu, u, r)
            + weights.get("binary", 0.0) * _ramp(binary, *BINARY_RAMP)
        ) / total
        matches.append((entry, score, angle, rms, scale, binary))
    matches.sort(key=lambda m: -m[1])
    best = matches[0][1] if matches else 0.0
    return [
        LibraryMatch(
            name=entry.name,
            score=score,
            angle=angle,
            featureRms=rms,
            featureScale=scale,
            binary=binary,
            flag="best"
            if i == 0
            else "close"
            if score >= best * (1 - CLOSE_FRACTION)
            else "far",
            spectrum=entry,
        )
        for i, (entry, score, angle, rms, scale, binary) in enumerate(matches)
    ]
