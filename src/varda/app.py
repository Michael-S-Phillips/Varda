from __future__ import annotations

from typing import TYPE_CHECKING

from app_model import Application

from varda._actions import ALL_ACTIONS
from varda._actions._context_keys import IMAGE_COUNT
from varda.common.di_types import ProjectImages
from varda.plugins import VardaPluginManager

# if TYPE_CHECKING:
from varda.maingui import MainGUI


class VardaApplication(Application):
    """Subclasses app-model's Application to co-locate Varda state
    (images, plugin manager, main window) with the command/menu/keybinding
    registries and DI injection store.
    """

    def __init__(self) -> None:
        super().__init__("varda")
        self.pluginManager = VardaPluginManager()
        self.maingui: MainGUI | None = None
        self.images = ProjectImages()

        # the lambdas defer resolution till later, since self.maingui isn't assigned right away
        self.injection_store.register_provider(lambda: self.images, ProjectImages)
        self.injection_store.register_provider(lambda: self.maingui, MainGUI)

        self.context[IMAGE_COUNT] = 0
        self.images.sigDataChanged.connect(self._onImagesChanged)

        self.register_actions(ALL_ACTIONS)

    def _onImagesChanged(self, items: list) -> None:
        count = len(items)
        if self.context.get(IMAGE_COUNT) != count:
            self.context[IMAGE_COUNT] = count
