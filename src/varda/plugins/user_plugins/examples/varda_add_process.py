import varda

import logging

logger = logging.getLogger(__name__)


@varda.plugins.hookimpl
def onLoad():
    logger.info("Plugin hook implementation called: varda_add_process :O")
    varda.app.registry.registerImageProcess(MyProcess)


class MyProcess:
    name = "My Category/My Process"
    parameters = {
        "scale_factor": {
            "type": float,
            "default": 1.0,
            "min": 0.1,
            "max": 10.0,
            "description": "Scale factor to apply to the image",
        },
        "invert": {
            "type": bool,
            "default": False,
            "description": "Whether to invert the image",
        }
    }
    input_data_type = "full_raster"

    def execute(self, image, scale_factor=1.0, invert=False):
        """
        Process the image by scaling and optionally inverting it.

        Args:
            image: The input image data
            scale_factor: Factor to scale the image by
            invert: Whether to invert the image

        Returns:
            The processed image data
        """
        # Apply scaling
        result = image * scale_factor

        # Apply inversion if requested
        if invert:
            # Assuming image values are in [0, 1] range
            result = 1.0 - result

        return result
