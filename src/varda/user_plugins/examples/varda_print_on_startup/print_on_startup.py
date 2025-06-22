import logging

import varda

logger = logging.getLogger(__name__)


@varda.api.hookimpl(specname="onLoad")
def onLoad1():
    """Hook called on plugin load."""
    logger.info("Plugin hook implementation #1 called: varda_print_on_startup :O")


@varda.api.hookimpl(specname="onLoad")
def onLoad2():
    """Hook called on plugin load."""
    logger.info("Plugin hook implementation #2 called: varda_print_on_startup :O")


logger.info("Plugin varda_print_on_startup Loaded! :O")
