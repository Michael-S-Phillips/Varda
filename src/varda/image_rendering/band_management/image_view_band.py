"""image_view_band.py
This feature creates a widget that lets you view and manipulate band data

Usage example:
    from varda.features.image_view_band.image_view_band import getBandView
    band_view = getBandView(proj, index, parent)
"""

from varda.image_rendering.band_management.band_viewmodel import BandViewModel
from varda.image_rendering.band_management.band_view import BandView


def getBandView(proj, index, parent):
    """Sets up and returns an instance of BandView."""
    viewModel = BandViewModel(proj, index, parent)
    view = BandView(viewModel, parent)
    return view
