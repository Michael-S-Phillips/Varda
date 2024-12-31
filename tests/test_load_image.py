import pytest
from pathlib import Path
import features.image_load as image_loader
from core.entities import Image, Metadata
import numpy as np

def test_load_image_envi():
    assert image_loader.loadNewImage(
        "testImages/HySpex/220724_VNIR_Reflectance.hdr") is not None

    image = image_loader.loadNewImage(
        "testImages/HySpex/220724_VNIR_Reflectance.hdr")

    assert isinstance(image, Image)
    assert isinstance(image.raster, np.ndarray)
    assert isinstance(image.metadata, Metadata)