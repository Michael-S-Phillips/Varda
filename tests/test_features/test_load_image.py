import pytest
from pathlib import Path
import features.image_load as image_loader
from core.entities import Image, Metadata
import numpy as np


def test_load_image_envi():
    assert (
        image_loader.loadNewImage(
            get_abs_path("../../testImages/HySpex/220724_VNIR_Reflectance.hdr")
        )
        is not None
    )

    image = image_loader.loadNewImage(
        get_abs_path("../../testImages/HySpex/220724_VNIR_Reflectance.hdr")
    )

    assert isinstance(image, Image)
    assert isinstance(image.raster, np.ndarray)
    assert isinstance(image.metadata, Metadata)


def test_load_image_hdf5():
    assert (
        image_loader.loadNewImage(
            get_abs_path(
                "../../testImages/NEON/NEON_D02_SERC_DP3_368000_4306000_reflectance.h5"
            )
        )
        is not None
    )

    image = image_loader.loadNewImage(
        get_abs_path(
            "../../testImages/NEON/NEON_D02_SERC_DP3_368000_4306000_reflectance.h5"
        )
    )

    assert isinstance(image, Image)
    assert isinstance(image.raster, np.ndarray)
    assert isinstance(image.metadata, Metadata)


def get_abs_path(path):
    return str(Path(path).absolute())
