import varda

import logging

logger = logging.getLogger(__name__)


@varda.plugins.hookimpl
def onLoad():
    logger.info("Plugin hook implementation called: varda_add_process :O")
    varda.app.registry.registerImageProcess(MyProcess)


class MyProcess:
    name = "My Category/My Process"
    parameters = None
    input_data_type = "full_raster"

    def execute(self, image):
        # Example processing (just return the data unchanged)
        return image
