"""``Varda --self-test``: check that a build works before it is released.

Runs the real application, then exercises what a frozen bundle most often
breaks: package metadata, bundled resources, PROJ data, reading and writing
files in background threads, numba-compiled rendering, the analyses that
lean on optional libraries, and the certificates the update check needs. Prints one line per check and returns the exit
code (0 when everything passed).
"""

import importlib
import ssl
import tempfile
import time
import traceback
from collections.abc import Callable
from pathlib import Path

import certifi
import numpy as np
from affine import Affine
from pyproj import Transformer
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication
from rasterio.crs import CRS

from varda.analysis.band_parameters import BandParametersAnalysis
from varda.analysis.transforms import PcaAnalysis
from varda.app import VardaApplication
from varda.branding.title_mark import ICON_DIR
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_loading.image_loading_service import ImageLoadingService
from varda.image_loading.raster_writer import writeRaster
from varda.image_rendering.image_renderer import ImageRenderer
from varda.version import vardaVersion

LOAD_TIMEOUT_S = 60
SHAPE = (16, 16, 60)  # rows, columns, bands
CRS_EPSG = 32612


def runSelfTest(app: VardaApplication) -> int:
    image = _sampleImage()
    with tempfile.TemporaryDirectory() as folder:
        checks: list[tuple[str, Callable[[], str]]] = [
            ("main window", lambda: _mainWindow(app)),
            ("version", _version),
            ("brand assets", _brandAssets),
            ("coordinate systems", _coordinateSystems),
            ("ENVI write and read", lambda: _roundTrip(image, Path(folder) / "a.img")),
            (
                "GeoTIFF write and read",
                lambda: _roundTrip(image, Path(folder) / "a.tif"),
            ),
            ("rendering", lambda: _render(image)),
            ("PCA (SPy)", lambda: _pca(image)),
            ("band parameters (HyPyRameter)", lambda: _bandParameters(image)),
            ("plugin API", _pluginApi),
            ("update check certificates", _updateCertificates),
        ]
        failures = sum(not _report(name, check) for name, check in checks)
    print(f"Self-test: {len(checks) - failures} of {len(checks)} checks passed")
    return 1 if failures else 0


def _report(name: str, check: Callable[[], str]) -> bool:
    try:
        detail = check()
    except Exception:
        print(f"FAIL {name}\n{traceback.format_exc()}", flush=True)
        return False
    print(f"PASS {name}: {detail}", flush=True)
    return True


def _sampleImage() -> VardaRaster:
    rows, columns, bands = SHAPE
    rng = np.random.default_rng(0)
    data = rng.uniform(0.1, 0.5, SHAPE).astype(np.float32)
    source = ArrayDataSource(
        data,
        wavelengths=np.linspace(400.0, 2500.0, bands),
        wavelengthUnits="Nanometers",
        crs=CRS.from_epsg(CRS_EPSG),
        transform=Affine(30.0, 0.0, 500000.0, 0.0, -30.0, 3500000.0),
    )
    return VardaRaster(dataSource=source, name="self-test")


def _mainWindow(app: VardaApplication) -> str:
    assert app.maingui is not None and app.maingui.isVisible()
    return app.maingui.windowTitle() or "shown"


def _version() -> str:
    version = vardaVersion()
    assert version != "unknown", "package metadata is missing"
    return version


def _brandAssets() -> str:
    icons = sorted(ICON_DIR.glob("*.svg"))
    assert icons, f"no icons in {ICON_DIR}"
    broken = [icon.name for icon in icons if not QSvgRenderer(str(icon)).isValid()]
    assert not broken, f"unreadable: {broken}"
    return f"{len(icons)} icons"


def _coordinateSystems() -> str:
    toLonLat = Transformer.from_crs(CRS_EPSG, 4326, always_xy=True)
    lon, lat = toLonLat.transform(500000.0, 3500000.0)
    assert np.isfinite([lon, lat]).all()
    return f"EPSG:{CRS_EPSG} -> ({lon:.3f}, {lat:.3f})"


def _roundTrip(image: VardaRaster, path: Path) -> str:
    written = writeRaster(image, path)
    loaded = _load(written)
    try:
        assert loaded.shape == image.shape, f"{loaded.shape} != {image.shape}"
        np.testing.assert_allclose(loaded.wavelengths, image.wavelengths, rtol=1e-4)
        assert loaded.crs is not None and loaded.crs.to_epsg() == CRS_EPSG
        return f"{written.name} {loaded.shape}"
    finally:
        loaded.close()  # Windows can't delete a file that is still open


def _load(path: Path) -> VardaRaster:
    """Load through the app's background loader, as File > Import does."""
    results: list[VardaRaster | str] = []
    ImageLoadingService.load_image_data(str(path), results.append, results.append)
    deadline = time.monotonic() + LOAD_TIMEOUT_S
    while not results and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    assert results, f"timed out loading {path.name}"
    result = results[0]
    assert isinstance(result, VardaRaster), result
    return result


def _render(image: VardaRaster) -> str:
    rgba = ImageRenderer(image).render()
    assert rgba.shape == (*SHAPE[:2], 4), rgba.shape
    return f"{rgba.shape}"


def _pca(image: VardaRaster) -> str:
    result = PcaAnalysis().run(image, lambda _percent, _message: None)
    assert result.bandCount > 0
    return f"{result.bandCount} components"


def _pluginApi() -> str:
    """Plugins import varda.api, which nothing in Varda imports itself, so a
    bundle can silently leave it out."""
    api = importlib.import_module("varda.api")
    missing = [name for name in api.__all__ if not hasattr(api, name)]
    assert not missing, f"varda.api lacks {missing}"
    return f"API {api.API_VERSION}, {len(api.__all__)} names"


def _updateCertificates() -> str:
    """The HTTPS certificates the update check uses are bundled. Offline: the
    self-test never contacts GitHub."""
    context = ssl.create_default_context(cafile=certifi.where())
    count = len(context.get_ca_certs())
    assert count, f"no certificates in {certifi.where()}"
    return f"{count} certificates"


def _bandParameters(image: VardaRaster) -> str:
    analysis = BandParametersAnalysis()
    assert analysis.isAvailable(), "HyPyRameter is not installed"
    analysis.prepareFor(image)
    choices = analysis.parameters.choices
    assert choices, "no parameters for 400-2500 nm"
    analysis.parameters.set(choices[:2])
    result = analysis.run(image, lambda _percent, _message: None)
    return f"{', '.join(result.bandNames)}"
