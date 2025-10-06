from PyQt6.QtWidgets import QWidget

from varda.image_rendering.raster_view.viewport import ImageViewport

class SpectralCubeAndParamCubeWorkflow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewport1 = ImageViewport()
