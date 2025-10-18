from varda.plugins import VardaPluginManager
from varda.project import ProjectContext
from varda.project.project_io import ProjectJsonIO
from varda.registries.registries import VardaRegistries


class VardaApplication:
    def __init__(self):
        self.projectIO = ProjectJsonIO()
        self.proj = ProjectContext(io=self.projectIO)
        self.pm = VardaPluginManager()
        self.registry = VardaRegistries()
