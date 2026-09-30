"""The PCA / MNF / ICA analyses produce component images over the source footprint."""

import numpy as np

from varda.analysis.transforms import IcaAnalysis, MnfAnalysis, PcaAnalysis
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


def _image(seed=0, bands=8) -> VardaRaster:
    rng = np.random.default_rng(seed)
    sources = rng.normal(size=(20 * 30, 3))
    mixing = rng.normal(size=(3, bands))
    cube = (sources @ mixing).reshape(20, 30, bands) + 0.01 * rng.normal(
        size=(20, 30, bands)
    )
    cube[0, 0, :] = -1.0  # a nodata pixel
    return VardaRaster(
        ArrayDataSource(
            cube, wavelengths=np.linspace(1000.0, 2600.0, bands), nodata=-1.0
        ),
        name="scene",
    )


def test_pca_image_has_named_components_and_nodata_stays_missing():
    image = _image()
    analysis = PcaAnalysis()
    analysis.components.set(3)

    result = analysis.run(image, lambda p, m: None)

    assert result.name == "scene PCA"
    assert result.bandCount == 3
    assert result.bandNames[0].startswith("PC 1 (") and result.bandNames[0].endswith(
        "%)"
    )
    assert result.width == image.width and result.height == image.height
    assert np.isnan(result.getData()[0, 0]).all()
    assert np.isfinite(result.getData()[5, 5]).all()


def test_mnf_image_is_named_and_ordered():
    image = _image()
    analysis = MnfAnalysis()
    analysis.components.set(2)

    result = analysis.run(image, lambda p, m: None)

    assert result.name == "scene MNF"
    assert result.bandNames == ["MNF 1", "MNF 2"]


def test_ica_image_is_named():
    image = _image()
    analysis = IcaAnalysis()
    analysis.components.set(3)

    result = analysis.run(image, lambda p, m: None)

    assert result.name == "scene ICA"
    assert result.bandNames == ["IC 1", "IC 2", "IC 3"]
    assert result.bandCount == 3


def test_components_are_capped_at_the_band_count():
    image = _image(bands=4)
    analysis = PcaAnalysis()
    analysis.components.set(50)

    result = analysis.run(image, lambda p, m: None)

    assert result.bandCount == 4


def test_transforms_are_filed_under_transforms():
    for analysis in (PcaAnalysis, MnfAnalysis, IcaAnalysis):
        assert analysis.category == "Transforms"
        assert analysis.isAvailable()
