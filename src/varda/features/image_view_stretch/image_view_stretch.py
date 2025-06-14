from .stretch_viewmodel import StretchViewModel
from .stretch_view import StretchView


def getStretchView(proj, index, parent):
    """Sets up and returns an instance of Stretch."""
    viewModel = StretchViewModel(proj, index, parent)
    view = StretchView(viewModel, parent)
    return view
