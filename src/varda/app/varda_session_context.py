import logging

from varda.project.project_context import ProjectContext
from varda.project.project_io import ProjectJsonIO
from varda.plugins.plugin_manager import VardaPluginManager
from varda.registries.registries import VardaRegistries

logger = logging.getLogger(__name__)


class VardaSessionContext:
    """
    Context for the current Varda session.
    Includes the project context, registry, and plugin manager.
    """

    def __init__(self):
        # Initialize the persistence module
        self.projectIO = ProjectJsonIO()

        # Initialize the project context with the persistence module
        self.proj = ProjectContext(io=self.projectIO)

        # Initialize other components
        self.pm = VardaPluginManager()
        self.registry = VardaRegistries()
