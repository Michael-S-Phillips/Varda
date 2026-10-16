"""Where a point or a line on one image falls on the others: the same pixel,
or the same place on the map (across map projections too); spectra read
there with no-data and bad bands left out."""

import numpy as np
from affine import Affine
from pyproj import CRS

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.workspaces.linked_images.linking import Link, linkedPoints, spectrumAt

EQC = CRS.from_user_input("+proj=eqc +R=3396190 +units=m +no_defs")


def _image(transform=None, crs=EQC, shape=(20, 30, 4), name="a", **kwargs):
    data = np.arange(np.prod(shape), dtype=np.float32).reshape(shape)
    if transform is None:
        return VardaRaster(ArrayDataSource(data, **kwargs), name=name)
    return VardaRaster(
        ArrayDataSource(data, transform=transform, crs=crs, **kwargs), name=name
    )


def test_by_pixel_every_image_gets_the_same_pixel():
    images = [_image(), _image(shape=(10, 10, 2))]
    a, b = linkedPoints(images, 0, [[5.5, 3.5]], Link.PIXEL)
    np.testing.assert_allclose(a, [[5.5, 3.5]])
    np.testing.assert_allclose(b, [[5.5, 3.5]])


def test_by_map_location_finer_and_shifted_grids_agree():
    coarse = _image(Affine(20, 0, 1000, 0, -20, 5000))
    fine = _image(Affine(10, 0, 1100, 0, -10, 4900), name="fine")
    _, there = linkedPoints([coarse, fine], 0, [[10, 10]], Link.MAP)
    # (10, 10) on the coarse grid is (1200, 4800): 10 px right and down on the fine
    np.testing.assert_allclose(there, [[10, 10]])
    _, back = linkedPoints([fine, coarse], 0, [[0, 0]], Link.MAP)
    np.testing.assert_allclose(back, [[5, 5]])


def test_by_map_location_across_map_projections():
    geographic = CRS.from_user_input("+proj=longlat +R=3396190 +no_defs")
    degree = np.pi * 3396190 / 180
    projected = _image(Affine(100, 0, 0, 0, -100, 0))
    lonlat = _image(Affine(0.01, 0, 0, 0, -0.01, 0), crs=geographic, name="ll")
    _, there = linkedPoints([projected, lonlat], 0, [[10, 10]], Link.MAP)
    # 1000 m east and south of (0, 0) is 1000 / degree degrees
    np.testing.assert_allclose(there, [[1000 / degree / 0.01] * 2], rtol=1e-6)


def test_images_without_georeferencing_fall_back_to_the_pixel():
    plain = _image()
    mapped = _image(Affine(20, 0, 1000, 0, -20, 5000))
    _, there = linkedPoints([mapped, plain], 0, [[3, 4]], Link.MAP)
    np.testing.assert_allclose(there, [[3, 4]])


def test_a_spectrum_leaves_out_no_data_and_bad_bands():
    image = _image(
        wavelengths=np.array([1.0, 2.0, 3.0, 4.0]),
        wavelengthUnits="micrometers",
        nodata=5.0,
        extraMetadata={"bbl": [1, 1, 0, 1]},
    )
    spectrum = spectrumAt(image, 1.5, 0.5)  # pixel (1, 0): values 4, 5, 6, 7
    assert spectrum is not None
    np.testing.assert_allclose(spectrum.axis, [1000, 2000, 3000, 4000])
    np.testing.assert_array_equal(np.isnan(spectrum.values), [False, True, True, False])
    assert spectrum.axisLabel == "Wavelength (µm)"
    np.testing.assert_allclose(spectrum.displayAxis, [1, 2, 3, 4])
    assert spectrumAt(image, -1, 3) is None  # off the image
    plain = spectrumAt(_image(), 2, 2)
    assert plain is not None and plain.axisLabel == "Band"
