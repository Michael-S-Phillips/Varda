from varda.common.entities import VardaRaster
from varda.common.observable_list import ObservableList


class ProjectImages(ObservableList[VardaRaster]):
    """Typed ObservableList for VardaRaster images, used as DI injection type."""

    pass
