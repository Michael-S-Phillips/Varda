"""Statistics over an arbitrary pixel footprint, without an ROI collection."""

import numpy as np
import rasterio.features
from shapely.geometry import Polygon, mapping

from varda.rois.region_statistics import boxPolygonPixels, computeRegionStatistics
from varda.utilities.debug import generate_random_image


def _pixelsCovered(polygon: np.ndarray, shape: tuple[int, int]) -> tuple[set, set]:
    mask = rasterio.features.rasterize(
        [(mapping(Polygon([tuple(p) for p in polygon])), 1)],
        out_shape=shape,
        fill=0,
        dtype=np.uint8,
    ).astype(bool)
    rows, cols = np.nonzero(mask)
    return set(rows.tolist()), set(cols.tolist())


def test_box_polygon_covers_exactly_the_requested_pixels_centred_on_the_click():
    rows, cols = _pixelsCovered(boxPolygonPixels(10, 20, 5, 3), (40, 40))
    assert cols == {8, 9, 10, 11, 12}
    assert rows == {19, 20, 21}


def test_even_box_extends_one_extra_pixel_right_and_down():
    rows, cols = _pixelsCovered(boxPolygonPixels(10, 20, 2, 2), (40, 40))
    assert cols == {10, 11}
    assert rows == {20, 21}


def test_region_statistics_average_the_covered_pixels():
    image = generate_random_image((20, 20, 10))
    box = boxPolygonPixels(5, 7, 3, 3)  # cols 4..6, rows 6..8

    stats = computeRegionStatistics(box, image)

    expected = np.mean(
        [image.getSpectrum(c, r).values for c in (4, 5, 6) for r in (6, 7, 8)], axis=0
    )
    np.testing.assert_allclose(stats["mean"], expected)
    assert stats["pixel_count"] == 9


def test_region_statistics_of_a_footprint_outside_the_image_are_empty():
    image = generate_random_image((20, 20, 10))
    stats = computeRegionStatistics(boxPolygonPixels(50, 50, 3, 3), image)
    assert stats["pixel_count"] == 0
    assert stats["mean"].shape == (10,)
