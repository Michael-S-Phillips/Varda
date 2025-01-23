"""image_view_roi.py
Will create a widget (table) that allows users to view an roi they
have created for an image

Usage example:
    from features.image_view_band.image_view_band import getBandView
    band_view = getBandView(proj, index, parent)
"""

from .roi_viewmodel import ROIViewModel
from .roi_view import ROIView


def getROIView(proj, index, parent):
    """Sets up and returns an instance of BandView."""
    viewModel = ROIViewModel(proj, index, parent)
    view = ROIView(viewModel, parent)
    return view