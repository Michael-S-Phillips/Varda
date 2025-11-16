from .image_loading_service import ImageLoadingService, register_image_loader
from .protocols import ImageLoaderProtocol


from . import (
    _loader_implementations,
)  # We import this so that the loaders get registered.
