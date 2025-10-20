from .raster_viewmodel import RasterViewModel
from .raster_view import RasterView


# support dual image view creation
def createDualModeRasterView(
    proj, image_index, parent=None, is_overlay_secondary=False
):
    """
    Create a RasterView configured for dual image mode.

    Args:
        proj: ProjectContext instance
        image_index: Index of the image to display
        parent: Parent widget
        is_overlay_secondary: Whether this view is the secondary overlay view

    Returns:
        RasterView: Configured raster view for dual mode
    """
    try:
        # Create view model and view
        view_model = RasterViewModel(proj, image_index)
        raster_view = RasterView(view_model, parent)

        # Configure for dual mode
        raster_view.set_dual_mode(True, is_overlay_secondary)

        return raster_view

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(
            f"Failed to create dual mode raster view for image {image_index}: {e}"
        )
        return None


def getRasterView(proj, index, parent) -> RasterView:
    """Sets up and returns an instance of RasterView."""
    viewModel = RasterViewModel(proj, index, parent)
    view = RasterView(viewModel, parent)
    return view
