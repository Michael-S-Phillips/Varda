from pathlib import Path
import logging
import importlib
import pkgutil

from features.image_load.abstractimageloader import AbstractImageLoader
from core.entities import Image

logger = logging.getLogger(__name__)


def loadNewImage(filepath):
    """
    Creates a new ImageModel from the given file path and appends it to the manager.

    Args:
        filepath (str): Path to the image file.

    Returns:
        QModelIndex: Index of the newly added image.

    Raises:
        ValueError: If the file type is not supported.
    """
    filepath = Path(filepath)
    imageType = getImageType(filepath)

    for loader in AbstractImageLoader.subclasses:
        if imageType in loader.imageType:
            # load() returns a tuple, so we unpack it (*) to pass to ImageModel
            img = Image(*loader(filepath).load())
            logger.info(f"Loaded image - {img}")
            return img  # return the new image

    # if no image type is found, raise an error
    error = ValueError(f"Bad file type {imageType}")
    logger.error(error)
    raise error

def getImageType(path):
    return path.suffix.strip()

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
