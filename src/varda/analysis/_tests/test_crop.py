"""Cropping: the shared crop, Crop to ROI, the Crop tool's box, and crops
landing in the project from a workspace."""

import numpy as np
import pytest
from affine import Affine
from PyQt6.QtCore import QPointF, QRect
from shapely.geometry import Polygon, box

from varda.analysis.analysis import AnalysisContext
from varda.analysis.geometry import CropToRoiAnalysis, crop
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.raster_view.viewport_tools.crop_tool import pixelBox
from varda.rois.roi_collection import ROICollection

QUIET = lambda percent, message: None  # noqa: E731
TRANSFORM = Affine(18.0, 0.0, 1000.0, 0.0, -18.0, 5000.0)


def _image() -> VardaRaster:
    cube = np.arange(20 * 30 * 3, dtype=np.float32).reshape(20, 30, 3)
    return VardaRaster(
        ArrayDataSource(
            cube, wavelengths=np.array([500.0, 600.0, 700.0]), transform=TRANSFORM
        ),
        name="scene",
    )


def _data(image: VardaRaster) -> np.ndarray:
    return np.asarray(image.getData(), float)


def test_crop_keeps_values_and_map_position():
    original = _image()
    cropped = crop(original, 4, 6, 5, 7)
    assert (cropped.height, cropped.width, cropped.bandCount) == (5, 7, 3)
    assert np.array_equal(_data(cropped), _data(original)[4:9, 6:13])
    assert cropped.transform * (0, 0) == original.transform * (6, 4)
    np.testing.assert_array_equal(cropped.wavelengths, original.wavelengths)


def test_crop_can_make_outside_pixels_nodata():
    outside = np.zeros((3, 3), bool)
    outside[0, 0] = True
    data = _data(crop(_image(), 0, 0, 3, 3, outside=outside))
    assert np.isnan(data[0, 0]).all() and np.isfinite(data[1:, 1:]).all()


def _cropToRoi(rois: ROICollection, **values) -> CropToRoiAnalysis:
    analysis = CropToRoiAnalysis()
    analysis.setContext(AnalysisContext(rois=rois))
    analysis.prepareFor(_image())
    for name, value in values.items():
        analysis.params[name].set(value)
    return analysis


def _rois() -> ROICollection:
    rois = ROICollection()
    # a triangle inside columns 10-20, rows 4-12
    rois.addROI(
        Polygon([(10, 4), (20, 4), (10, 12)]),
        "lava",
        Color(1, 0, 0, 1),
        ROIMode.POLYGON,
    )
    rois.addROI(box(1, 1, 3, 3), "dust", Color(0, 0, 1, 1), ROIMode.RECTANGLE)
    return rois


def test_crop_to_roi_crops_to_the_bounding_box_and_masks_outside():
    analysis = _cropToRoi(_rois(), classes=["lava"])
    result = analysis.run(_image(), QUIET)
    # pixels whose centers are inside: column 19's falls just outside the slant
    assert (result.height, result.width) == (8, 9)
    data = _data(result)
    assert np.isfinite(data[0, 0]).all()  # the triangle's corner is inside
    assert np.isnan(data[-1, -1]).all()  # the far corner is outside it
    assert result.transform * (0, 0) == TRANSFORM * (10, 4)


def test_crop_to_roi_can_keep_the_whole_box():
    analysis = _cropToRoi(_rois(), classes=["lava"], maskOutside=False)
    assert np.isfinite(_data(analysis.run(_image(), QUIET))).all()


def test_crop_to_roi_needs_rois_and_a_class():
    assert "Draw an ROI" in _cropToRoi(ROICollection()).unavailableReason(_image())
    analysis = _cropToRoi(_rois(), classes=[])
    assert "Tick at least one" in analysis.unavailableReason(_image())


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (
            QPointF(2.4, 3.6),
            QPointF(7.2, 9.1),
            QRect(2, 3, 6, 7),
        ),  # whole pixels covered
        (QPointF(7.2, 9.1), QPointF(2.4, 3.6), QRect(2, 3, 6, 7)),  # either direction
        (QPointF(-5, -5), QPointF(4, 4), QRect(0, 0, 4, 4)),  # clamped to the image
    ],
)
def test_the_crop_box_covers_whole_pixels_inside_the_image(start, end, expected):
    assert pixelBox(start, end, 30, 20) == expected


def test_a_box_outside_the_image_is_empty():
    assert pixelBox(QPointF(40, 40), QPointF(50, 50), 30, 20).isEmpty()
