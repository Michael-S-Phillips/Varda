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


def test_bad_bands_keep_the_input_values():
    """Bad bands are filled along the spectrum to filter the cube, but the
    result gives them back as they were, still marked bad."""
    image = _image()
    cube = np.array(image.getData())
    cube[:, :, 12] = 7.0 + np.arange(cube.shape[1])  # garbage in a bad band
    bbl = [0 if b == 12 else 1 for b in range(cube.shape[2])]
    source = ArrayDataSource(
        cube,
        wavelengths=np.asarray(image.wavelengths),
        wavelengthUnits="nm",
        nodata=-1.0,
        extraMetadata={"bbl": bbl},
    )
    result = IovfAnalysis().run(VardaRaster(source, name="scene"), lambda p, m: None)
    out = result.getData()
    expected = cube[:, :, 12].astype(np.float32)
    np.testing.assert_array_equal(out[1:, :, 12], expected[1:])
    assert np.isnan(out[0, 0]).all()  # nodata stays missing
    assert result.bandModel.badBands[12]


def test_the_replaced_count_map_comes_with_the_filtered_cube():
    """By default the run also gives a one-band image of how many bands were
    replaced at each pixel; both record the per-round counts."""
    image = _image()
    filtered, counts = IovfAnalysis().runAll(image, lambda p, m: None)

    assert filtered.name == "scene IOVF"
    assert counts.name == "scene IOVF replaced"
    assert counts.bandNames == ["Bands replaced"]
    values = counts.getData()[:, :, 0]
    assert values[8, 7] >= 1  # the spike
    assert np.isnan(values[0, 0])  # nodata stays missing
    record = filtered.extraMetadata["iovf"]
    assert counts.extraMetadata["iovf"] == record
    assert record["replacedTotal"] == sum(record["replacedPerRound"]) > 0
    assert record["rounds"] == len(record["replacedPerRound"])
    assert record["pixelsWithReplacements"] == int(np.nansum(values > 0))
    assert record["stopReason"]
    assert (
        f"{record['replacedTotal']} voxels replaced" in filtered.dataSource.description
    )


def test_the_count_map_can_be_left_out():
    analysis = IovfAnalysis()
    analysis.replacedMap.set(False)
    (filtered,) = analysis.runAll(_image(), lambda p, m: None)
    assert "iovf" in filtered.extraMetadata
