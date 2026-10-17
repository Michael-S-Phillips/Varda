"""Edits saved into an ENVI header: only the edited fields change, the rest
stays as written, a backup is kept, and the file reopens with the edits."""

import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_loading.envi_header import headerFor, readHeader, saveToHeader
from varda.image_loading.image_loading_service import openDataSource
from varda.image_loading.raster_writer import writeRaster


def _written(tmp_path):
    data = np.arange(24, dtype=np.float32).reshape(2, 3, 4)
    data[0, 0] = -999.0
    image = VardaRaster(
        ArrayDataSource(data, wavelengths=np.array([1.0, 2.0, 3.0, 4.0])), name="c"
    )
    return writeRaster(image, tmp_path / "cube.img")


def test_the_header_is_found_by_any_of_its_names(tmp_path):
    (tmp_path / "a.img").write_text("")
    (tmp_path / "a.hdr").write_text("ENVI\n")
    (tmp_path / "B.IMG").write_text("")
    (tmp_path / "B.IMG.HDR").write_text("ENVI\n")
    assert headerFor(tmp_path / "a.img") == tmp_path / "a.hdr"
    assert headerFor(tmp_path / "B.IMG") == tmp_path / "B.IMG.HDR"
    assert headerFor(tmp_path / "none.img") is None


def test_edits_are_saved_and_the_file_reopens_with_them(tmp_path):
    data = _written(tmp_path)
    header = headerFor(data)
    before = dict(readHeader(header))
    saveToHeader(
        data,
        {
            "nodata": -999.0,
            "wavelengths": [1000.0, 1100.0, 1200.0, 1300.0],
            "wavelengthUnits": "Nanometers",
            "bandNames": ["a", "b", "c", "d"],
            "fwhm": [10.0] * 4,
            "bbl": [1, 1, 0, 1],
            "description": "edited in Varda",
        },
    )
    after = dict(readHeader(header))
    assert after["data ignore value"] == "-999"
    assert (
        after["samples"] == before["samples"]
        and after["interleave"] == before["interleave"]
    )
    assert (header.parent / (header.name + ".bak")).read_text().startswith("ENVI")
    image = VardaRaster(openDataSource(str(data)))
    assert image.nodata == -999.0
    np.testing.assert_allclose(image.bandModel.centers, [1000, 1100, 1200, 1300])
    assert image.bandNames == ["a", "b", "c", "d"]
    np.testing.assert_array_equal(image.bandModel.badBands, [False, False, True, False])
    assert np.isnan(image.getBands([0])[0, 0, 0])  # the file's no-data now


def test_clearing_the_no_data_value_removes_it(tmp_path):
    data = _written(tmp_path)
    header = headerFor(data)
    saveToHeader(data, {"nodata": -999.0})
    saveToHeader(data, {"nodata": None})
    assert "data ignore value" not in dict(readHeader(header))
