"""The Band Parameters analysis produces a parameter image over the source's footprint."""

import numpy as np
import pytest

from varda.analysis.band_parameters import BandParametersAnalysis
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


def _reflectanceImage() -> VardaRaster:
    rng = np.random.default_rng(1)
    wavelengths = np.arange(400.0, 2601.0, 10.0)
    cube = 0.2 + 0.1 * rng.random((6, 5, wavelengths.size))
    return VardaRaster(
        ArrayDataSource(cube, wavelengths=wavelengths, wavelengthUnits="nm"),
        name="scene",
    )


def test_unavailable_without_hypyrameter(monkeypatch):
    from varda.analysis import band_parameters

    monkeypatch.setattr(band_parameters, "HYPYRAMETER_AVAILABLE", False)
    assert not BandParametersAnalysis.isAvailable()


def test_band_parameters_image_has_one_band_per_valid_parameter():
    pytest.importorskip("hypyrameter")
    from varda.analysis.hypyrameter_adapter import validParameterNames

    image = _reflectanceImage()
    result = BandParametersAnalysis().run(image, lambda p, m: None)

    names = validParameterNames(image.wavelengths)
    assert result.name == "scene parameters"
    assert result.bandNames == names
    assert list(result.wavelengths) == names  # string "wavelengths" name the bands
    assert result.bandCount == len(names)
    assert result.width == image.width and result.height == image.height
    assert result.transform == image.transform


def test_string_wavelengths_are_rejected_with_a_clear_message():
    pytest.importorskip("hypyrameter")
    image = VardaRaster(
        ArrayDataSource(np.zeros((4, 4, 3)), wavelengths=np.array(["a", "b", "c"])),
        name="bands",
    )
    with pytest.raises(ValueError, match="numeric wavelengths"):
        BandParametersAnalysis().run(image, lambda p, m: None)


def _twin(image: VardaRaster, cube, wavelengths, units, extra=None) -> VardaRaster:
    return VardaRaster(
        ArrayDataSource(
            cube,
            wavelengths=wavelengths,
            wavelengthUnits=units,
            extraMetadata=extra or {},
        ),
        name="twin",
    )


def test_a_micrometre_image_gives_the_same_parameters_as_its_nanometre_twin():
    pytest.importorskip("hypyrameter")
    image = _reflectanceImage()
    cube = image.getData()
    twin = _twin(image, cube, image.wavelengths / 1000.0, "Micrometers")
    nm = BandParametersAnalysis().run(image, lambda p, m: None)
    um = BandParametersAnalysis().run(twin, lambda p, m: None)
    assert um.bandNames == nm.bandNames
    np.testing.assert_allclose(um.getData(), nm.getData(), equal_nan=True)


def test_scaled_reflectance_is_unscaled_before_computing():
    pytest.importorskip("hypyrameter")
    image = _reflectanceImage()
    scaled = _twin(
        image,
        image.getData() * 10000,
        image.wavelengths,
        "nm",
        {"reflectance_scale_factor": "10000"},
    )
    expected = BandParametersAnalysis().run(image, lambda p, m: None).getData()
    result = BandParametersAnalysis().run(scaled, lambda p, m: None).getData()
    np.testing.assert_allclose(result, expected, rtol=1e-5, equal_nan=True)
