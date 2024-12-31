from core.data import ProjectContext

from .imageview_list import ImageViewList
from .imagelistviewmodel import ImageListViewModel


def newList(proj: ProjectContext):
    model = ImageListViewModel(proj)
    list = ImageViewList(model)
