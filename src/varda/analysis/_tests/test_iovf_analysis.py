"""Processing > Filtering > IOVF cleans spikes and keeps the image's bands."""

import numpy as np

from varda.analysis.filtering import IovfAnalysis
from varda.analysis.registry import ANALYSES
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


def _image() -> VardaRaster:
    rng = np.random.default_rng(0)
    wl = np.linspace(1000.0, 2500.0, 40)
    cube = 0.3 + 0.002 * rng.normal(size=(16, 14, wl.size))
    cube[8, 7, 20] = 0.9  # a spike
    cube[0, 0, :] = -1.0  # nodata pixel
    source = ArrayDataSource(
        cube,
        wavelengths=wl,
        wavelengthUnits="nm",
        nodata=-1.0,
        defaultBands=np.array([30, 20, 5]),
    )
    return VardaRaster(source, name="scene")


def test_iovf_is_listed_under_spectral_filtering():
    assert IovfAnalysis in ANALYSES
    assert IovfAnalysis.category == "Filtering/Spectral"


def test_result_keeps_bands_and_removes_the_spike():
    image = _image()
    result = IovfAnalysis().run(image, lambda p, m: None)

    assert result.name == "scene IOVF"
    assert list(result.wavelengths) == list(image.wavelengths)
    assert list(result.defaultBands) == [30, 20, 5]
    data = result.getData()
    assert abs(data[8, 7, 20] - 0.3) < 0.02
    assert np.isnan(data[0, 0]).all()  # nodata stays missing
