import sys

from PyQt6.QtWidgets import QApplication

from varda.core.data import ProjectContext
from varda.plugins.plugin_manager import VardaPluginManager
from varda.registries import WidgetRegistry, ImageLoaderRegistry

proj = ProjectContext()
widgetRegistry = WidgetRegistry()
imageLoaderRegistry = ImageLoaderRegistry()
pm = VardaPluginManager()
app = QApplication(sys.argv)
app.setApplicationName("Varda")
app.setOrganizationName("Varda")
