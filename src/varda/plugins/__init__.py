# This package contains the plugin system for Varda.

from varda.plugins._hooks import hookimpl, onLoad, onUnload
from varda.plugins.plugin_manager import VardaPluginManager

__all__ = [
    "hookimpl",
    "onLoad",
    "onUnload",
    "VardaPluginManager",
]
