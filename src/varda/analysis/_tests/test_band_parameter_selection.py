"""Band Parameters lets the user choose which HyPyRameter parameters to compute."""

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


def test_preparing_for_an_image_offers_its_valid_parameters_all_selected():
    pytest.importorskip("hypyrameter")
    from varda.analysis.hypyrameter_adapter import validParameterNames

    image = _reflectanceImage()
    analysis = BandParametersAnalysis()

    analysis.prepareFor(image)

    names = validParameterNames(image.wavelengths)
    assert analysis.parameters.choices == names
    assert analysis.parameters.get() == names


def test_preparing_for_an_image_without_numeric_wavelengths_offers_nothing():
    pytest.importorskip("hypyrameter")
    image = VardaRaster(
        ArrayDataSource(np.zeros((4, 4, 3)), wavelengths=np.array(["a", "b", "c"])),
        name="bands",
    )
    analysis = BandParametersAnalysis()
    analysis.prepareFor(image)
    assert analysis.parameters.choices == []


def test_run_computes_only_the_selected_parameters():
    pytest.importorskip("hypyrameter")
    image = _reflectanceImage()
    analysis = BandParametersAnalysis()
    analysis.prepareFor(image)
    chosen = analysis.parameters.choices[:2]
    analysis.parameters.set(chosen)

    result = analysis.run(image, lambda p, m: None)

    assert result.bandNames == chosen
    assert result.bandCount == 2


def test_run_with_nothing_selected_is_an_error():
    pytest.importorskip("hypyrameter")
    image = _reflectanceImage()
    analysis = BandParametersAnalysis()
    analysis.prepareFor(image)
    analysis.parameters.set([])

    with pytest.raises(ValueError, match="at least one parameter"):
        analysis.run(image, lambda p, m: None)
