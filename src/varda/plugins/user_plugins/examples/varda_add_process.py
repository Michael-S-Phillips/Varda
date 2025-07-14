import varda
from varda.core.image_process.imageprocess import ImageProcess

import logging

logger = logging.getLogger(__name__)


@varda.plugins.hookimpl
def onLoad():
    logger.info("Plugin hook implementation called: varda_add_process :O")
    varda.app.registry.registerImageProcess(MyProcess)


class MyProcess(ImageProcess):
    name = "My Category/My Process"
    parameters = {}

    def execute(self, image):
        # Example processing (just return the data unchanged)
        return image
