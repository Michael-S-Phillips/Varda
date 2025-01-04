from .raster_viewmodel import RasterViewModel
from .raster_view import RasterView


def getRasterView(proj, index, parent):
    viewModel = RasterViewModel(proj, index, parent)
    view = RasterView(viewModel, parent)
    return view
