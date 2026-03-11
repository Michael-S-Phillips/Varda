from .imageview_list import ImageListWidget
from varda.common import ObservableList


def newList(imageList: ObservableList, parent=None):
    """Creates and returns a new ImageListWidget instance.

    Args:
        proj (ProjectContext): The project context associated with the image list.
        parent (QWidget): The parent object for the image list widget. Defaults to None.
    """
    return ImageListWidget(imageList, parent)
