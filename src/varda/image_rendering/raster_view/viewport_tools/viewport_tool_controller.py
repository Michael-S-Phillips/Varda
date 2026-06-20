from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtCore import QObject, QEvent, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QKeyEvent
from PyQt6.QtWidgets import QToolBar

from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.pointer_event import KeyEvent
from varda.image_rendering.raster_view.viewport_tools.tool_registry import (
    ToolRegistry,
)
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import (
    ViewportTool,
)


class ViewportToolController(QObject):
    """Drives tools across a group of viewports from a single shared toolbar.

    Modal tools (chosen in the toolbar) are armed on every viewport at once and
    auto-disarm everywhere when any instance emits ``sigCompleted``. Ambient tools
    (e.g. Pixel Select) are installed on every viewport permanently and never appear
    in the toolbar. Tool instances stay per-viewport, since their overlays live on
    one viewport.
    """

    # Emitted once per modal instance created/destroyed, so consumers can wire
    # per-instance signals (e.g. ROIDrawingTool.sigROIDrawingComplete).
    sigToolActivated = pyqtSignal(object)
    sigToolDeactivated = pyqtSignal(object)

    def __init__(self, viewports: Sequence[ImageViewport], parent=None):
        super().__init__(parent)
        self.viewports: list[ImageViewport] = list(viewports)
        self.toolRegistry = ToolRegistry()

        self._modalInstances: dict[ImageViewport, ViewportTool] = {}
        # Holds ambient tool instances to keep them alive for the controller's lifetime.
        self._ambientInstances: list[ViewportTool] = []
        self._currentModalClass: type[ViewportTool] | None = None
        self._actions: dict[type[ViewportTool], QAction] = {}

        self.toolBar = self._createToolbar()
        self._installAmbientTools()

        for viewport in self.viewports:
            viewport.installEventFilter(self)

    # --- construction helpers ---

    def _createToolbar(self) -> QToolBar:
        """Build a single toolbar holding every modal (non-ambient) tool."""
        toolbar = QToolBar("Tools")
        self._actionGroup = QActionGroup(toolbar)
        # ExclusiveOptional so "no modal tool active" is valid (needed for auto-disarm).
        self._actionGroup.setExclusionPolicy(
            QActionGroup.ExclusionPolicy.ExclusiveOptional
        )

        firstCategory = True
        for category in sorted(self.toolRegistry.getCategories()):
            tools = [
                tool
                for tool in self.toolRegistry.getToolsByCategory(category)
                if not tool.isAmbient
            ]
            if not tools:
                continue
            if not firstCategory:
                toolbar.addSeparator()
            firstCategory = False
            for toolClass in sorted(tools, key=lambda t: t.toolName):
                action = toolClass.createAction(toolbar)
                action.triggered.connect(
                    lambda checked, tc=toolClass: self._onActionTriggered(tc, checked)
                )
                self._actionGroup.addAction(action)
                toolbar.addAction(action)
                self._actions[toolClass] = action
        return toolbar

    def _installAmbientTools(self) -> None:
        """Instantiate each ambient tool once per viewport and keep it installed."""
        for toolClass in self.toolRegistry.getAmbientTools():
            for viewport in self.viewports:
                tool = toolClass(viewport, parent=self)
                tool.activate()
                self._ambientInstances.append(tool)

    # --- modal tool lifecycle ---

    def _onActionTriggered(self, toolClass: type[ViewportTool], checked: bool) -> None:
        if checked:
            self.activateTool(toolClass)
        else:
            self.deactivateCurrentTool()

    def activateTool(self, toolClass: type[ViewportTool]) -> None:
        """Arm a modal tool on every viewport."""
        self.deactivateCurrentTool()
        self._currentModalClass = toolClass
        for viewport in self.viewports:
            tool = toolClass(viewport, parent=self)
            tool.sigCompleted.connect(self._onToolCompleted)
            self._modalInstances[viewport] = tool
            tool.activate()
            self.sigToolActivated.emit(tool)

        action = self._actions.get(toolClass)
        if action is not None and not action.isChecked():
            action.setChecked(True)

    def deactivateCurrentTool(self) -> None:
        """Disarm the modal tool on every viewport."""
        if not self._modalInstances:
            self._currentModalClass = None
            return
        for tool in list(self._modalInstances.values()):
            tool.deactivate()
            self.sigToolDeactivated.emit(tool)
            tool.deleteLater()
        self._modalInstances.clear()
        self._currentModalClass = None

    def _onToolCompleted(self) -> None:
        """A modal instance finished its action -> disarm the group + uncheck."""
        toolClass = self._currentModalClass
        self.deactivateCurrentTool()
        if toolClass is not None:
            action = self._actions.get(toolClass)
            if action is not None:
                action.setChecked(False)

    # --- key forwarding ---

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        """Forward KeyPress events to the active modal tool of the source viewport.

        Without this, key presses are consumed before reaching the imageItem, so
        tools like polygon-drawing never see Enter/Escape/Backspace.
        """
        obj, event = a0, a1
        if (
            event is not None
            and isinstance(a0, ImageViewport)
            and event.type() == QEvent.Type.KeyPress
            and a0 in self._modalInstances
        ):
            if isinstance(event, QKeyEvent):
                return self._modalInstances[a0].onKeyEvent(KeyEvent.fromQt(event))
        return False
