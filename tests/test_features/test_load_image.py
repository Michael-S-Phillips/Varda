import os

import pytest
from pathlib import Path
import features.image_load as image_loader
from core.data import ProjectContext
from core.entities import Image, Metadata
import numpy as np
import os
import asyncio


def test_load_image():
    if not Path("./testImages").exists():
        print(os.getcwd())
        print("Test image directory doesnt exist!")
        assert False

    proj = ProjectContext()
    # test ENVI Image Loading
    result = asyncio.run(
        image_loader.loadNewImage(
            proj, get_abs_path("./testImages/HySpex/220724_VNIR_Reflectance.hdr")
        )
    )
    assert result is not None
    image = proj.getImage(result)
    assert isinstance(image, Image)
    assert isinstance(image.raster, np.ndarray)
    assert isinstance(image.metadata, Metadata)

    # test HDF5 Image Loading
    result = asyncio.run(
        image_loader.loadNewImage(
            proj,
            get_abs_path(
                "./testImages/NEON/NEON_D02_SERC_DP3_368000_4306000_reflectance.h5"
            ),
        )
    )
    assert result is not None
    image = proj.getImage(result)
    assert isinstance(image, Image)
    assert isinstance(image.raster, np.ndarray)
    assert isinstance(image.metadata, Metadata)


def get_abs_path(path):
    return str(Path(path).absolute())
