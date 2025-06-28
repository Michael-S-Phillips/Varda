"""
Generic ROI Drawing Controller

A reusable component for managing ROI drawing operations on any graphics view.
This controller handles the drawing logic and orchestration without being coupled
to specific view implementations or data models.
"""

import logging
from typing import List, Dict, Optional, Tuple, Callable, Any
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QToolBar, QLabel
from PyQt6.QtGui import QAction

from varda.features.components.roi_drawing import ROIDrawingObject, ROIMode

logger = logging.getLogger(__name__)


@dataclass
class ROIDrawingConfig:
    """Configuration for ROI drawing behavior"""

    colors: List[Tuple[int, int, int, int]] = None
    defaultMode: ROIMode = ROIMode.FREEHAND
    enableToolbar: bool = True
    toolbarTitle: str = "ROI Tools"

    def __post_init__(self):
        if self.colors is None:
            self.colors = [
                (255, 0, 0, 100),  # Red
                (0, 255, 0, 100),  # Green
                (0, 0, 255, 100),  # Blue
                (255, 255, 0, 100),  # Yellow
                (255, 0, 255, 100),  # Magenta
                (0, 255, 255, 100),  # Cyan
                (255, 255, 255, 100),  # White
            ]


@dataclass
class ROIDrawingRequest:
    """Request to start drawing a new ROI"""

    targetItem: Any  # The graphics item to anchor the ROI to
    mode: Optional[ROIMode] = None
    color: Optional[Tuple[int, int, int, int]] = None
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata for the ROI


@dataclass
class ROIDrawingResult:
    """Result of completed ROI drawing"""

    points: List[List[float]]  # [x_coords, y_coords]
    geoPoints: Optional[List[List[float]]] = None  # Geographic coordinates if available
    color: Tuple[int, int, int, int] = (255, 0, 0, 100)
    mode: ROIMode = ROIMode.FREEHAND
    metadata: Optional[Dict[str, Any]] = None


class ROIDrawingController(QObject):
    """
    Generic controller for ROI drawing operations.

    This controller manages the drawing process without being coupled to specific
    views or data models. It communicates through signals and delegates view-specific
    operations to the caller.
    """

    # Signals for communicating with the outside world
    roiDrawingStarted = pyqtSignal(object)  # Emits ROISelector when drawing starts
    roiDrawingCompleted = pyqtSignal(object)  # Emits ROIDrawingResult when complete
    roiDrawingCanceled = pyqtSignal()
    drawingModeChanged = pyqtSignal(int)  # Emits ROIMode when mode changes
    statusMessageChanged = pyqtSignal(str)  # Emits status messages

    # Signals for requesting operations from the view
    requestAddToView = pyqtSignal(object)  # Request to add ROISelector to view
    requestRemoveFromView = pyqtSignal(
        object
    )  # Request to remove ROISelector from view
    requestShowAllROIs = pyqtSignal()  # Request to show all ROIs
    requestHideAllROIs = pyqtSignal()  # Request to hide all ROIs

    def __init__(self, config: Optional[ROIDrawingConfig] = None, parent=None):
        super().__init__(parent)

        self.config = config or ROIDrawingConfig()

        # Drawing state
        self.currentMode = self.config.defaultMode
        self.activeSelector: Optional[ROIDrawingObject] = None
        self.colorIndex = 0

        # UI components
        self.toolbar: Optional[QToolBar] = None
        self.statusLabel: Optional[QLabel] = None

        # Create toolbar if enabled
        if self.config.enableToolbar:
            self._createToolbar()

    def _createToolbar(self) -> QToolBar:
        """Create and configure the ROI drawing toolbar"""
        self.toolbar = QToolBar(self.config.toolbarTitle)

        # Drawing mode actions
        self.actionFreehand = QAction("Freehand", self.toolbar)
        self.actionFreehand.setCheckable(True)
        self.actionFreehand.setChecked(self.currentMode == ROIMode.FREEHAND)
        self.actionFreehand.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.FREEHAND)
        )

        self.actionRectangle = QAction("Rectangle", self.toolbar)
        self.actionRectangle.setCheckable(True)
        self.actionRectangle.setChecked(self.currentMode == ROIMode.RECTANGLE)
        self.actionRectangle.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.RECTANGLE)
        )

        self.actionEllipse = QAction("Ellipse", self.toolbar)
        self.actionEllipse.setCheckable(True)
        self.actionEllipse.setChecked(self.currentMode == ROIMode.ELLIPSE)
        self.actionEllipse.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.ELLIPSE)
        )

        self.actionPolygon = QAction("Polygon", self.toolbar)
        self.actionPolygon.setCheckable(True)
        self.actionPolygon.setChecked(self.currentMode == ROIMode.POLYGON)
        self.actionPolygon.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.POLYGON)
        )

        # Store actions for easy access
        self.modeActions = [
            self.actionFreehand,
            self.actionRectangle,
            self.actionEllipse,
            self.actionPolygon,
        ]

        # Add actions to toolbar
        for action in self.modeActions:
            self.toolbar.addAction(action)

        self.toolbar.addSeparator()

        # ROI visibility controls
        self.actionShowAll = QAction("Show All ROIs", self.toolbar)
        self.actionShowAll.triggered.connect(self._onShowAllRois)
        self.toolbar.addAction(self.actionShowAll)

        self.actionHideAll = QAction("Hide All ROIs", self.toolbar)
        self.actionHideAll.triggered.connect(self._onHideAllRois)
        self.toolbar.addAction(self.actionHideAll)

        # Status label
        self.statusLabel = QLabel("")
        self.toolbar.addWidget(self.statusLabel)

        return self.toolbar

    def getToolbar(self) -> Optional[QToolBar]:
        """Get the ROI drawing toolbar"""
        return self.toolbar

    def setDrawingMode(self, mode: ROIMode):
        """Set the current drawing mode"""
        if self.currentMode == mode:
            return

        self.currentMode = mode

        # Update toolbar actions
        if self.toolbar:
            for i, action in enumerate(self.modeActions):
                action.setChecked(i == mode)

        # Update active selector if drawing
        if self.activeSelector:
            self.activeSelector.setMode(mode)

        # Emit signals
        self.drawingModeChanged.emit(mode)

        modeNames = ["Freehand", "Rectangle", "Ellipse", "Polygon"]
        self._updateStatus(f"Drawing Mode: {modeNames[mode]}")

    def getDrawingMode(self) -> ROIMode:
        """Get the current drawing mode"""
        return self.currentMode

    def startDrawing(self, request: ROIDrawingRequest) -> bool:
        """
        Start drawing a new ROI

        Args:
            request: ROI drawing request with target item and parameters

        Returns:
            True if drawing started successfully, False otherwise
        """
        try:
            # Cancel any active drawing
            self.cancelDrawing()

            # Determine drawing parameters
            mode = request.mode if request.mode is not None else self.currentMode
            color = request.color if request.color is not None else self._getNextColor()

            # Create new ROI selector
            self.activeSelector = ROIDrawingObject(color, mode)

            # Set target item for anchoring
            if request.targetItem:
                self.activeSelector.setTargetImageItem(request.targetItem)

            # Apply any additional metadata
            if request.metadata:
                # Set geo transform if provided
                if "geoTransform" in request.metadata:
                    self.activeSelector.setGeoTransform(
                        request.metadata["geoTransform"]
                    )

                # Set image index if provided
                if "imageIndex" in request.metadata:
                    self.activeSelector.setImageIndex(request.metadata["imageIndex"])

            # Connect signals
            self.activeSelector.sigDrawingComplete.connect(self._onDrawingComplete)
            self.activeSelector.sigDrawingCanceled.connect(self._onDrawingCanceled)

            # Request view to add the selector
            self.requestAddToView.emit(self.activeSelector)

            # Start drawing
            self.activeSelector.draw()

            # Update status
            instructions = {
                ROIMode.FREEHAND: "Click and drag to draw freehand ROI. Release to complete.",
                ROIMode.RECTANGLE: "Click and drag to define rectangle. Release to complete.",
                ROIMode.ELLIPSE: "Click and drag to define ellipse. Release to complete.",
                ROIMode.POLYGON: "Click to add points. Double-click or press Enter to complete. Esc to cancel.",
            }
            self._updateStatus(instructions[mode])

            # Emit started signal
            self.roiDrawingStarted.emit(self.activeSelector)

            return True

        except Exception as e:
            logger.error(f"Error starting ROI drawing: {e}")
            self._updateStatus("Error starting ROI drawing")
            return False

    def cancelDrawing(self):
        """Cancel any active drawing operation"""
        if self.activeSelector:
            # Disconnect signals to prevent recursion
            self.activeSelector.sigDrawingComplete.disconnect()
            self.activeSelector.sigDrawingCanceled.disconnect()

            # Cancel the drawing
            self.activeSelector.cancelDrawing()

            # Request removal from view
            self.requestRemoveFromView.emit(self.activeSelector)

            # Clean up
            self.activeSelector = None

            self._updateStatus("ROI drawing canceled")
            self.roiDrawingCanceled.emit()

    def isDrawingActive(self) -> bool:
        """Check if a drawing operation is currently active"""
        return self.activeSelector is not None

    def _getNextColor(self) -> Tuple[int, int, int, int]:
        """Get the next color in the rotation"""
        color = self.config.colors[self.colorIndex]
        self.colorIndex = (self.colorIndex + 1) % len(self.config.colors)
        return color

    def _updateStatus(self, message: str):
        """Update status message"""
        if self.statusLabel:
            self.statusLabel.setText(message)
        self.statusMessageChanged.emit(message)

    def _onDrawingComplete(self, roiData: Dict[str, Any]):
        """Handle completion of ROI drawing"""
        if not self.activeSelector:
            return

        try:
            # Extract data from the ROI selector
            points = roiData.get("points", [])
            geoPoints = roiData.get("geo_points")
            color = roiData.get("color", (255, 0, 0, 100))
            mode = roiData.get("mode", ROIMode.FREEHAND)
            metadata = roiData.get("metadata", {})

            # Create result object
            result = ROIDrawingResult(
                points=points,
                geoPoints=geoPoints,
                color=color,
                mode=mode,
                metadata=metadata,
            )

            # Clean up
            self.activeSelector = None
            self._updateStatus("ROI drawing completed")

            # Emit completion signal
            self.roiDrawingCompleted.emit(result)

        except Exception as e:
            logger.error(f"Error handling drawing completion: {e}")
            self._updateStatus("Error completing ROI drawing")
            self.cancelDrawing()

    def _onDrawingCanceled(self):
        """Handle cancellation of ROI drawing"""
        self.cancelDrawing()

    def _onShowAllRois(self):
        """Handle show all ROIs request"""
        self.requestShowAllROIs.emit()
        self._updateStatus("All ROIs visible")

    def _onHideAllRois(self):
        """Handle hide all ROIs request"""
        self.requestHideAllROIs.emit()
        self._updateStatus("All ROIs hidden")

    def cleanup(self):
        """Clean up resources"""
        self.cancelDrawing()

        if self.toolbar:
            self.toolbar.deleteLater()
            self.toolbar = None
