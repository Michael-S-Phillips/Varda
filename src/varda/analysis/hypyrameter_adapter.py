"""Drive HyPyRameter's spectral-parameter library on an in-memory cube.

HyPyRameter's ``cubeParamCalculator`` is built around ENVI files and interactive
dialogs, but its parameter methods themselves only read ``self.cube``/``self.f``
(the reflectance cube) and ``self.wvt`` (wavelengths in nm) and call
``hypyrameter.utils``. This module creates the calculator without running its
constructor, supplies those attributes, and calls the parameter methods
directly.

HyPyRameter is an optional dependency: ``HYPYRAMETER_AVAILABLE`` says whether it
could be imported, and the functions here raise ``ImportError`` otherwise.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import sys
import types
from collections.abc import Callable, Sequence

import numpy as np

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], None]

# HyPyRameter accepts a parameter whose wavelength bounds lie this far (nm)
# outside the image's range (its determineValidParams tolerance).
WAVELENGTH_TOLERANCE_NM = 5.0

# Methods of cubeParamCalculator that are not spectral parameters.
_NON_PARAMETER_METHODS = frozenset(
    {
        "denoiser",
        "previewData",
        "determineValidParams",
        "calculateParams",
        "calculateBrowse",
        "saveParamCube",
        "run",
    }
)


def _stubTkinterIfMissing() -> None:
    """HyPyRameter imports tkinter at module level for its own file dialogs,
    which Varda never uses. Pythons built without Tk (MacPorts, minimal Linux)
    would fail to import it, so give them an inert stand-in."""
    if importlib.util.find_spec("_tkinter") is not None:
        return
    filedialog = types.ModuleType("tkinter.filedialog")
    tkinter = types.ModuleType("tkinter")
    setattr(tkinter, "filedialog", filedialog)
    sys.modules.setdefault("tkinter", tkinter)
    sys.modules.setdefault("tkinter.filedialog", filedialog)


_Calculator: type | None
try:
    _stubTkinterIfMissing()
    from hypyrameter.paramCalculator import cubeParamCalculator

    _Calculator = cubeParamCalculator
    HYPYRAMETER_AVAILABLE = True
except ImportError as error:  # the optional "hypyrameter" extra is not installed
    logger.info("HyPyRameter unavailable (%s); Band Parameters disabled", error)
    _Calculator = None
    HYPYRAMETER_AVAILABLE = False


def toNanometres(wavelengths) -> np.ndarray:
    """Wavelengths in nm; values below 10 are taken to be micrometres, as
    HyPyRameter itself assumes."""
    values = np.asarray(wavelengths, dtype=np.float64)
    if values.size and np.nanmax(values) < 10.0:
        return values * 1000.0
    return values


def parameterNames() -> list[str]:
    """HyPyRameter's spectral parameters, in its definition order (some later
    parameters depend on earlier ones)."""
    calculator = _require()
    names = []
    for name, member in vars(calculator).items():
        if name.startswith("_") or name in _NON_PARAMETER_METHODS:
            continue
        if not inspect.isfunction(member):
            continue
        if "check" not in inspect.signature(member).parameters:
            continue
        names.append(name)
    return names


def parameterBounds(name: str) -> tuple[float, float]:
    """(min, max) wavelength in nm that a parameter needs."""
    low, high = getattr(_require(), name)(_shell(), check=True)
    return float(low), float(high)


def validParameterNames(wavelengthsNm) -> list[str]:
    """The parameters an image with these wavelengths (nm) can support."""
    values = np.asarray(wavelengthsNm, dtype=np.float64)
    low, high = float(np.nanmin(values)), float(np.nanmax(values))
    return [
        name for name in parameterNames() if _covers(parameterBounds(name), low, high)
    ]


def _covers(bounds: tuple[float, float], low: float, high: float) -> bool:
    return (
        bounds[0] > low - WAVELENGTH_TOLERANCE_NM
        and bounds[1] < high + WAVELENGTH_TOLERANCE_NM
    )


def computeParameterCube(
    cube,
    wavelengthsNm,
    names: Sequence[str],
    reportProgress: ProgressCallback | None = None,
) -> np.ndarray:
    """(rows, cols, len(names)) float32 cube of the named parameters.

    Parameters are computed in the given order, as HyPyRameter does: BDI1000VIS
    uses the reflectance peak that RPEAK1 leaves on the calculator.
    """
    calculator = _require()
    shell = _shell(np.asarray(cube, dtype=np.float64), toNanometres(wavelengthsNm))
    layers = []
    for i, name in enumerate(names):
        method = getattr(calculator, name)
        if name == "BDI1000VIS" and hasattr(shell, "rpeak_reflectance"):
            layer = method(shell, rp_r=shell.rpeak_reflectance)
        else:
            layer = method(shell)
        layers.append(np.asarray(layer, dtype=np.float32))
        if reportProgress is not None:
            reportProgress(int(round(100 * (i + 1) / len(names))), name)
    return np.dstack(layers)


def _require() -> type:
    if _Calculator is None:
        raise ImportError(
            "HyPyRameter is not installed; install Varda's 'hypyrameter' extra."
        )
    return _Calculator


def _shell(cube: np.ndarray | None = None, wavelengthsNm: np.ndarray | None = None):
    """A cubeParamCalculator with just the state its parameter methods read,
    bypassing the constructor (which opens file dialogs and reads ENVI files)."""
    calculator = object.__new__(_require())  # instance without running __init__
    calculator.f = cube
    calculator.cube = cube
    calculator.wvt = [] if wavelengthsNm is None else [float(w) for w in wavelengthsNm]
    return calculator
