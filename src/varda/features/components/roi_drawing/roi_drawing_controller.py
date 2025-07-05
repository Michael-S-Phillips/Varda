"""
Generic ROI Drawing Controller

A reusable component for managing ROI drawing operations on any graphics view.
This controller handles the drawing logic and orchestration without being coupled
to specific view implementations or data models.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from varda.app.services.roi_utils import VardaROIItem
from varda.core.entities import ROIMode
from varda.features.components.generic_protocols import Viewport
from varda.features.components.viewport_tools import (
    ROIDrawingTool,
    FreehandROITool,
    RectangleROITool,
    EllipseROITool,
    PolygonROITool,
)

logger = logging.getLogger(__name__)


class ROIDrawingController(QObject):

    sigDrawingComplete = pyqtSignal(object)
    sigDrawingCanceled = pyqtSignal(object)

    @dataclass
    class ActiveState:
        viewport: Viewport
        tool: Optional[ROIDrawingTool]
        ROIItem: VardaROIItem

    def __init__(self, parent=None):
        super().__init__(parent)
        self.activeState: Optional[ROIDrawingController.ActiveState] = None

    def startDrawing(self, mode: ROIMode, viewport: Viewport):
        """begin drawing a new ROI on the specified image item"""
        if self.activeState is not None:
            logger.warning(
                "Already drawing an ROI. Complete or cancel the current drawing first."
            )
            return

        if mode == ROIMode.FREEHAND:
            tool = FreehandDrawingTool(viewport)
        elif mode == ROIMode.RECTANGLE:
            tool = RectangleDrawingTool(viewport)
        elif mode == ROIMode.ELLIPSE:
            tool = EllipseDrawingTool(viewport)
        elif mode == ROIMode.POLYGON:
            tool = PolygonDrawingTool(viewport)
        else:
            raise ValueError(f"Unknown ROI mode: {mode}")

        tool.sigDrawingComplete.connect(self._onDrawingComplete)
        tool.sigDrawingCanceled.connect(self._onDrawingCanceled)
        tool.sigDrawingUpdated.connect(self._onDrawingUpdated)

        ROIItem = VardaROIItem(tool.roiEntity)
        viewport.viewBox.addItem(ROIItem)

        self.activeState = self.ActiveState(viewport, tool, ROIItem)
        tool.startDrawing()

    def _reset(self):
        """Reset the active state"""
        if self.activeState is None:
            return

        self.activeState.tool.sigDrawingComplete.disconnect(self._onDrawingComplete)
        self.activeState.tool.sigDrawingCanceled.disconnect(self._onDrawingCanceled)
        self.activeState.tool.sigDrawingUpdated.disconnect(self._onDrawingUpdated)
        self.activeState.viewport.viewBox.removeItem(self.activeState.ROIItem)
        self.activeState = None

    def _onDrawingComplete(self, tool: BaseROIDrawingTool):
        """Handle completion of ROI drawing"""
        roiResult = tool.roiEntity.clone()
        logger.info(f"ROI drawing completed: {roiResult}")
        self._reset()
        self.sigDrawingComplete.emit(roiResult)

    def _onDrawingCanceled(self, tool: BaseROIDrawingTool):
        """Handle cancellation of ROI drawing"""
        self._reset()
        self.sigDrawingCanceled.emit()

    def _onDrawingUpdated(self, tool: BaseROIDrawingTool):
        """Handle updates during drawing"""
        self.activeState.ROIItem.setROIData(tool.roiEntity)
        self.activeState.ROIItem.refresh()
