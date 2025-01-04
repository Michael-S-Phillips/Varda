from pathlib import Path
import logging

import asyncio
from PyQt6.QtWidgets import QFileDialog

from core.data import ProjectContext
from features.image_load.abstractimageloader import AbstractImageLoader


logger = logging.getLogger(__name__)


async def loadNewImage(proj: ProjectContext):
    """Queries the user for a filePath and Loads the image. adds it to project

    Returns:
        int: Index of the newly added image.
    """
    filePath = requestFilePath()
    if filePath is False:
        return
    raster, metadata = beginLoader(filePath)
    index = proj.createImage(raster, metadata)
    return index


def requestFilePath():
    # TODO: automatically determine all file types that are supported
    fileName = QFileDialog.getOpenFileName(
        None,
        "Open File",
        "",
        "image file (*.hdr *.img " "*.h5)",  # pylint: disable=implicit-str-concat
    )
    return fileName[0]


def beginLoader(filePath):
    imageType = getImageType(filePath)
    for loader in AbstractImageLoader.subclasses:
        if imageType in loader.imageType:
            # load() returns a tuple, so we unpack it (*) to pass to ImageModel
            return loader(filePath).load()

    # if no image type is found, raise an error
    raise ValueError(f"Bad file type {imageType}")


def getImageType(path):
    return Path(path).suffix.strip()


# TODO: complete improved system for image loading. I think we can skip the
#  AbstractImageLoader stuff and just iterate through the modules

# def loadNewImage(filepath):
#     """
#     Creates a new ImageModel from the given file path and appends it to the manager.
#
#     Args:
#         filepath (str): Path to the image file.
#
#     Returns:
#         QModelIndex: Index of the newly added image.
#
#     Raises:
#         ValueError: If the file type is not supported.
#     """
#     if filepath is None:
#         logger.error("No file path provided")
#     dir = Path(".").absolute()
#     print(dir)
#     print("Begin iterate through modules")
#     print(Path("features/image_load").absolute())
#     for moduleName in pkgutil.iter_modules(["features/image_load"]):
#         if moduleName == __name__:
#             continue
#         module = importlib.import_module(f".{moduleName.name}", "features.image_load")
#         print(moduleName, module)
#     print("End iterate through modules")
#
#     return
