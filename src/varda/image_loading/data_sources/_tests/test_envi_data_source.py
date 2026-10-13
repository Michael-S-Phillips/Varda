"""ENVI files open with the right data, whatever their layout, compared against
Spectral Python (SPy) as the reference reader."""

import numpy as np
import pytest
import rasterio
import spectral.io.envi as envi

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.envi_data_source import (
    ENVIDataSource,
    findEnviDataFile,
)
from varda.image_loading.data_sources.rasterio_data_source import RasterioDataSource
from varda.image_loading.image_loading_service import openDataSource

ROWS, COLS, BANDS = 5, 7, 4


def _cube(dtype) -> np.ndarray:
    values = np.arange(ROWS * COLS * BANDS).reshape(ROWS, COLS, BANDS) % 200
    return values.astype(dtype)


def _write(
    tmp_path, dtype=np.float32, interleave="bsq", byteorder=0, ext=".img", **metadata
):
    header = tmp_path / "cube.hdr"
    envi.save_image(
        str(header),
        _cube(dtype),
        dtype=dtype,
        interleave=interleave,
        byteorder=byteorder,
        ext=ext,
        metadata=metadata,
        force=True,
    )
    return header, tmp_path / f"cube{ext}"


def _assertMatchesSpy(path, header, dataFile):
    reference = np.asarray(envi.open(str(header), str(dataFile)).open_memmap())
    data = openDataSource(str(path)).readAllBands()
    np.testing.assert_array_equal(data, reference.astype(data.dtype))


@pytest.mark.parametrize("interleave", ["bsq", "bil", "bip"])
@pytest.mark.parametrize("byteorder", [0, 1])
def test_every_interleave_and_byte_order(tmp_path, interleave, byteorder):
    header, data = _write(tmp_path, interleave=interleave, byteorder=byteorder)
    _assertMatchesSpy(header, header, data)


@pytest.mark.parametrize(
    "dtype", [np.uint8, np.int16, np.uint16, np.int32, np.float32, np.float64]
)
def test_every_data_type(tmp_path, dtype):
    header, data = _write(tmp_path, dtype=dtype)
    _assertMatchesSpy(header, header, data)


@pytest.mark.parametrize("ext", [".img", ".dat", ".raw", ".bin", ".bsq", ""])
def test_the_data_file_is_found_from_the_header_whatever_its_extension(tmp_path, ext):
    header, data = _write(tmp_path, ext=ext)
    assert findEnviDataFile(header) == data
    _assertMatchesSpy(header, header, data)


@pytest.mark.parametrize("ext", [".dat", ".raw", ".bin", ".bsq", ".img"])
def test_opening_the_data_file_uses_the_envi_reader_when_a_header_is_beside_it(
    tmp_path, ext
):
    header, data = _write(
        tmp_path, ext=ext, wavelength=[1, 2, 3, 4], **{"wavelength units": "um"}
    )
    source = openDataSource(str(data))
    assert isinstance(source, ENVIDataSource)
    assert VardaRaster(source).bandModel.isSpectral
    _assertMatchesSpy(data, header, data)


def test_upper_case_and_double_extensions(tmp_path):
    header, data = _write(tmp_path)
    upper = tmp_path / "CUBE.HDR"
    header.rename(upper)
    data.rename(tmp_path / "CUBE.IMG")
    assert findEnviDataFile(upper) == tmp_path / "CUBE.IMG"
    double = tmp_path / "scene.img.hdr"
    upper.rename(double)
    (tmp_path / "CUBE.IMG").rename(tmp_path / "scene.img")
    assert findEnviDataFile(double) == tmp_path / "scene.img"
    _assertMatchesSpy(double, double, tmp_path / "scene.img")


def test_a_folder_named_hdr_does_not_confuse_the_search(tmp_path):
    folder = tmp_path / "flights.hdr.d"
    folder.mkdir()
    header, data = _write(folder)
    assert findEnviDataFile(header) == data


def test_an_img_without_a_header_is_not_forced_through_the_envi_reader(tmp_path):
    path = tmp_path / "plain.img"  # e.g. an Erdas or PDS file GDAL can open
    with rasterio.open(
        path, "w", driver="HFA", width=COLS, height=ROWS, count=1, dtype="uint8"
    ) as dst:
        dst.write(np.zeros((1, ROWS, COLS), dtype=np.uint8))
    source = openDataSource(str(path))
    assert isinstance(source, RasterioDataSource) and not isinstance(
        source, ENVIDataSource
    )


def test_header_offset_mixed_case_keys_and_multiline_lists(tmp_path):
    cube = _cube(np.float32)
    offset = 128
    data = tmp_path / "manual.dat"
    data.write_bytes(
        b"\0" * offset + np.ascontiguousarray(cube.transpose(2, 0, 1)).tobytes()
    )
    header = tmp_path / "manual.hdr"
    header.write_text(
        "ENVI\n"
        f"Samples = {COLS}\nLINES = {ROWS}\nBands = {BANDS}\n"
        f"Header Offset = {offset}\nFile Type = ENVI Standard\n"
        "Data Type = 4\nInterleave = bsq\nByte Order = 0\n"
        "Wavelength Units = Micrometers\n"
        "Wavelength = {\n 1.0,\n 1.5,\n 2.0,\n 2.5 }\n"
        "fwhm = {0.01, 0.01,\n 0.02, 0.02}\n"
        "bbl = {1, 1, 0, 1}\n"
        "data ignore value = -9999.5\n"
        "reflectance scale factor = 1000.0\n"
    )
    _assertMatchesSpy(header, header, data)
    model = VardaRaster(openDataSource(str(header))).bandModel
    np.testing.assert_allclose(model.centers, [1000, 1500, 2000, 2500])
    np.testing.assert_allclose(model.fwhm, [10, 10, 20, 20])
    assert model.badBands.tolist() == [False, False, True, False]
    assert model.noData == -9999.5 and model.scaleFactor == 1000.0


@pytest.mark.parametrize("ignore", [-9999, 0.5])
def test_integer_and_float_data_ignore_values_become_no_data(tmp_path, ignore):
    dtype = np.int16 if isinstance(ignore, int) else np.float32
    cube = _cube(dtype)
    cube[0, 0, :] = ignore
    header = tmp_path / "nd.hdr"
    envi.save_image(
        str(header),
        cube,
        dtype=dtype,
        metadata={"data ignore value": ignore},
        force=True,
        ext=".img",
    )
    data = openDataSource(str(header)).readAllBands()
    assert np.isnan(data[0, 0]).all()
    assert not np.isnan(data[1:]).any()


def test_without_default_bands_a_spectral_image_opens_in_true_colour(tmp_path):
    wavelengths = list(np.arange(400.0, 1001.0, 50.0))
    header = tmp_path / "vis.hdr"
    data = np.ones((3, 4, len(wavelengths)), dtype=np.float32)
    envi.save_image(
        str(header),
        data,
        metadata={"wavelength": wavelengths, "wavelength units": "nm"},
        ext=".img",
    )
    bands = openDataSource(str(header)).defaultBands
    assert [wavelengths[b] for b in bands] == [650.0, 550.0, 450.0]


def test_a_header_default_bands_entry_still_wins(tmp_path):
    wavelengths = list(np.arange(400.0, 1001.0, 50.0))
    header = tmp_path / "vis.hdr"
    data = np.ones((3, 4, len(wavelengths)), dtype=np.float32)
    envi.save_image(
        str(header),
        data,
        metadata={
            "wavelength": wavelengths,
            "wavelength units": "nm",
            "default bands": [1, 2, 3],
        },
        ext=".img",
    )
    assert list(openDataSource(str(header)).defaultBands) == [0, 1, 2]
