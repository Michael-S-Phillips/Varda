# Shared Workspace Toolbar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-viewport toolbars with a single toolbar per workspace that drives tools across every viewport at once.

**Architecture:** A new workspace-level `ViewportToolController` owns one `QToolBar` over a group of viewports. Modal tools (ROI drawing) are armed on every viewport simultaneously and auto-disarm everywhere when any instance completes its action. Ambient tools (Pixel Select) are installed on every viewport permanently and never appear in the toolbar. Tool instances stay per-viewport (their overlays live on one viewport), so `ViewportTool` subclasses barely change.

**Tech Stack:** Python, PyQt6, pyqtgraph, pytest + pytest-qt, uv (package manager), ruff (format), ty (type check).

## Global Constraints

- Type hints everywhere possible; **never** use `Any`. If a hint isn't feasible, omit it.
- Qt-derived classes use camelCase for methods/variables; Qt-independent modules may use snake_case.
- No lazy imports (import at module top) unless needed to break an existing circular import.
- Prefer simplicity/conciseness and declarative patterns.
- Tests are colocated under a sibling `_tests/` folder, files named `test_*.py`.
- Run tests with `uv run pytest`; format with `uv run ruff format`; type-check with `uv run ty check`.

---

## File Structure

**Modified:**
- `src/varda/image_rendering/raster_view/viewport_tools/viewport_tool.py` — add `isAmbient` class attr + `sigCompleted` signal.
- `src/varda/image_rendering/raster_view/viewport_tools/pixel_select_tool.py` — mark `isAmbient = True`; drop the `self.activate()` call from `__init__`.
- `src/varda/image_rendering/raster_view/viewport_tools/roi_tools.py` — emit `sigCompleted` at end of `completeDrawing`.
- `src/varda/image_rendering/raster_view/viewport_tools/tool_registry.py` — add `getAmbientTools()`.
- `src/varda/workspaces/general_image_analysis/general_image_analysis.py` — use the controller; place toolbar on the window.
- `src/varda/workspaces/dual_image_workspace/dual_image_workspace.py` — use the controller (side-by-side + overlay); place toolbar.
- `src/varda/image_rendering/raster_view/image_viewport.py` — remove `addToolBar`.
- `src/varda/image_rendering/raster_view/viewport_protocol.py` — remove `addToolBar` from the protocol.
- `src/varda/image_rendering/raster_view/triple_raster_view.py` — remove the now-dead `addToolbarToViewport`.

**Created:**
- `src/varda/image_rendering/raster_view/viewport_tools/viewport_tool_controller.py` — `ViewportToolController`.
- `src/varda/image_rendering/raster_view/viewport_tools/_tests/__init__.py`
- `src/varda/image_rendering/raster_view/viewport_tools/_tests/conftest.py` — offscreen Qt platform.
- `src/varda/image_rendering/raster_view/viewport_tools/_tests/test_tool_classification.py`
- `src/varda/image_rendering/raster_view/viewport_tools/_tests/test_viewport_tool_controller.py`

**Deleted:**
- `src/varda/image_rendering/raster_view/viewport_tools/tool_manager.py` — replaced by the controller.

---

### Task 1: Tool classification primitives (ambient flag + completion signal)

Adds the two base-class hooks the controller relies on, marks Pixel Select ambient, makes ROI tools announce completion generically, and exposes ambient tools from the registry.

**Files:**
- Modify: `src/varda/image_rendering/raster_view/viewport_tools/viewport_tool.py`
- Modify: `src/varda/image_rendering/raster_view/viewport_tools/pixel_select_tool.py`
- Modify: `src/varda/image_rendering/raster_view/viewport_tools/roi_tools.py`
- Modify: `src/varda/image_rendering/raster_view/viewport_tools/tool_registry.py`
- Create: `src/varda/image_rendering/raster_view/viewport_tools/_tests/__init__.py`
- Create: `src/varda/image_rendering/raster_view/viewport_tools/_tests/conftest.py`
- Test: `src/varda/image_rendering/raster_view/viewport_tools/_tests/test_tool_classification.py`

**Interfaces:**
- Produces:
  - `ViewportTool.isAmbient: bool` (class attr, default `False`).
  - `ViewportTool.sigCompleted` — `pyqtSignal()` with no args; emitted by a modal tool when its one-shot action finishes.
  - `ToolRegistry.getAmbientTools() -> list[type[ViewportTool]]`.
  - `PixelSelectTool.isAmbient == True`.
  - `ROIDrawingTool.completeDrawing()` emits `sigCompleted` after `sigROIDrawingComplete`.

- [ ] **Step 1: Create the test package + offscreen conftest**

Create `src/varda/image_rendering/raster_view/viewport_tools/_tests/__init__.py` (empty file).

Create `src/varda/image_rendering/raster_view/viewport_tools/_tests/conftest.py`:

```python
import os

# Run Qt headless for these widget tests. Must be set before any QApplication is
# created (pytest-qt creates it lazily when qtbot is first used).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

- [ ] **Step 2: Write the failing test**

Create `src/varda/image_rendering/raster_view/viewport_tools/_tests/test_tool_classification.py`:

```python
from __future__ import annotations

from PyQt6.QtCore import QPointF

from varda.image_rendering.raster_view.viewport_tools.viewport_tool import (
    ViewportTool,
)
from varda.image_rendering.raster_view.viewport_tools.pixel_select_tool import (
    PixelSelectTool,
)
from varda.image_rendering.raster_view.viewport_tools.roi_tools import (
    RectangleROITool,
    FreehandROITool,
)
from varda.image_rendering.raster_view.viewport_tools.tool_registry import (
    ToolRegistry,
)


class _FakeImage:
    hasGeospatialData = False


class _FakeHandle:
    def setPoints(self, points):
        pass

    def setText(self, text):
        pass

    def remove(self):
        pass


class _FakeViewport:
    """Minimal stand-in for ImageViewport used by tool unit tests."""

    def __init__(self):
        self.installedTools: list[ViewportTool] = []
        self.imageEntity = _FakeImage()

    def installTool(self, tool):
        if tool not in self.installedTools:
            self.installedTools.append(tool)

    def removeTool(self, tool):
        if tool in self.installedTools:
            self.installedTools.remove(tool)

    def installEventFilter(self, obj):
        pass

    def addCrosshair(self, color=None):
        return _FakeHandle()

    def addPolygonOverlay(self, *args, **kwargs):
        return _FakeHandle()

    def addTextOverlay(self, *args, **kwargs):
        return _FakeHandle()

    def localToImage(self, points):
        return [(float(x), float(y)) for x, y in points]


def test_pixel_select_is_ambient():
    assert PixelSelectTool.isAmbient is True


def test_roi_tools_are_not_ambient():
    assert FreehandROITool.isAmbient is False


def test_default_tool_is_not_ambient():
    assert ViewportTool.isAmbient is False


def test_registry_lists_pixel_select_as_ambient():
    registry = ToolRegistry()
    assert PixelSelectTool in registry.getAmbientTools()
    assert FreehandROITool not in registry.getAmbientTools()


def test_completed_signal_fires_on_roi_completion(qtbot):
    viewport = _FakeViewport()
    tool = RectangleROITool(viewport)
    tool.activate()
    tool.points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    tool.startPoint = QPointF(0.0, 0.0)

    with qtbot.waitSignal(tool.sigCompleted, timeout=1000):
        tool.completeDrawing()
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest src/varda/image_rendering/raster_view/viewport_tools/_tests/test_tool_classification.py -v`
Expected: FAIL — `AttributeError`/`assert` on `isAmbient`, `getAmbientTools`, and `sigCompleted` not existing.

- [ ] **Step 4: Add `isAmbient` and `sigCompleted` to the base class**

In `src/varda/image_rendering/raster_view/viewport_tools/viewport_tool.py`, inside `class ViewportTool`, extend the signals and class attributes:

```python
    sigActivated = pyqtSignal()
    sigDeactivated = pyqtSignal()
    # Emitted by a modal tool when its one-shot action completes, so a controller
    # can disarm the tool across every viewport. Persistent tools never emit it.
    sigCompleted = pyqtSignal()

    # Class attributes that subclasses should override
    toolName = "Generic Tool"
    toolDescription = "Base tool class"
    toolIcon = None  # Path to icon or QIcon
    toolCategory = "General"
    # Ambient tools are installed on every viewport permanently and never shown in
    # the toolbar (e.g. Pixel Select, which is gated on Ctrl+Click).
    isAmbient = False
```

- [ ] **Step 5: Mark Pixel Select ambient and remove its self-activation**

In `src/varda/image_rendering/raster_view/viewport_tools/pixel_select_tool.py`:

Add the class attribute alongside the other metadata:

```python
    # Tool metadata
    toolName = "Pixel Select"
    toolDescription = "Select individual pixels (Ctrl+Click)"
    toolCategory = "Selection"
    isAmbient = True
```

Then remove the `self.activate()` line from `__init__` so lifecycle is the controller's job. The `__init__` becomes:

```python
    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(viewport, parent)
        self._crosshair: CrosshairHandle | None = None
        self.isDragging = False

        self.sigPixelSelected.connect(
            self.onPixelSelected
        )  # TODO: This is probably temp
```

- [ ] **Step 6: Emit `sigCompleted` when an ROI finishes**

In `src/varda/image_rendering/raster_view/viewport_tools/roi_tools.py`, in `ROIDrawingTool.completeDrawing`, add the emit after `stopDrawing()`:

```python
        self.sigROIDrawingComplete.emit(
            {
                "geometry": geometry,
                "roiType": self.roiMode,
            }
        )

        self.stopDrawing()
        self.sigCompleted.emit()
```

- [ ] **Step 7: Add `getAmbientTools` to the registry**

In `src/varda/image_rendering/raster_view/viewport_tools/tool_registry.py`, add this method (next to `getTools`):

```python
    def getAmbientTools(self) -> List[Type[ViewportTool]]:
        """Get all registered ambient tool classes (installed on every viewport)."""
        return [tool for tool in self._tools if tool.isAmbient]
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `uv run pytest src/varda/image_rendering/raster_view/viewport_tools/_tests/test_tool_classification.py -v`
Expected: PASS (5 tests).

- [ ] **Step 9: Format, type-check, commit**

```bash
uv run ruff format src/varda/image_rendering/raster_view/viewport_tools/
uv run ty check src/varda/image_rendering/raster_view/viewport_tools/
git add src/varda/image_rendering/raster_view/viewport_tools/
git commit -m "feat: add ambient flag + completion signal to viewport tools"
```

---

### Task 2: `ViewportToolController`

The core of the feature: a workspace-level controller owning one toolbar over a group of viewports.

**Files:**
- Create: `src/varda/image_rendering/raster_view/viewport_tools/viewport_tool_controller.py`
- Test: `src/varda/image_rendering/raster_view/viewport_tools/_tests/test_viewport_tool_controller.py`

**Interfaces:**
- Consumes: `ViewportTool.isAmbient`, `ViewportTool.sigCompleted`, `ToolRegistry.getAmbientTools()`, `ToolRegistry.getCategories()`, `ToolRegistry.getToolsByCategory()`, `ViewportTool.createAction()`, `ImageViewport.installTool/removeTool/installEventFilter`, `KeyEvent.fromQt`.
- Produces:
  - `ViewportToolController(viewports: Sequence[ImageViewport], parent=None)`.
  - `.toolBar: QToolBar` — the single shared toolbar (modal tools only).
  - `.sigToolActivated = pyqtSignal(object)` / `.sigToolDeactivated = pyqtSignal(object)` — emitted **per modal instance**, preserving each workspace's existing `_onToolActivated` wiring.
  - `.activateTool(toolClass: type[ViewportTool])`, `.deactivateCurrentTool()`.
  - `._modalInstances: dict[ImageViewport, ViewportTool]` (active modal tool per viewport).

- [ ] **Step 1: Write the failing test**

Create `src/varda/image_rendering/raster_view/viewport_tools/_tests/test_viewport_tool_controller.py`:

```python
from __future__ import annotations

from varda.image_rendering.raster_view.viewport_tools.viewport_tool import (
    ViewportTool,
)
from varda.image_rendering.raster_view.viewport_tools.viewport_tool_controller import (
    ViewportToolController,
)
from varda.image_rendering.raster_view.viewport_tools.pixel_select_tool import (
    PixelSelectTool,
)
from varda.image_rendering.raster_view.viewport_tools.roi_tools import (
    FreehandROITool,
    RectangleROITool,
)


class _FakeImage:
    hasGeospatialData = False


class _FakeHandle:
    def setPoints(self, points):
        pass

    def setText(self, text):
        pass

    def remove(self):
        pass


class _FakeViewport:
    def __init__(self):
        self.installedTools: list[ViewportTool] = []
        self.imageEntity = _FakeImage()

    def installTool(self, tool):
        if tool not in self.installedTools:
            self.installedTools.append(tool)

    def removeTool(self, tool):
        if tool in self.installedTools:
            self.installedTools.remove(tool)

    def installEventFilter(self, obj):
        pass

    def addCrosshair(self, color=None):
        return _FakeHandle()

    def addPolygonOverlay(self, *args, **kwargs):
        return _FakeHandle()

    def addTextOverlay(self, *args, **kwargs):
        return _FakeHandle()

    def localToImage(self, points):
        return [(float(x), float(y)) for x, y in points]

    def modalTools(self) -> list[ViewportTool]:
        return [t for t in self.installedTools if not t.isAmbient]

    def ambientTools(self) -> list[ViewportTool]:
        return [t for t in self.installedTools if t.isAmbient]


def _controller(nViewports=2):
    viewports = [_FakeViewport() for _ in range(nViewports)]
    return ViewportToolController(viewports), viewports


def test_ambient_tools_installed_on_every_viewport_at_construction(qtbot):
    _, viewports = _controller()
    for vp in viewports:
        ambient = vp.ambientTools()
        assert len(ambient) == 1
        assert isinstance(ambient[0], PixelSelectTool)


def test_toolbar_excludes_ambient_tools(qtbot):
    controller, _ = _controller()
    labels = [action.text() for action in controller.toolBar.actions()]
    assert PixelSelectTool.toolName not in labels
    assert FreehandROITool.toolName in labels


def test_activate_modal_arms_every_viewport(qtbot):
    controller, viewports = _controller()
    controller.activateTool(FreehandROITool)
    assert len(controller._modalInstances) == len(viewports)
    for vp in viewports:
        modal = vp.modalTools()
        assert len(modal) == 1
        assert isinstance(modal[0], FreehandROITool)
        # ambient tool is still present alongside the modal one
        assert len(vp.ambientTools()) == 1


def test_completion_disarms_all_viewports(qtbot):
    controller, viewports = _controller()
    controller.activateTool(FreehandROITool)
    oneInstance = next(iter(controller._modalInstances.values()))

    oneInstance.sigCompleted.emit()

    assert controller._modalInstances == {}
    for vp in viewports:
        assert vp.modalTools() == []
        assert len(vp.ambientTools()) == 1  # ambient survives


def test_switching_modal_replaces_previous(qtbot):
    controller, viewports = _controller()
    controller.activateTool(FreehandROITool)
    controller.activateTool(RectangleROITool)
    for vp in viewports:
        modal = vp.modalTools()
        assert len(modal) == 1
        assert isinstance(modal[0], RectangleROITool)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest src/varda/image_rendering/raster_view/viewport_tools/_tests/test_viewport_tool_controller.py -v`
Expected: FAIL — `ModuleNotFoundError` for `viewport_tool_controller`.

- [ ] **Step 3: Implement the controller**

Create `src/varda/image_rendering/raster_view/viewport_tools/viewport_tool_controller.py`:

```python
from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtCore import QObject, QEvent, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup
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
        for tool in self._modalInstances.values():
            tool.deactivate()
            self.sigToolDeactivated.emit(tool)
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

    def eventFilter(self, a0, a1):
        """Forward KeyPress events to the active modal tool of the source viewport.

        Without this, key presses are consumed before reaching the imageItem, so
        tools like polygon-drawing never see Enter/Escape/Backspace.
        """
        obj, event = a0, a1
        if event.type() == QEvent.Type.KeyPress and obj in self._modalInstances:
            return self._modalInstances[obj].onKeyEvent(KeyEvent.fromQt(event))
        return False
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest src/varda/image_rendering/raster_view/viewport_tools/_tests/test_viewport_tool_controller.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Format, type-check, commit**

```bash
uv run ruff format src/varda/image_rendering/raster_view/viewport_tools/
uv run ty check src/varda/image_rendering/raster_view/viewport_tools/
git add src/varda/image_rendering/raster_view/viewport_tools/
git commit -m "feat: add ViewportToolController for a shared workspace toolbar"
```

---

### Task 3: Wire the general image analysis workspace to the controller

Replace the three `ToolManager`s + three viewport toolbars with one controller and a single window toolbar.

**Files:**
- Modify: `src/varda/workspaces/general_image_analysis/general_image_analysis.py`

**Interfaces:**
- Consumes: `ViewportToolController`, its `.toolBar`, `.sigToolActivated`.

- [ ] **Step 1: Swap the import**

In `general_image_analysis.py`, replace the `ToolManager` import (line ~27):

```python
from varda.image_rendering.raster_view.viewport_tools.viewport_tool_controller import (
    ViewportToolController,
)
```

- [ ] **Step 2: Replace per-viewport managers with one controller**

In `_initComponents`, replace the block that creates `toolManager1/2/3` and calls `addToolBar` on each viewport (currently lines ~89-97) with:

```python
        # One shared toolbar drives a tool across all three viewports.
        self.toolController = ViewportToolController(
            [
                self.tripleRasterView.viewport1,
                self.tripleRasterView.viewport2,
                self.tripleRasterView.viewport3,
            ],
            self,
        )
        self.addToolBar(self.toolController.toolBar)
```

- [ ] **Step 3: Update signal wiring**

In `_connectSignals`, replace the loop over `toolManager1/2/3` (currently lines ~228-230) with:

```python
        # Wire ROI drawing tools to the collection via the shared controller.
        self.toolController.sigToolActivated.connect(self._onToolActivated)
```

Leave `_onToolActivated` and `_onROIDrawn` unchanged — they already connect `sigROIDrawingComplete` per `ROIDrawingTool` instance.

- [ ] **Step 4: Verify nothing else references the old managers**

Run: `grep -n "toolManager" src/varda/workspaces/general_image_analysis/general_image_analysis.py`
Expected: no matches.

- [ ] **Step 5: Smoke-test imports + launch**

Run: `uv run python -c "import varda.workspaces.general_image_analysis.general_image_analysis"`
Expected: no error.

Then launch the app and open a General Image Analysis workspace. Verify: a single toolbar appears at the top of the window; selecting Rectangle ROI lets you draw on any of the three viewports; finishing a draw on one viewport disarms the tool on all three; Ctrl+Click selects a pixel in any viewport without selecting a toolbar tool.

Run: `uv run python -m varda.main` (or the project's normal launch command)

- [ ] **Step 6: Format, type-check, commit**

```bash
uv run ruff format src/varda/workspaces/general_image_analysis/
uv run ty check src/varda/workspaces/general_image_analysis/general_image_analysis.py
git add src/varda/workspaces/general_image_analysis/general_image_analysis.py
git commit -m "feat: single shared toolbar for general image analysis workspace"
```

---

### Task 4: Wire the dual image workspace to the controller

Same swap for both side-by-side and overlay layouts. Drawing now works on both panes (previously the restriction was implicit per-toolbar).

**Files:**
- Modify: `src/varda/workspaces/dual_image_workspace/dual_image_workspace.py`

**Interfaces:**
- Consumes: `ViewportToolController`, its `.toolBar`, `.sigToolActivated`.

- [ ] **Step 1: Swap the import**

In `dual_image_workspace.py`, replace the `ToolManager` import (line ~28):

```python
from varda.image_rendering.raster_view.viewport_tools.viewport_tool_controller import (
    ViewportToolController,
)
```

- [ ] **Step 2: Replace managers in side-by-side**

In `_initSideBySide`, replace the `toolManager1/2`, the two `addToolBar` calls, and the `_drawingToolManagers` assignment (currently lines ~139-142 and ~153) with:

```python
        self.toolController = ViewportToolController(
            [self.viewport1, self.viewport2], self
        )
        self.addToolBar(self.toolController.toolBar)
```

(Delete the line `self._drawingToolManagers = [self.toolManager1, self.toolManager2]`; the comment above it about co-registered images can stay or be folded into the controller comment.)

- [ ] **Step 3: Replace managers in overlay**

In `_initOverlay`, replace the `toolManager1`, the `addToolBar` call, and the `_drawingToolManagers` assignment (currently lines ~220-225) with:

```python
        self.toolController = ViewportToolController([self.viewport1], self)
        self.addToolBar(self.toolController.toolBar)
```

- [ ] **Step 4: Update signal wiring**

In `_connectSignals`, replace the loop over `self._drawingToolManagers` (currently lines ~266-268) with:

```python
        # Wire drawing tools to the collection via the shared controller.
        self.toolController.sigToolActivated.connect(self._onToolActivated)
```

Leave `_onToolActivated` and `_onROIDrawn` unchanged.

- [ ] **Step 5: Verify nothing else references the old managers**

Run: `grep -n "toolManager\|_drawingToolManagers" src/varda/workspaces/dual_image_workspace/dual_image_workspace.py`
Expected: no matches.

- [ ] **Step 6: Smoke-test imports + launch**

Run: `uv run python -c "import varda.workspaces.dual_image_workspace.dual_image_workspace"`
Expected: no error.

Then launch the app and open a Dual Image workspace in both side-by-side and overlay modes. Verify: one toolbar at the top; ROI drawing works on either pane; completing a draw on one pane disarms both; Ctrl+Click pixel select works on either pane.

- [ ] **Step 7: Format, type-check, commit**

```bash
uv run ruff format src/varda/workspaces/dual_image_workspace/
uv run ty check src/varda/workspaces/dual_image_workspace/dual_image_workspace.py
git add src/varda/workspaces/dual_image_workspace/dual_image_workspace.py
git commit -m "feat: single shared toolbar for dual image workspace"
```

---

### Task 5: Remove dead toolbar plumbing

With both workspaces migrated, the per-viewport toolbar API and the old `ToolManager` are unused. Remove them.

**Files:**
- Modify: `src/varda/image_rendering/raster_view/image_viewport.py`
- Modify: `src/varda/image_rendering/raster_view/viewport_protocol.py`
- Modify: `src/varda/image_rendering/raster_view/triple_raster_view.py`
- Delete: `src/varda/image_rendering/raster_view/viewport_tools/tool_manager.py`

- [ ] **Step 1: Confirm there are no remaining references**

Run:
```bash
grep -rn "addToolBar\|addToolbarToViewport\|ToolManager\b\|getToolbar" src/varda --include="*.py" | grep -v "dual_image_view/dual_image_tool_manager\|dual_image_view/dual_image_view"
```
Expected: only the definitions in `image_viewport.py`, `viewport_protocol.py`, `triple_raster_view.py`, and `tool_manager.py` themselves (no live callers). The legacy `dual_image_view/` `DualImageToolManager` is a different class and must stay.

- [ ] **Step 2: Remove `ImageViewport.addToolBar`**

In `src/varda/image_rendering/raster_view/image_viewport.py`, delete the method (currently lines ~466-468):

```python
    def addToolBar(self, toolbar):
        """Add a toolbar to the viewport."""
        self.layout().addWidget(toolbar)
```

- [ ] **Step 3: Remove `addToolBar` from the viewport protocol**

In `src/varda/image_rendering/raster_view/viewport_protocol.py`, delete the protocol method (currently line ~222):

```python
    def addToolBar(self, toolbar: QWidget) -> None: ...
```

If `QWidget` is now unused in that file after the deletion, remove its import too (check with `grep -n "QWidget" src/varda/image_rendering/raster_view/viewport_protocol.py`).

- [ ] **Step 4: Remove the dead helper in TripleRasterView**

In `src/varda/image_rendering/raster_view/triple_raster_view.py`, delete the `addToolbarToViewport` method (currently lines ~78-88).

- [ ] **Step 5: Delete the old ToolManager**

```bash
git rm src/varda/image_rendering/raster_view/viewport_tools/tool_manager.py
```

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest`
Expected: PASS (no import errors from the removals; controller + classification tests green).

- [ ] **Step 7: Re-launch both workspaces for a final manual check**

Launch the app; open General Image Analysis and Dual Image (both modes). Confirm the shared toolbar, all-viewport arming, auto-disarm on completion, and always-on Ctrl+Click pixel select all still work.

- [ ] **Step 8: Format, type-check, commit**

```bash
uv run ruff format src/varda/image_rendering/raster_view/
uv run ty check src/varda/image_rendering/raster_view/
git add -A src/varda/image_rendering/raster_view/
git commit -m "refactor: remove per-viewport toolbar plumbing and old ToolManager"
```

---

## Notes / verification call-outs

- **Region viewports (general workspace):** `viewport2`/`viewport3` are region-controller targets (self-navigation disabled) but still receive pointer events through their imageItem event filter, and `localToImage` already maps correctly for region display (the hover readout relies on it). The plan arms all three. If manual testing in Task 3 Step 5 shows ROI coordinates are wrong on a region viewport, the fix is to pass only the self-navigating viewport(s) to the controller's drawing group — but default to all three per the agreed semantics.
- **Toolbar placement:** Both workspaces are `QMainWindow`, so `self.addToolBar(...)` puts the single toolbar in the window's native top toolbar area, above all viewports. This resolves the spec's open "exact placement widget" item.
```
