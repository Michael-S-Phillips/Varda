"""
Feature: View Image Data

Purpose: This feature allows the user to view and edit basic image data in various ways

"""

from core.data import ProjectContext
from features.image_view_data.viewmodels.image_viewmodel import ImageViewModel
from .views.imageview_raster import ImageViewRaster
from .views.imageview_band import ImageViewBand
from .views.imageview_stretch import ImageViewStretch


def getBandView(proj: ProjectContext, index: int, parent):
    viewmodel = ImageViewModel(proj.getImageFromIndex(index))
    view = ImageViewBand(viewmodel, parent)
    return view


def getStretchView(proj: ProjectContext, index: int, parent):
    viewmodel = ImageViewModel(proj.getImageFromIndex(index))
    view = ImageViewStretch(viewmodel, parent)
    return view


def getRasterView(proj: ProjectContext, index: int, parent):
    image = proj.getImageFromIndex(index)
    viewmodel = ImageViewModel(image)
    view = ImageViewRaster(viewmodel, parent)
    return view
