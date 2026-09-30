"""Bridges ImageListWidget interactions to the app_model image-list actions."""

from __future__ import annotations

from app_model import Application
from app_model.backends.qt import QModelMenu
from PyQt6.QtCore import QObject, QPoint

from varda.all_images_view_list.image_list_actions import (
    IMAGE_LIST_CONTEXT_MENU_ID,
    OPEN_GENERAL_ANALYSIS_ID,
    ImageListClickContext,
    setCurrentClickContext,
)
from varda.common.entities import VardaRaster


class ImageListMenuController(QObject):
    """Double-click opens the image directly; right-click shows the context menu."""

    def __init__(self, app: Application, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._app = app

    def onImagesActivated(self, images: list[VardaRaster]) -> None:
        setCurrentClickContext(ImageListClickContext(images))
        try:
            # .result() surfaces any exception raised inside the command callback
            self._app.commands.execute_command(OPEN_GENERAL_ANALYSIS_ID).result()
        finally:
            setCurrentClickContext(None)

    def onContextMenuRequested(
        self, images: list[VardaRaster], globalPos: QPoint
    ) -> None:
        if not images:
            return
        setCurrentClickContext(ImageListClickContext(images))
        try:
            QModelMenu(IMAGE_LIST_CONTEXT_MENU_ID, self._app).exec(globalPos)
        finally:
            setCurrentClickContext(None)
