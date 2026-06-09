"""Bridges a viewport's right-click to the app_model viewport context menu."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app_model import Application
from app_model.backends.qt import QModelMenu
from PyQt6.QtCore import QObject, QPoint

from varda.image_rendering.raster_view.viewport_actions import (
    VIEWPORT_CONTEXT_MENU_ID,
    ViewportClickContext,
    setCurrentClickContext,
)

if TYPE_CHECKING:
    from varda.rois.roi_manager_widget import ROIManagerWidget

logger = logging.getLogger(__name__)


class ViewportContextMenuController(QObject):
    """Shows the app_model viewport context menu and owns the column-lock toggle."""

    def __init__(
        self, roiManager: ROIManagerWidget, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._roiManager = roiManager

    def onContextMenuRequested(
        self, imageCol: float, imageRow: float, globalPos: QPoint
    ) -> None:
        app = Application.get_app("varda")
        if app is None:
            logger.warning("No 'varda' app instance; cannot show viewport menu")
            return

        def _place() -> None:
            self._roiManager.placeTemplate(
                clickRow=int(round(imageRow)),
                clickCol=int(round(imageCol)),
            )

        setCurrentClickContext(ViewportClickContext(placeTemplate=_place))
        try:
            menu = QModelMenu(VIEWPORT_CONTEXT_MENU_ID, app)
            menu.exec(globalPos)
        finally:
            setCurrentClickContext(None)
