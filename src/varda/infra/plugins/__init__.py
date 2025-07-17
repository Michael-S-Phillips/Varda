# This file marks the plugins directory as a Python package.
# It contains the plugin system for the Varda application.

from ._hooks import hookimpl, onLoad, onUnload
from .plugin_manager import VardaPluginManager

__all__ = [
    'hookimpl',
    'onLoad',
    'onUnload',
    'VardaPluginManager',
]