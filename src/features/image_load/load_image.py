from pathlib import Path
import logging

from PyQt6.QtWidgets import QFileDialog

from core.data import ProjectContext
import core.utilities as utils
from features.image_load.abstractimageloader import AbstractImageLoader


logger = logging.getLogger(__name__)


# TODO: create improved system for image loading. I think we can skip the
#  AbstractImageLoader stuff and just iterate through the modules. This would
#  probably be a lot simpler to understand and work with.


def loadNewImage(proj: ProjectContext, filePath=None, functionCallback=None):
    """Loads a new image and adds it to project.
    If a filePath is not provided, it will prompt the user to select a file
    using a file dialog.
    functionCallback is an optional function that will be called after the
    image is loaded.

    Returns:
        int: Index of the newly added image. -1 if an error occurred.
    """
    if filePath is None:
        filePath = _requestFilePath()
    if filePath is None:
        functionCallback(-1)
        return

    loader = _getLoader(filePath)

    loadingManager = ImageLoadingManager(proj, loader, filePath, functionCallback)
    loadingManager.load()


def _requestFilePath():
    fileName = QFileDialog.getOpenFileName(
        None,
        "Open File",
        "",
        "image file (*.hdr *.img " "*.h5)",  # pylint: disable=implicit-str-concat
    )
    return fileName[0]


def _getLoader(filePath):
    imageType = _getImageType(filePath)
    for loader in AbstractImageLoader.subclasses:
        if imageType in loader.imageType:
            return loader()

    # if no image type is found, raise an error
    raise ValueError(f"Bad file type {imageType}")


def _getImageType(path):
    return Path(path).suffix.strip()


class ImageLoadingManager:
    def __init__(self, proj, loader, filePath, functionCallback):
        self.proj = proj
        self.loader = loader
        self.filePath = filePath
        self.functionCallback = functionCallback

    def load(self):
        """Begins the loading process. This will load the image data in a
        separate thread. When the complete, it will use the data to add a
        new image to the project, and call the functionCallback.
        """
        utils.threading_helper.dispatchThreadProcess(
            self._onLoaderFinished, lambda: self.loader.load(self.filePath)
        )

    def _onLoaderFinished(self, loadedData):
        raster, metadata = loadedData
        index = self.proj.createImage(raster, metadata)
        self.functionCallback(index)


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
