from .histogram_viewmodel import HistogramViewModel
from .histogram_view import HistogramView


def getHistogramView(proj, imageIndex, parent=None):
    """returns a new HistogramView with the given project and image index."""
    viewModel = HistogramViewModel(proj, imageIndex, parent)
    return HistogramView(viewModel, parent)
