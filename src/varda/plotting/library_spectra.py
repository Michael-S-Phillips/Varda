from pathlib import Path

import numpy as np

_MISSING_VALUE_THRESHOLD = -1e30
DEFAULT_LIBRARY_PATH = Path(__file__).parent.parent.parent.parent / "librarySpectra"


def _readDataFile(path: Path) -> np.ndarray:
    """Read a one-value-per-line USGS .txt file, skipping the header line."""
    values = []
    with open(path) as f:
        next(f)  # skip header
        for line in f:
            line = line.strip()
            if line:
                values.append(float(line))
    arr = np.array(values, dtype=float)
    arr[arr < _MISSING_VALUE_THRESHOLD] = np.nan
    return arr


def loadSpectrum(folder: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load a USGS library spectrum from its folder.

    Returns (wavelengths_nm, reflectance) where wavelengths have been
    converted from micrometers to nanometers.
    """
    reflectance_path = folder / (folder.name + ".txt")
    wavelength_paths = list(folder.glob("*Wavelengths*.txt"))
    if not wavelength_paths:
        raise FileNotFoundError(f"No wavelength file found in {folder}")

    reflectance = _readDataFile(reflectance_path)
    wavelengths_um = _readDataFile(wavelength_paths[0])
    wavelengths_nm = wavelengths_um * 1000.0
    return wavelengths_nm, reflectance


def listSpectra(library_path: Path = DEFAULT_LIBRARY_PATH) -> list[str]:
    """Return sorted names of all spectrum folders in the library path."""
    if not library_path.is_dir():
        return []
    return sorted(p.name for p in library_path.iterdir() if p.is_dir())
