# standard library
from enum import Enum, auto

# third party imports
from PyQt6.QtCore import Qt

# local imports


class ImageDataType(Enum):
    """
    Enum for the different types of image data
    """
    OBJECT = Qt.ItemDataRole.UserRole
    RASTER_DATA = auto()
    METADATA = auto()
    BANDS = auto()
    STRETCH = auto()
    HISTOGRAM = auto()
    ROI = auto()
