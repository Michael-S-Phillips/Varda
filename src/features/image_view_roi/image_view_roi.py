"""image_view_roi.py
Will create a widget (table) that allows users to view an roi they
have created for an image

"""

from .roi_viewmodel import ROIViewModel
from .enhanced_roi_view import EnhancedROIView

def getROIView(proj, index, parent):
    """Sets up and returns an instance of ROIView."""
    viewModel = ROIViewModel(proj, index, parent)
    view = EnhancedROIView(viewModel, parent)
    return view