# Shared Workspace Toolbar — Design

**Date:** 2026-06-19
**Status:** Approved (pending implementation plan)

## Problem

Each `ImageViewport` currently carries its own toolbar, attached below it via
`ImageViewport.addToolBar`. Both shipping workspaces show multiple viewports, so
each workspace ends up with multiple toolbars. To use a tool on a given viewport
the user must find and click that viewport's own toolbar. This is awkward, and
the per-viewport toolbar has too little horizontal space to display all tools
cleanly.

## Goal

Give each workspace a **single toolbar above all its viewports** that drives a
tool across every viewport in the workspace.

### Semantics (decided during brainstorming)

- **All viewports at once.** Selecting a modal tool (e.g. an ROI drawing tool)
  arms *every* viewport in the workspace. The user can then act in whichever
  viewport they like; each viewport maintains its own preview overlay.
- **Auto-disarm on completion.** When a one-shot action completes on any one
  viewport (e.g. an ROI is finished), the tool disarms across *all* viewports —
  the user does not have to manually cancel it on the others.
- **Ambient tools are always on.** Pixel Select is gated on Ctrl+Click, so it
  never interferes with pan/zoom. It is installed on every viewport permanently
  and does not appear in the toolbar at all.

## Current Architecture (for reference)

- `ViewportTool` (`viewport_tools/viewport_tool.py`) — base `QObject`. Holds a
  single `self.viewport`, created fresh on each activation, creates its overlays
  (crosshair, polygon preview, text) directly on that viewport. `activate()`
  calls `viewport.installTool(self)`; `deactivate()` calls `removeTool`.
- `ToolManager` (`viewport_tools/tool_manager.py`) — **per viewport**. Builds a
  toolbar from `ToolRegistry`, tracks one `activeTool`, instantiates the tool
  bound to its viewport on a toolbar click, forwards `KeyPress` to the active
  tool via an event filter on the viewport.
- `ToolRegistry` (`viewport_tools/tool_registry.py`) — singleton; lists tool
  classes by `toolCategory`.
- `ImageViewport.installTool/removeTool` — viewport keeps a `_tools` list and
  dispatches translated `PointerEvent`s to each installed tool (first to return
  `True` consumes). `ImageViewport.addToolBar` appends a toolbar widget under
  the viewport.
- Workspaces:
  - `general_image_analysis` — 3 viewports of the **same** image
    (`TripleRasterView`), 3 `ToolManager`s, 3 toolbars.
  - `dual_image_workspace` — 2 viewports of **co-registered** images (side by
    side) or 1 (overlay mode), one `ToolManager` per viewport, toolbars below.
- ROI completion wiring (preserved): each workspace connects
  `ToolManager.sigToolActivated` → `_onToolActivated`, which (if the tool is an
  `ROIDrawingTool`) connects `tool.sigROIDrawingComplete` → `_onROIDrawn`, which
  adds the ROI to the collection.

The key property we exploit: **tool instances are inherently per-viewport**
(their overlays live on one viewport). So "one shared toolbar" is implemented as
*one toolbar driving a group of per-viewport tool instances* — the tools
themselves barely change.

## Design (Approach A)

### 1. Tool categories & base-class changes

Two class-level attributes on `ViewportTool` classify each tool; behavior flows
from them:

- `isAmbient: bool = False` — ambient tools are installed on every viewport at
  startup and never appear in the toolbar. `PixelSelectTool` sets
  `isAmbient = True`.
- `sigCompleted = pyqtSignal()` — a new generic signal on the base. A **modal**
  tool emits it when its single action finishes; the controller uses it to
  disarm the whole group. A modal tool that should stay active simply never
  emits it, so no separate "one-shot" flag is required.

Concrete changes:

- `ROIDrawingTool.completeDrawing()` emits `self.sigCompleted` immediately after
  `self.sigROIDrawingComplete` (so existing ROI wiring is untouched and the
  controller gets a generic completion notice).
- `PixelSelectTool` sets `isAmbient = True` and **removes the `self.activate()`
  call from its `__init__`** — lifecycle becomes the controller's
  responsibility. (The pre-existing `# TODO: temp` self-connect and plot
  behavior are out of scope and left as-is.)

### 2. `ViewportToolController` (replaces `ToolManager`)

`ToolManager` is rewritten into a workspace-level controller and renamed
`ViewportToolController` (it no longer manages a single viewport). It owns one
toolbar over a group of viewports.

**Constructor:** `ViewportToolController(viewports: Sequence[ImageViewport], parent=None)`

On construction it:
- Builds **one** `QToolBar` from `ToolRegistry`, including only **modal**
  (non-ambient) tools, grouped/sorted as today. The `QActionGroup` uses
  `ExclusionPolicy.ExclusiveOptional` so "no modal tool active" is a valid state
  (required for auto-disarm to fully unselect).
- Instantiates each **ambient** tool once per viewport and activates them —
  permanently installed for the workspace's lifetime.
- Installs a key-event filter on each viewport that forwards `KeyPress` to that
  viewport's active *modal* instance (mirrors today's `ToolManager` filter).

**State:**
- `self._modalInstances: dict[ImageViewport, ViewportTool]` — the active modal
  tool per viewport (empty when no modal tool is armed).
- `self._ambientInstances: list[ViewportTool]` — the permanently-installed
  ambient tools.

**Signals:** keeps `sigToolActivated(object)` / `sigToolDeactivated(object)`,
emitted **per instance**, so workspaces' existing per-instance wiring continues
to work.

**Behavior:**
- `activateTool(toolClass)`:
  1. Disarm any current modal group (`deactivateCurrentTool`).
  2. For each viewport: instantiate `toolClass(viewport)`, call
     `tool.activate()` (installs on that viewport), store in `_modalInstances`,
     connect `tool.sigCompleted` → `_onToolCompleted`, and emit
     `sigToolActivated(tool)`.
- `_onToolCompleted()`: disarm the whole modal group across all viewports and
  uncheck the toolbar action. (The instance that completed has already stopped
  drawing; the others are cancelled by `deactivate`.)
- `deactivateCurrentTool()`: `deactivate()` every modal instance, emit
  `sigToolDeactivated` per instance, clear `_modalInstances`.

The viewport-side event dispatch (`ImageViewport.eventFilter` →
`installTool`/`_tools`) is unchanged; each viewport already dispatches pointer
events to its own installed instances.

### 3. Workspace integration & toolbar placement

Both workspaces drop their N `ToolManager`s for a single controller and place
its toolbar **above** the viewport grid in the workspace layout (no longer via
`ImageViewport.addToolBar`).

- **general_image_analysis**: replace `toolManager1/2/3` with
  `self.toolController = ViewportToolController([vp1, vp2, vp3])`; add
  `toolController.toolBar` at the top of the raster-view container. In
  `_connectSignals`, connect `toolController.sigToolActivated` → existing
  `_onToolActivated` (logic unchanged). All three viewports now draw.
- **dual_image_workspace**: replace the per-viewport managers (and the
  overlay-mode single manager) with one controller over the relevant viewports;
  toolbar above. The old "only the right viewport draws" restriction is removed
  — both panes draw, matching the "any viewport" goal. The `_drawingToolManagers`
  list is replaced by the single controller.

### 4. Cleanup

- Remove `ImageViewport.addToolBar` and its `viewport_protocol.py` entry (now
  unused). Remove the `addToolBar` path in `triple_raster_view.py` if nothing
  else uses it.
- The old single-viewport `ToolManager` semantics are gone (file rewritten as
  the controller). Legacy `dual_image_view/dual_image_tool_manager.py` is a
  separate legacy `ProjectContext` view and is left untouched.

## Testing

The controller's grouping logic is the testable core, isolated from real Qt
widgets via a lightweight fake viewport (stub exposing
`installTool`/`removeTool` and no-op overlay methods, plus `imageEntity`):

- Activating a modal tool creates exactly one instance per viewport and installs
  each on its own viewport.
- `sigCompleted` from any one instance disarms all instances and unchecks the
  toolbar action.
- Ambient tools are installed on every viewport at construction and survive
  modal-tool switches (never deactivated by `activateTool`).
- Switching modal tools deactivates the previous group before arming the new one.

Pure-Qt-widget behavior (toolbar rendering, real pointer dispatch) remains
manual, consistent with the repo's current GUI-testing limits.

## Open items to verify during implementation

- Region viewports in `general_image_analysis` (viewport2/3 are
  region-controller targets with self-navigation disabled). Confirm modal
  drawing on them maps coordinates correctly via `localToImage` for the region
  case; adjust if a region viewport should be excluded from the drawing group.
- Exact placement widget for the toolbar in each workspace's existing
  layout/dock structure.
