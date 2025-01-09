from pathlib import Path
import logging

from PyQt6.QtWidgets import QFileDialog

from core.data import ProjectContext
from features.image_load.abstractimageloader import AbstractImageLoader


logger = logging.getLogger(__name__)


# TODO: switch from async back to multithrading. Turns out async still freezes
#  the program.


# TODO: create improved system for image loading. I think we can skip the
#  AbstractImageLoader stuff and just iterate through the modules. This would
#  probably be a lot simpler to understand and work with.


async def loadNewImage(proj: ProjectContext, filePath=None):
    """Queries the user for a filePath and Loads the image. adds it to project

    Returns:
        int: Index of the newly added image.
    """
    if filePath is None:
        filePath = _requestFilePath()
    if filePath is None:
        return -1

    raster, metadata = _beginLoader(filePath)
    index = proj.createImage(raster, metadata)
    return index


def _requestFilePath():
    fileName = QFileDialog.getOpenFileName(
        None,
        "Open File",
        "",
        "image file (*.hdr *.img " "*.h5)",  # pylint: disable=implicit-str-concat
    )
    return fileName[0]


def _beginLoader(filePath):
    imageType = _getImageType(filePath)
    for loader in AbstractImageLoader.subclasses:
        if imageType in loader.imageType:
            # load() returns a tuple, so we unpack it (*) to pass to ImageModel
            return loader().load(filePath)

    # if no image type is found, raise an error
    raise ValueError(f"Bad file type {imageType}")


def _getImageType(path):
    return Path(path).suffix.strip()


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
