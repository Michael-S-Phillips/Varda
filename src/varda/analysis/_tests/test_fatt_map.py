"""The FATT detection map (DAFA/TT) marks where a library target fits."""

import numpy as np
import pytest

from varda.analysis.fatt_map import FattMapAnalysis
from varda.analysis.spectral_library import LibrarySpectrum
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

WAVELENGTHS = np.linspace(1000.0, 2600.0, 160)


def _spectrum(continuum: float, *bands: tuple[float, float, float]) -> np.ndarray:
    s = continuum + 0.05 * (WAVELENGTHS - 1000.0) / 1600.0
    for center, width, depth in bands:
        s = s * (1 - depth * np.exp(-0.5 * ((WAVELENGTHS - center) / width) ** 2))
    return s


KAOLINITE = _spectrum(0.45, (2165, 12, 0.25), (2205, 14, 0.35))
CALCITE = _spectrum(0.4, (2340, 22, 0.35))


def _scene() -> VardaRaster:
    rng = np.random.default_rng(3)
    background = np.stack([_spectrum(0.35, (2285, 18, 0.3)), _spectrum(0.25)])
    cube = rng.dirichlet(np.ones(2), size=(30, 30)) @ background
    patch = rng.uniform(0.2, 0.6, size=(12, 12, 1))
    cube[:12, :12] = (1 - patch) * cube[:12, :12] + patch * KAOLINITE
    cube += rng.normal(scale=2e-4, size=cube.shape)
    cube[29, 29] = -1.0  # no-data
    source = ArrayDataSource(
        cube.astype(np.float32),
        wavelengths=WAVELENGTHS,
        wavelengthUnits="nm",
        nodata=-1.0,
    )
    return VardaRaster(source, name="scene")


def _analysis() -> FattMapAnalysis:
    analysis = FattMapAnalysis(
        [
            LibrarySpectrum("kaolinite", WAVELENGTHS, KAOLINITE),
            LibrarySpectrum("calcite", WAVELENGTHS, CALCITE),
        ]
    )
    analysis.factors.set(4)
    analysis.threshold.set(0.1)  # × 10⁻⁴; the synthetic fits are very clean
    return analysis


def test_the_map_counts_detections_and_keeps_each_targets_fit():
    result = _analysis().run(_scene(), lambda p, m: None)

    assert result.bandNames == [
        "Targets detected",
        "nRMSE: kaolinite",
        "nRMSE: calcite",
    ]
    data = result.getData()
    assert (data[3:9, 3:9, 0] == 1).all()  # kaolinite, inside the patch
    assert (data[20:28, 20:28, 0] == 0).all()  # nothing far from it
    assert np.isnan(data[29, 29]).all()  # no-data stays missing
    assert result.extraMetadata["fatt"]["targets"] == ["kaolinite", "calcite"]


def test_only_the_wavelength_range_is_used():
    analysis = _analysis()
    analysis.minWavelength.set(2100.0)
    analysis.maxWavelength.set(2600.0)
    result = analysis.run(_scene(), lambda p, m: None)
    inRange = int(((WAVELENGTHS >= 2100) & (WAVELENGTHS <= 2600)).sum())
    assert result.extraMetadata["fatt"]["bands"] == [inRange, inRange]


def test_targets_are_needed():
    analysis = FattMapAnalysis()
    assert "target" in analysis.unavailableReason(_scene()).lower()
    with pytest.raises(ValueError):
        analysis.run(_scene(), lambda p, m: None)


def test_each_targets_map_uses_the_bands_it_covers():
    """Ticking a target that covers fewer bands must not change another
    target's map."""
    kaolinite = LibrarySpectrum("kaolinite", WAVELENGTHS, KAOLINITE)
    short = WAVELENGTHS >= 2000
    calcite = LibrarySpectrum("calcite", WAVELENGTHS[short], CALCITE[short])

    alone = FattMapAnalysis([kaolinite])
    both = FattMapAnalysis([kaolinite, calcite])
    for analysis in (alone, both):
        analysis.factors.set(4)
        analysis.threshold.set(0.1)
    image = _scene()
    aloneResult = alone.run(image, lambda p, m: None)
    bothResult = both.run(image, lambda p, m: None)

    np.testing.assert_array_equal(
        aloneResult.getData()[:, :, 1], bothResult.getData()[:, :, 1]
    )
    inRange = (WAVELENGTHS >= 1700) & (WAVELENGTHS <= 2600)  # the default range
    assert bothResult.extraMetadata["fatt"]["bands"] == [
        int(inRange.sum()),
        int((inRange & short).sum()),
    ]


def test_a_target_covering_too_few_bands_is_named():
    tiny = LibrarySpectrum("tiny", WAVELENGTHS[:3], KAOLINITE[:3])
    analysis = FattMapAnalysis(
        [LibrarySpectrum("kaolinite", WAVELENGTHS, KAOLINITE), tiny]
    )
    with pytest.raises(ValueError, match="tiny"):
        analysis.run(_scene(), lambda p, m: None)
