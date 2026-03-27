from __future__ import annotations

from typing import TYPE_CHECKING

from app_model import Application

from varda.common.observable_list import ImageList
from varda.plugins import VardaPluginManager

if TYPE_CHECKING:
    from varda.maingui import MainGUI


class VardaApplication(Application):
    """Central application object for Varda.

    Subclasses app-model's Application to add Varda-specific state
    (images, plugin manager, main window reference) alongside the
    command/menu/keybinding registries and DI injection store.
    """

    def __init__(self) -> None:
        super().__init__("varda")
        self.pm = VardaPluginManager()
        self.maingui: MainGUI | None = None
        self.images = ImageList()
