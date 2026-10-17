"""A crop drawn with the Crop tool records its window and its input."""

import numpy as np
from PyQt6.QtCore import QRect

from varda.common.entities import VardaRaster
from varda.common.provenance import PROVENANCE_KEY
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.workspaces.cropping import addCrop


def test_a_crop_records_its_window_and_input():
    source = ArrayDataSource(
        np.zeros((20, 30, 2), np.float32), filePath="/data/scene.img"
    )
    image = VardaRaster(source, name="scene")
    project: list[VardaRaster] = []

    cropped = addCrop(image, QRect(4, 3, 10, 8), project)

    assert project == [cropped] and cropped.shape == (8, 10, 2)
    record = cropped.extraMetadata[PROVENANCE_KEY]
    assert record["process"] == "Crop"
    assert record["parameters"] == {"row": 3, "column": 4, "height": 8, "width": 10}
    assert record["inputs"] == [{"name": "scene", "path": "/data/scene.img"}]
