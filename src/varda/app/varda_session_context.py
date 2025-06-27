import logging

from varda.core.data import ProjectContext, Registry
from varda.plugins.plugin_manager import VardaPluginManager


logger = logging.getLogger(__name__)


class VardaSessionContext:
    """
    Context for the current Varda session.
    Includes the project context, registry, and plugin manager.
    """

    def __init__(self):
        self.proj = ProjectContext()
        self.registry = Registry()
        self.pm = VardaPluginManager()
