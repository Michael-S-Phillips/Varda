from varda.project import ProjectContext

from .imageview_list import ImageListWidget


def newList(proj: ProjectContext, parent=None):
    """Creates and returns a new ImageListWidget instance.

    Args:
        proj (ProjectContext): The project context associated with the image list.
        parent (QWidget): The parent object for the image list widget. Defaults to None.
    """
    return ImageListWidget(proj, parent)
