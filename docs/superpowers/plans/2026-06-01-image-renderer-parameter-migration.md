# Image Renderer Settings → Parameter System Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the image renderer's settings from a hand-mutated dataclass + bespoke Qt panel onto Varda's parameter system, so the settings UI is auto-generated and every setting (especially stretch algorithm + manual min/max) is programmatically editable, and wire the histogram's region-drag to drive the stretch min/max.

**Architecture:** `RendererSettings` becomes a `ParameterGroup`. Three render-specific `Parameter` subclasses (`BandParameter`, `ColorMapParameter`, `StretchParameter`) live in a new `image_rendering/render_parameters.py`. `ImageRenderer` owns one stable settings object, listens to its `sigParameterChanged` (clears cache + emits `sigShouldRefresh`), and exposes convenience methods for manual stretch. The settings panel shrinks to composing param widgets plus one mode-driven stacked layout. A prerequisite fix makes nested `ParameterGroup`s propagate change signals correctly.

**Tech Stack:** Python 3.13, PyQt6, pyqtgraph, numpy, numba (existing), pytest + pytest-qt, `uv` for running, `ruff` for formatting, `ty` for type checking.

**Spec:** `docs/superpowers/specs/2026-06-01-image-renderer-parameter-migration-design.md`

---

## File Structure

**Create:**
- `src/varda/image_rendering/render_parameters.py` — `BandParameter`, `ColorMapParameter`, `StretchParameter` (render-specific parameter types; keeps pyqtgraph/stretch deps out of `common/parameter.py`).
- `src/varda/common/_tests/conftest.py` — headless Qt for this dir's tests.
- `src/varda/image_rendering/_tests/conftest.py` — headless Qt.
- `src/varda/image_rendering/_tests/test_render_parameters.py` — tests for the three new param types.
- `src/varda/image_rendering/_tests/test_image_renderer.py` — tests for `RendererSettings` + `ImageRenderer`.
- `src/varda/common/_tests/test_parameter_group_nesting.py` — tests for the nested-group signal/clone fix.

**Modify:**
- `src/varda/common/parameter.py` — fix nested-`ParameterGroup` signal payload + `clone()`.
- `src/varda/image_rendering/image_renderer.py` — `RenderMode`, `RgbBandGroup`, `MonoViewGroup`, `RendererSettings(ParameterGroup)`, rewritten `ImageRenderer`, rewritten `RendererSettingsPanel`.
- `src/varda/image_rendering/new_histogram_view.py` — read `mode` as enum; movable regions wired to `setStretchMinMax`; updated `__main__`.

**Unaffected (verified):** `general_image_analysis.py`, `dual_image_workspace.py`, `imageview_list.py`, `triple_raster_view.py`, `image_viewport.py`, `varda_viewport.py`, `image_region_item.py`, `_experiments/vispy_varda_raster_viewer.py` — they only construct `ImageRenderer(image=...)`, call `render()`, or connect `sigShouldRefresh`. Task 9 greps to confirm.

---

## Task 1: Fix nested `ParameterGroup` change propagation

Nesting `ParameterGroup`s (this migration's `rgb`/`mono`) exposes two dormant bugs in `common/parameter.py`:
1. `ParameterGroup.sigParameterChanged` is `pyqtSignal()` (no arg), but the child-wiring slot is `lambda _: ...` (needs one arg) — a child group emitting nothing raises `TypeError`.
2. `ParameterGroup.clone()` calls `self.__class__()` (which wires fresh params) then overwrites the attributes with *un-wired* clones, leaving `self.params` and the attributes pointing at different objects. The clone's attributes don't propagate changes.

Fix both: make the group signal carry the group (`pyqtSignal(object)` emitting `self`), and make `clone()` return a correctly-wired fresh instance.

**Files:**
- Create: `src/varda/common/_tests/conftest.py`
- Create: `src/varda/common/_tests/test_parameter_group_nesting.py`
- Modify: `src/varda/common/parameter.py:40`, `:60-62`, `:93-100`

- [ ] **Step 1: Add headless-Qt conftest for this test dir**

Create `src/varda/common/_tests/conftest.py`:

```python
import os

# Run Qt headless for tests in this directory. Must be set before any QApplication
# is created (pytest-qt creates it lazily when qtbot/qapp is first used).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

- [ ] **Step 2: Write the failing tests**

Create `src/varda/common/_tests/test_parameter_group_nesting.py`:

```python
from varda.common.parameter import ParameterGroup, IntParameter


class _Inner(ParameterGroup):
    value = IntParameter("Value", 0, (0, 10))


class _Outer(ParameterGroup):
    inner = _Inner()
    top = IntParameter("Top", 0, (0, 10))


def test_clone_keeps_attribute_and_params_consistent(qtbot):
    inner = _Inner()
    cloned = inner.clone()
    # the attribute and the params-dict entry must be the SAME object
    assert cloned.value is cloned.params["value"]


def test_leaf_change_emits_group_instance(qtbot):
    outer = _Outer()
    received = []
    outer.sigParameterChanged.connect(lambda g: received.append(g))
    outer.top.set(3)
    assert received and received[-1] is outer


def test_nested_group_change_propagates(qtbot):
    outer = _Outer()
    received = []
    outer.sigParameterChanged.connect(lambda g: received.append(g))
    # set through the attribute (this is what render()/programmatic edits use)
    outer.inner.value.set(7)
    assert received and received[-1] is outer
    assert outer.inner.value.get() == 7
    assert outer.inner.params["value"].get() == 7
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest src/varda/common/_tests/test_parameter_group_nesting.py -v`
Expected: FAIL — `test_clone_keeps_attribute_and_params_consistent` asserts identity mismatch; `test_nested_group_change_propagates` raises `TypeError` from the `lambda _:` wiring (or fails the propagation assertion).

- [ ] **Step 4: Fix the signal declaration**

In `src/varda/common/parameter.py`, change line 40 from:

```python
    sigParameterChanged: pyqtSignal = pyqtSignal()
```

to:

```python
    sigParameterChanged: pyqtSignal = pyqtSignal(object)
```

- [ ] **Step 5: Fix the child-wiring to emit the group**

In `src/varda/common/parameter.py` `ParameterGroup.__init__`, change lines 60-62 from:

```python
                instanceParam.sigParameterChanged.connect(
                    lambda _: self.sigParameterChanged.emit()
                )
```

to:

```python
                instanceParam.sigParameterChanged.connect(
                    lambda _: self.sigParameterChanged.emit(self)
                )
```

- [ ] **Step 6: Fix `clone()` to return a correctly-wired instance**

In `src/varda/common/parameter.py`, replace the whole `clone` method (lines 93-100):

```python
    def clone(self, parent: QObject | None = None) -> ParameterGroup:
        """
        Instantiates a new ParameterGroup based on the current group's state.
        """
        newGroup = self.__class__(parent)
        for name, param in self.params.items():
            setattr(newGroup, name, param.clone(parent=newGroup))
        return newGroup
```

with:

```python
    def clone(self, parent: QObject | None = None) -> ParameterGroup:
        """
        Returns a fresh instance of this group. Subclasses define their parameters as
        class attributes, so ``self.__class__(parent)`` reconstructs them at their
        defaults with the attributes, ``params`` dict, and change-signal wiring all
        consistent. (Used by the parent group's magic to give each instance its own copy.)
        """
        return self.__class__(parent)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest src/varda/common/_tests/test_parameter_group_nesting.py -v`
Expected: PASS (3 passed)

- [ ] **Step 8: Run the full existing suite to check for regressions**

Run: `uv run pytest src/varda/common src/varda/plotting -q`
Expected: PASS — `plot.py`'s `ParameterGroup` consumers are zero-arg slots and stay compatible (Qt allows slots with fewer args than the signal).

- [ ] **Step 9: Commit**

```bash
git add src/varda/common/parameter.py src/varda/common/_tests/conftest.py src/varda/common/_tests/test_parameter_group_nesting.py
git commit -m "fix: make nested ParameterGroups propagate change signals and clone consistently"
```

---

## Task 2: `BandParameter`

A band-index parameter whose widget lists the image's wavelengths. Image-aware via `setImage()` (mirrors `ImageParameter.setProvider`).

**Files:**
- Create: `src/varda/image_rendering/render_parameters.py`
- Create: `src/varda/image_rendering/_tests/conftest.py`
- Create: `src/varda/image_rendering/_tests/test_render_parameters.py`

- [ ] **Step 1: Add headless-Qt conftest**

Create `src/varda/image_rendering/_tests/conftest.py`:

```python
import os

# Run Qt headless for tests in this directory.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

- [ ] **Step 2: Write the failing tests**

Create `src/varda/image_rendering/_tests/test_render_parameters.py`:

```python
import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources import ArrayDataSource
from varda.image_rendering.render_parameters import BandParameter


def make_image(bands: int = 5) -> VardaRaster:
    data = (np.random.rand(8, 9, bands) * 100).astype(np.float32)
    wavelengths = np.array([400.0 + i * 100 for i in range(bands)])
    return VardaRaster(dataSource=ArrayDataSource(data, wavelengths=wavelengths))


def test_band_parameter_set_get(qtbot):
    p = BandParameter("Band", 0)
    p.setImage(make_image(5))
    p.set(3)
    assert p.get() == 3


def test_band_parameter_clamps_stale_value_on_set_image(qtbot):
    p = BandParameter("Band", 0)
    p.value = 99  # stale index from before an image was attached
    p.setImage(make_image(5))
    assert p.get() == 0


def test_band_parameter_clone_preserves_value_and_image(qtbot):
    img = make_image(5)
    p = BandParameter("Band", 0)
    p.setImage(img)
    p.set(2)
    c = p.clone()
    assert c.get() == 2
    assert c.image is img


def test_band_parameter_widget_reflects_value(qtbot):
    img = make_image(4)
    p = BandParameter("Band", 0)
    p.setImage(img)
    w = p.getWidget()
    qtbot.addWidget(w)
    p.set(2)
    assert w.comboBox.currentIndex() == 2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest src/varda/image_rendering/_tests/test_render_parameters.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'varda.image_rendering.render_parameters'`

- [ ] **Step 4: Create the module with `BandParameter`**

Create `src/varda/image_rendering/render_parameters.py`:

```python
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QSignalBlocker, pyqtSlot
from PyQt6.QtWidgets import (
    QComboBox,
    QMessageBox,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from varda.common.entities import VardaRaster
from varda.common.parameter import Parameter, paramLayoutDefault
from varda.common.vec2 import Vec2
from varda.image_rendering.stretch_algorithms import (
    StretchAlgorithm,
    stretchAlgorithmRegistry,
)


class BandParameter(Parameter[int]):
    """Selects a band by index. The widget lists the image's wavelengths.

    Image-aware: ``setImage()`` must be called before building the widget (mirrors
    ``ImageParameter.setProvider``).
    """

    def __init__(
        self,
        name: str,
        default: int = 0,
        description: str | None = None,
        parent=None,
    ):
        super().__init__(name, default, description, parent)
        self.image: VardaRaster | None = None

    def setImage(self, image: VardaRaster) -> None:
        self.image = image
        if self.value >= image.bandCount:
            self.value = 0

    def getWidget(self, parent=None) -> QWidget:
        return self.BandParameterWidget(self, parent)

    def clone(self, parent=None) -> BandParameter:
        new = BandParameter(self.name, self.default, self.description, parent)
        new.value = self.value
        if self.image is not None:
            new.setImage(self.image)
        return new

    class BandParameterWidget(QWidget):
        def __init__(self, param: BandParameter, parent=None):
            super().__init__(parent)
            self.param = param
            self.param.sigParameterChanged.connect(self.onParamChanged)
            assert self.param.image is not None, (
                "BandParameter.setImage() must be called before building its widget"
            )
            self.comboBox = QComboBox(self)
            self.comboBox.addItems([str(w) for w in self.param.image.wavelengths])
            self.comboBox.setCurrentIndex(self.param.get())
            self.comboBox.currentIndexChanged.connect(self._onSelectionChanged)

            layout = paramLayoutDefault()
            layout.addWidget(self.comboBox)
            self.setLayout(layout)

        def _onSelectionChanged(self, index: int) -> None:
            self.param.set(index)

        @pyqtSlot(object)
        def onParamChanged(self, value: int) -> None:
            if self.comboBox.currentIndex() != value:
                with QSignalBlocker(self.comboBox):
                    self.comboBox.setCurrentIndex(value)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest src/varda/image_rendering/_tests/test_render_parameters.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add src/varda/image_rendering/render_parameters.py src/varda/image_rendering/_tests/
git commit -m "feat: add BandParameter render-specific parameter type"
```

---

## Task 3: `ColorMapParameter`

A pyqtgraph `ColorMap`, edited via a `GradientWidget`. The HSV-unsupported guard (currently in the panel) moves here.

**Files:**
- Modify: `src/varda/image_rendering/render_parameters.py` (append class)
- Modify: `src/varda/image_rendering/_tests/test_render_parameters.py` (append tests)

- [ ] **Step 1: Write the failing tests**

Append to `src/varda/image_rendering/_tests/test_render_parameters.py`:

```python
import pyqtgraph as pg

from varda.image_rendering.render_parameters import ColorMapParameter


def test_colormap_default_is_a_colormap(qtbot):
    p = ColorMapParameter("Color Map")
    assert isinstance(p.get(), pg.ColorMap)


def test_colormap_set_get(qtbot):
    p = ColorMapParameter("Color Map")
    new = pg.ColorMap(None, color=[1.0, 0.0])
    p.set(new)
    assert p.get() is new


def test_colormap_clone(qtbot):
    p = ColorMapParameter("Color Map")
    c = p.clone()
    assert isinstance(c, ColorMapParameter)
    assert isinstance(c.get(), pg.ColorMap)


def test_colormap_widget_builds(qtbot):
    p = ColorMapParameter("Color Map")
    w = p.getWidget()
    qtbot.addWidget(w)
    assert w.gradient is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/varda/image_rendering/_tests/test_render_parameters.py -k colormap -v`
Expected: FAIL with `ImportError: cannot import name 'ColorMapParameter'`

- [ ] **Step 3: Implement `ColorMapParameter`**

Append to `src/varda/image_rendering/render_parameters.py`:

```python
class ColorMapParameter(Parameter[pg.ColorMap]):
    """A pyqtgraph ColorMap, edited via a gradient widget."""

    def __init__(
        self,
        name: str,
        default: pg.ColorMap | None = None,
        description: str | None = None,
        parent=None,
    ):
        if default is None:
            default = pg.ColorMap(None, color=[0.0, 1.0])  # simple black -> white map
        super().__init__(name, default, description, parent)

    def getWidget(self, parent=None) -> QWidget:
        return self.ColorMapParameterWidget(self, parent)

    def clone(self, parent=None) -> ColorMapParameter:
        return ColorMapParameter(self.name, self.default, self.description, parent)

    class ColorMapParameterWidget(QWidget):
        def __init__(self, param: ColorMapParameter, parent=None):
            super().__init__(parent)
            self.param = param
            self.param.sigParameterChanged.connect(self.onParamChanged)

            self.gradient = pg.GradientWidget()
            self.gradient.setColorMap(self.param.get())
            self.gradient.sigGradientChanged.connect(self._onGradientChanged)

            layout = paramLayoutDefault()
            layout.addWidget(self.gradient)
            self.setLayout(layout)

        def _onGradientChanged(self, item) -> None:
            try:
                colorMap = item.colorMap()  # raises NotImplementedError for HSV maps
            except NotImplementedError:
                QMessageBox.warning(
                    self,
                    "Unsupported Color Map",
                    "HSV color maps are not supported yet.",
                )
                with QSignalBlocker(self.gradient):
                    self.gradient.setColorMap(self.param.get())  # revert
                return
            self.param.set(colorMap)

        @pyqtSlot(object)
        def onParamChanged(self, colorMap: pg.ColorMap) -> None:
            with QSignalBlocker(self.gradient):
                self.gradient.setColorMap(colorMap)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/varda/image_rendering/_tests/test_render_parameters.py -k colormap -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/varda/image_rendering/render_parameters.py src/varda/image_rendering/_tests/test_render_parameters.py
git commit -m "feat: add ColorMapParameter render-specific parameter type"
```

---

## Task 4: `StretchParameter`

Selects the active stretch algorithm from the registry. The value is the active `StretchAlgorithm` instance; one instance of every registered algorithm is built up-front so each option keeps its own sub-parameters. `getWidget()` returns a self-contained combo + stacked sub-form.

**Files:**
- Modify: `src/varda/image_rendering/render_parameters.py` (append class)
- Modify: `src/varda/image_rendering/_tests/test_render_parameters.py` (append tests)

- [ ] **Step 1: Write the failing tests**

Append to `src/varda/image_rendering/_tests/test_render_parameters.py`:

```python
from varda.common.vec2 import Vec2
from varda.image_rendering.render_parameters import StretchParameter


def test_stretch_default_is_auto(qtbot):
    p = StretchParameter("Stretch")
    assert p.nameOf(p.current) == "Min-Max (Auto Full Range)"


def test_stretch_select_by_name(qtbot):
    p = StretchParameter("Stretch")
    p.selectByName("Min-Max (Manual)")
    assert p.nameOf(p.current) == "Min-Max (Manual)"
    assert p.current is p.option("Min-Max (Manual)")


def test_stretch_subparam_change_propagates(qtbot):
    p = StretchParameter("Stretch")
    received = []
    p.sigParameterChanged.connect(lambda v: received.append(v))
    p.option("Min-Max (Manual)").config.redStretch.set(Vec2(0.1, 0.9))
    assert len(received) >= 1


def test_stretch_clone_preserves_selection_with_independent_instances(qtbot):
    p = StretchParameter("Stretch")
    p.selectByName("Linear Percentile")
    c = p.clone()
    assert c.nameOf(c.current) == "Linear Percentile"
    assert c.current is not p.current


def test_stretch_widget_combo_drives_selection(qtbot):
    p = StretchParameter("Stretch")
    w = p.getWidget()
    qtbot.addWidget(w)
    manual_index = p.optionNames.index("Min-Max (Manual)")
    w.comboBox.setCurrentIndex(manual_index)
    assert p.nameOf(p.current) == "Min-Max (Manual)"
    assert w.stack.currentIndex() == manual_index
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/varda/image_rendering/_tests/test_render_parameters.py -k stretch -v`
Expected: FAIL with `ImportError: cannot import name 'StretchParameter'`

- [ ] **Step 3: Implement `StretchParameter`**

Append to `src/varda/image_rendering/render_parameters.py`:

```python
class StretchParameter(Parameter[StretchAlgorithm]):
    """Selects the active stretch algorithm from the registry.

    The value is the active ``StretchAlgorithm`` instance. One instance of every
    registered algorithm is built up-front and kept, so each option retains its own
    sub-parameters. The widget is a self-contained combo + stacked sub-form.
    """

    DEFAULT_NAME = "Min-Max (Auto Full Range)"
    MANUAL_NAME = "Min-Max (Manual)"

    def __init__(self, name: str, description: str | None = None, parent=None):
        self._instances: dict[str, StretchAlgorithm] = {
            n: cls() for n, cls in stretchAlgorithmRegistry.items()
        }
        default = self._instances.get(self.DEFAULT_NAME) or next(
            iter(self._instances.values())
        )
        super().__init__(name, default, description, parent)
        for instance in self._instances.values():
            instance.parameters().sigParameterChanged.connect(self._onSubParamChanged)

    def _onSubParamChanged(self, *args) -> None:
        # a sub-parameter of one of the algorithms changed; treat it as a settings change
        self.sigParameterChanged.emit(self.value)

    @property
    def current(self) -> StretchAlgorithm:
        return self.value

    @property
    def optionNames(self) -> list[str]:
        return list(self._instances.keys())

    def option(self, name: str) -> StretchAlgorithm:
        return self._instances[name]

    def nameOf(self, instance: StretchAlgorithm) -> str:
        for n, inst in self._instances.items():
            if inst is instance:
                return n
        raise ValueError("instance is not one of this parameter's algorithms")

    def selectByName(self, name: str) -> None:
        self.set(self._instances[name])

    def getWidget(self, parent=None) -> QWidget:
        return self.StretchParameterWidget(self, parent)

    def clone(self, parent=None) -> StretchParameter:
        new = StretchParameter(self.name, self.description, parent)
        new.selectByName(self.nameOf(self.value))
        return new

    class StretchParameterWidget(QWidget):
        def __init__(self, param: StretchParameter, parent=None):
            super().__init__(parent)
            self.param = param
            self.param.sigParameterChanged.connect(self.onParamChanged)

            self.comboBox = QComboBox(self)
            self.comboBox.addItems(self.param.optionNames)

            self.stack = QStackedLayout()
            self.stack.setAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
            )
            for name in self.param.optionNames:
                self.stack.addWidget(self.param.option(name).parameters().createWidget())

            self.comboBox.currentIndexChanged.connect(self._onComboChanged)

            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(self.comboBox)
            layout.addLayout(self.stack)
            self.setLayout(layout)

            self._syncToParam()

        def _onComboChanged(self, index: int) -> None:
            self.param.selectByName(self.param.optionNames[index])
            self.stack.setCurrentIndex(index)

        def _syncToParam(self) -> None:
            index = self.param.optionNames.index(self.param.nameOf(self.param.current))
            with QSignalBlocker(self.comboBox):
                self.comboBox.setCurrentIndex(index)
            self.stack.setCurrentIndex(index)

        @pyqtSlot(object)
        def onParamChanged(self, value) -> None:
            self._syncToParam()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/varda/image_rendering/_tests/test_render_parameters.py -k stretch -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Run the whole render-params file**

Run: `uv run pytest src/varda/image_rendering/_tests/test_render_parameters.py -v`
Expected: PASS (13 passed)

- [ ] **Step 6: Commit**

```bash
git add src/varda/image_rendering/render_parameters.py src/varda/image_rendering/_tests/test_render_parameters.py
git commit -m "feat: add StretchParameter (registry selection + per-option sub-params)"
```

---

## Task 5: `RendererSettings` as a `ParameterGroup`

Replace the `RendererSettings` dataclass with a `ParameterGroup`, plus the `RenderMode` enum and the `RgbBandGroup`/`MonoViewGroup` sub-groups. (This task only changes the data model; `ImageRenderer`/`render()` are rewritten in Task 6, so the file will not fully run until then — that's expected.)

**Files:**
- Modify: `src/varda/image_rendering/image_renderer.py:1-52` (imports + replace `RendererSettings` dataclass)
- Create: `src/varda/image_rendering/_tests/test_image_renderer.py`

- [ ] **Step 1: Write the failing tests**

Create `src/varda/image_rendering/_tests/test_image_renderer.py`:

```python
import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources import ArrayDataSource
from varda.image_rendering.image_renderer import (
    RenderMode,
    RendererSettings,
)


def make_image(bands: int = 5) -> VardaRaster:
    data = (np.random.rand(8, 9, bands) * 100).astype(np.float32)
    wavelengths = np.array([400.0 + i * 100 for i in range(bands)])
    return VardaRaster(dataSource=ArrayDataSource(data, wavelengths=wavelengths))


def test_settings_defaults(qtbot):
    img = make_image(5)
    s = RendererSettings(img)
    assert s.image is img
    assert s.mode.get() == RenderMode.MONO
    assert s.opacity.get() == 1.0
    # bands seeded from image.defaultBands ([0, 1, 2])
    assert s.rgb.red.get() == 0
    assert s.rgb.green.get() == 1
    assert s.rgb.blue.get() == 2
    assert s.mono.band.get() == 0


def test_settings_band_params_are_image_aware(qtbot):
    img = make_image(5)
    s = RendererSettings(img)
    assert s.rgb.red.image is img
    assert s.mono.band.image is img


def test_settings_change_emits_group(qtbot):
    s = RendererSettings(make_image(5))
    received = []
    s.sigParameterChanged.connect(lambda g: received.append(g))
    s.rgb.red.set(3)
    assert received and received[-1] is s


def test_settings_stretch_default_is_auto(qtbot):
    s = RendererSettings(make_image(5))
    assert s.stretch.nameOf(s.stretch.current) == "Min-Max (Auto Full Range)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/varda/image_rendering/_tests/test_image_renderer.py -v`
Expected: FAIL with `ImportError: cannot import name 'RenderMode'`

- [ ] **Step 3: Replace imports and the `RendererSettings` dataclass**

In `src/varda/image_rendering/image_renderer.py`, replace lines 1-52 (everything from the top imports through the end of the `RendererSettings` dataclass, i.e. up to and including its `__repr__`) with:

```python
import sys
from enum import Enum, auto
from typing import Optional

from PyQt6.QtCore import pyqtSignal, QObject, Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QStackedLayout,
    QApplication,
)
import numpy as np

from varda.common.parameter import (
    ParameterGroup,
    EnumParameter,
    FloatParameter,
    ParameterGroupWidget,
)
from varda.common.entities import VardaRaster
from varda.common.vec2 import Vec2
from varda.utilities import debug
from varda.image_rendering.render_parameters import (
    BandParameter,
    ColorMapParameter,
    StretchParameter,
)


class RenderMode(Enum):
    MONO = auto()
    RGB = auto()


class RgbBandGroup(ParameterGroup):
    red = BandParameter("Red Band")
    green = BandParameter("Green Band")
    blue = BandParameter("Blue Band")


class MonoViewGroup(ParameterGroup):
    band = BandParameter("Band")
    colorMap = ColorMapParameter("Color Map")


class RendererSettings(ParameterGroup):
    mode = EnumParameter("Mode", RenderMode, RenderMode.MONO)
    rgb = RgbBandGroup()
    mono = MonoViewGroup()
    stretch = StretchParameter("Stretch Algorithm")
    opacity = FloatParameter(
        "Opacity", 1.0, (0.0, 1.0), "%", "Opacity of the rendered image."
    )

    def __init__(self, image: VardaRaster, parent: QObject | None = None):
        super().__init__(parent)
        self.image = image
        for bandParam in (self.rgb.red, self.rgb.green, self.rgb.blue, self.mono.band):
            bandParam.setImage(image)
        # seed band selections from the image's default bands
        defaultBands = image.defaultBands
        self.rgb.red.value = int(defaultBands[0])
        self.rgb.green.value = int(defaultBands[1])
        self.rgb.blue.value = int(defaultBands[2])
        self.mono.band.value = int(defaultBands[0])
```

Note: `from typing import Optional` is **kept** because the still-present old `ImageRenderer` (replaced in Task 6) has `Optional[RendererSettings]` in its signature, which is evaluated at import time. The old `from dataclasses import dataclass`, the `QComboBox`/`QButtonGroup`/`QRadioButton`/`QHBoxLayout`/`QMessageBox` imports, `import pyqtgraph as pg`, `from pyqtgraph import ColorMap`, and the `from varda.image_rendering.stretch_algorithms import ...` import are dropped here — they were only used inside method bodies (`RendererSettings.new`, the old panel `__init__`) that are not executed at import time or by this task's tests, so the module still imports. (`Optional` becomes unused after Task 6 replaces `ImageRenderer`; Task 9's `ruff` pass removes it.)

- [ ] **Step 4: Run the data-model tests**

Run: `uv run pytest src/varda/image_rendering/_tests/test_image_renderer.py -v`
Expected: PASS (4 passed). (`ImageRenderer` is rewritten next; these tests only touch `RendererSettings`/`RenderMode`.)

- [ ] **Step 5: Commit**

```bash
git add src/varda/image_rendering/image_renderer.py src/varda/image_rendering/_tests/test_image_renderer.py
git commit -m "feat: model RendererSettings as a ParameterGroup"
```

---

## Task 6: Rewrite `ImageRenderer` (param-based render, change propagation, convenience methods)

`ImageRenderer` now owns a stable settings object, refreshes on any param change, reads from params in `render()`, and exposes `setManualStretch` / `setStretchMinMax`. The stubbed `updateSettings`/`setMinMaxValues`/`manuallySetStretch` are removed.

**Files:**
- Modify: `src/varda/image_rendering/image_renderer.py` (the `ImageRenderer` class)
- Modify: `src/varda/image_rendering/_tests/test_image_renderer.py` (append tests)

- [ ] **Step 1: Write the failing tests**

Append to `src/varda/image_rendering/_tests/test_image_renderer.py`:

```python
from varda.common.vec2 import Vec2
from varda.image_rendering.image_renderer import ImageRenderer


def make_renderer(bands: int = 5) -> ImageRenderer:
    return ImageRenderer(image=make_image(bands))


def test_render_returns_rgba(qtbot):
    out = make_renderer().render()
    assert out.ndim == 3 and out.shape[2] == 4


def test_render_is_cached(qtbot):
    r = make_renderer()
    r.render()
    assert r.cachedRender is not None


def test_param_change_invalidates_cache_and_emits_refresh(qtbot):
    r = make_renderer()
    r.render()
    with qtbot.waitSignal(r.sigShouldRefresh, timeout=1000):
        r.settings.opacity.set(0.5)
    assert r.cachedRender is None


def test_mode_switch_changes_render_path(qtbot):
    r = make_renderer()
    r.settings.mode.set(RenderMode.RGB)
    out = r.render()
    assert out.shape[2] == 4


def test_setManualStretch_activates_manual_on_all_channels(qtbot):
    r = make_renderer()
    r.setManualStretch(10.0, 50.0)
    stretch = r.settings.stretch
    assert stretch.nameOf(stretch.current) == "Min-Max (Manual)"
    assert stretch.current.config.redStretch.get() == Vec2(10.0, 50.0)
    assert stretch.current.config.greenStretch.get() == Vec2(10.0, 50.0)
    assert stretch.current.config.blueStretch.get() == Vec2(10.0, 50.0)


def test_setStretchMinMax_seeds_other_channels_and_sets_target(qtbot):
    r = make_renderer()
    r.render()  # auto stretch computes its min/max for seeding
    r.setStretchMinMax(0, 5.0, 7.0)
    manual = r.settings.stretch.option("Min-Max (Manual)")
    assert r.settings.stretch.current is manual
    assert manual.config.redStretch.get() == Vec2(5.0, 7.0)
    # green/blue were seeded from the auto stretch (not left at the Vec2(0, 1) default)
    assert isinstance(manual.config.greenStretch.get(), Vec2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/varda/image_rendering/_tests/test_image_renderer.py -v`
Expected: FAIL — `render()` still reads dataclass-style `.settings.mode`/`.bands`/etc. and the convenience methods don't exist yet.

- [ ] **Step 3: Replace the `ImageRenderer` class**

In `src/varda/image_rendering/image_renderer.py`, replace the entire `ImageRenderer` class (from `class ImageRenderer(QObject):` through its last method `getSettingsPanel`) with:

```python
class ImageRenderer(QObject):
    sigShouldRefresh: pyqtSignal = pyqtSignal()

    def __init__(
        self,
        image: VardaRaster | None = None,
        settings: RendererSettings | None = None,
    ):
        super().__init__()
        if settings is None and image is None:
            raise ValueError("Either image or settings must be provided.")
        self.settings = settings if settings is not None else RendererSettings(image)
        self.image = self.settings.image
        self.cachedRender = None
        self._stretchedData = None  # latest render post-stretch but pre-colormap
        self._rawBandData = None  # extracted band data with no processing applied
        self.settings.sigParameterChanged.connect(self._onSettingsChanged)

    def _onSettingsChanged(self, *args) -> None:
        # any parameter (UI or programmatic) changed: drop caches and request a refresh
        self.cachedRender = None
        self._stretchedData = None
        self.sigShouldRefresh.emit()

    def render(self):
        """
        Render the image with the current band and stretch settings.
        Returns: numpy ndarray with shape (height, width, 4) representing an RGBA image.
        """
        if self.cachedRender is not None:
            return self.cachedRender
        if self.image is None or self.settings is None:
            raise ValueError("Image and settings must be set before rendering.")

        mode = self.settings.mode.get()
        if mode == RenderMode.MONO:
            # maintain 3D shape so stretch algorithms don't branch on 2d/3d
            data = self.image.getBands([int(self.settings.mono.band.get())])
        else:
            data = self.image.getBands(
                [
                    int(self.settings.rgb.red.get()),
                    int(self.settings.rgb.green.get()),
                    int(self.settings.rgb.blue.get()),
                ]
            )
        self._rawBandData = data

        if np.ma.isMaskedArray(data):
            data = data.filled(np.nan)

        data = self.settings.stretch.current.apply(data)
        self._stretchedData = data
        data[np.isnan(data)] = 0

        if mode == RenderMode.MONO:
            data = np.squeeze(data)  # back to 2D because ColorMap expects it
            lut = self.settings.mono.colorMap.get().getLookupTable(
                0, 1, 256, alpha=False
            )
            data = lut[(data * 255).astype(np.uint8)]
        else:
            data = (data * 255).astype(np.uint8)

        alpha = np.full(
            (data.shape[0], data.shape[1], 1),
            int(self.settings.opacity.get() * 255),
            dtype=np.uint8,
        )
        rgba = np.concatenate((data, alpha), axis=2)
        self.cachedRender = rgba
        return rgba

    def getStretchedData(self) -> np.ndarray:
        if self._stretchedData is None:
            self.render()
        assert self._stretchedData is not None
        return self._stretchedData

    def getRawBandData(self) -> np.ndarray:
        if self._rawBandData is None:
            self.render()
        assert self._rawBandData is not None
        return self._rawBandData

    def getMinMaxValues(self):
        if self.cachedRender is None:
            self.render()
        return self.settings.stretch.current.minMaxVals()

    def setManualStretch(self, lo: float, hi: float) -> None:
        """Switch to the manual stretch and set every channel to [lo, hi]."""
        manual = self.settings.stretch.option(StretchParameter.MANUAL_NAME)
        value = Vec2(float(lo), float(hi))
        manual.config.redStretch.set(value)
        manual.config.greenStretch.set(value)
        manual.config.blueStretch.set(value)
        self.settings.stretch.selectByName(StretchParameter.MANUAL_NAME)

    def setStretchMinMax(self, channel: int, lo: float, hi: float) -> None:
        """Set one channel's manual min/max (0=red, 1=green, 2=blue).

        When switching into the manual stretch, seed all channels from the current
        stretch's computed min/max so the other channels don't jump.
        """
        stretch = self.settings.stretch
        manual = stretch.option(StretchParameter.MANUAL_NAME)
        channelParams = [
            manual.config.redStretch,
            manual.config.greenStretch,
            manual.config.blueStretch,
        ]
        if stretch.current is not manual:
            self.render()  # ensure the current stretch has computed its min/max
            seed = stretch.current.minMaxVals()
            if seed is not None:
                mins = np.resize(np.atleast_1d(np.asarray(seed[0], dtype=float)).ravel(), 3)
                maxs = np.resize(np.atleast_1d(np.asarray(seed[1], dtype=float)).ravel(), 3)
                for i, param in enumerate(channelParams):
                    param.set(Vec2(float(mins[i]), float(maxs[i])))
            stretch.selectByName(StretchParameter.MANUAL_NAME)
        channelParams[channel].set(Vec2(float(lo), float(hi)))

    def getSettingsPanel(self) -> "RendererSettingsPanel":
        return RendererSettingsPanel(self.settings)
```

(Leave the `getComboBox()` helper in place for now — the old `RendererSettingsPanel` still references it until Task 7, which removes both together.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/varda/image_rendering/_tests/test_image_renderer.py -v`
Expected: PASS (11 passed). The old `RendererSettingsPanel` is still defined at this point, but these tests never instantiate it and its class body references no dropped names, so the module imports fine. (Its `__init__` would fail if run — Task 7 rewrites it next.)

- [ ] **Step 5: Commit**

```bash
git add src/varda/image_rendering/image_renderer.py src/varda/image_rendering/_tests/test_image_renderer.py
git commit -m "feat: render from parameters; add manual-stretch convenience methods"
```

---

## Task 7: Rewrite `RendererSettingsPanel`

The panel composes parameter widgets plus one mode-driven `QStackedLayout` (RGB band group ↔ mono band+colormap group). It edits the live parameters directly — no dataclass mutation, no `sigSettingsChanged`.

**Files:**
- Modify: `src/varda/image_rendering/image_renderer.py` (the `RendererSettingsPanel` class)

- [ ] **Step 1: Replace the `getComboBox` helper and the `RendererSettingsPanel` class**

In `src/varda/image_rendering/image_renderer.py`, delete the `getComboBox()` helper function and replace the entire `RendererSettingsPanel` class with:

```python
class RendererSettingsPanel(QWidget):
    """Panel for adjusting render settings, generated from the settings' parameters."""

    def __init__(self, settings: RendererSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Render Settings")
        self.settings = settings

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.setSpacing(2)

        # Mode
        layout.addWidget(QLabel("Mode:"))
        layout.addWidget(settings.mode.getWidget(self))

        # Band / colormap area, swapped by the mode parameter
        self.bandStack = QStackedLayout()
        self.bandStack.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._rgbIndex = self.bandStack.addWidget(settings.rgb.createWidget())
        self._monoIndex = self.bandStack.addWidget(settings.mono.createWidget())
        layout.addLayout(self.bandStack)
        self._syncBandStack()
        settings.mode.sigParameterChanged.connect(self._syncBandStack)

        # Stretch (self-contained combo + stacked sub-form)
        layout.addWidget(QLabel("Stretch Algorithm:"))
        layout.addWidget(settings.stretch.getWidget(self))

        # Opacity (labeled form row)
        layout.addWidget(ParameterGroupWidget([settings.opacity], self))

        self.setLayout(layout)

    def _syncBandStack(self, *args) -> None:
        isRgb = self.settings.mode.get() == RenderMode.RGB
        self.bandStack.setCurrentIndex(self._rgbIndex if isRgb else self._monoIndex)
```

- [ ] **Step 2: Verify the module imports and renderer tests pass**

Run: `uv run pytest src/varda/image_rendering/_tests/test_image_renderer.py -v`
Expected: PASS (11 passed)

- [ ] **Step 3: Manually verify the panel renders and is interactive**

Run: `uv run python -m varda.image_rendering.image_renderer`
Expected: A "Image Render Settings" window opens with: a Mode combo (Mono/Rgb), a band/colormap area that swaps when you change Mode, a Stretch Algorithm combo whose sub-parameters swap with selection, and an Opacity row. Changing Mode to "Rgb" shows three band combos; "Mono" shows one band combo + a gradient. Close the window to exit.

- [ ] **Step 4: Commit**

```bash
git add src/varda/image_rendering/image_renderer.py
git commit -m "feat: generate RendererSettingsPanel from the parameter system"
```

---

## Task 8: Histogram — enum mode reads + region-drag → stretch

Update `new_histogram_view.py` to read `mode` as an enum, make the region items movable, and wire `sigRegionChangeFinished` to `ImageRenderer.setStretchMinMax`. Regions are kept (not nuked by `clear()`) and resynced (signal-blocked) on each refresh.

**Files:**
- Modify: `src/varda/image_rendering/new_histogram_view.py`

- [ ] **Step 1: Update imports**

In `src/varda/image_rendering/new_histogram_view.py`, change the local import block (lines 21-25) to add `RenderMode`:

```python
from varda.image_rendering.image_renderer import (
    ImageRenderer,
    RendererSettings,
    RenderMode,
    RendererSettingsPanel,
)
```

- [ ] **Step 2: Initialize region attributes in `__init__`**

In `NewHistogramView.__init__`, ensure the region attributes are initialized before `self._updateHistogram()` (replace the existing `self.rRegion = None` / `self.gRegion = None` / `self.bRegion = None` / `self.monoRegion` lines with this consolidated set, keeping them above the `self._updateHistogram()` call):

```python
        self.rRegion: pg.LinearRegionItem | None = None
        self.gRegion: pg.LinearRegionItem | None = None
        self.bRegion: pg.LinearRegionItem | None = None
        self.monoRegion: pg.LinearRegionItem | None = None
```

- [ ] **Step 3: Replace `_updateHistogram` and add region helpers**

Replace the entire `_updateHistogram` method with the following methods:

```python
    def _updateHistogram(self):
        renderer = self.imageRenderer
        mode = renderer.settings.mode.get()
        self.layout().setCurrentIndex(1 if mode == RenderMode.MONO else 0)

        # clear curves (this also removes region items; they are re-added below)
        self.rPlot.clear()
        self.gPlot.clear()
        self.bPlot.clear()
        self.monoPlot.clear()

        minMaxVals = renderer.getMinMaxValues()
        if minMaxVals is not None:
            data = renderer.getRawBandData()
        else:
            data = renderer.getStretchedData()

        def plotHistogram(arr, plotWidget, pen, brush):
            if arr.size:
                vmin, vmax = np.nanmin(arr), np.nanmax(arr)
                if vmin == vmax:
                    vmin -= 0.5
                    vmax += 0.5
                y, x = np.histogram(arr, bins=256, range=(vmin, vmax))
                plotWidget.plot(x[1:], y, pen=pen, fillLevel=0, brush=brush)

        if mode == RenderMode.MONO:
            plotHistogram(data.ravel(), self.monoPlot, "w", (255, 255, 255, 50))
            self._syncMonoRegion(minMaxVals)
        else:
            plotHistogram(data[:, :, 0].ravel(), self.rPlot, "r", (255, 0, 0, 50))
            plotHistogram(data[:, :, 1].ravel(), self.gPlot, "g", (0, 255, 0, 50))
            plotHistogram(data[:, :, 2].ravel(), self.bPlot, "b", (0, 0, 255, 50))
            self._syncRgbRegions(minMaxVals)

    def _syncMonoRegion(self, minMaxVals):
        if minMaxVals is None:
            self.monoRegion = None
            return
        lo = float(np.ravel(minMaxVals[0])[0])
        hi = float(np.ravel(minMaxVals[1])[0])
        if self.monoRegion is None:
            self.monoRegion = pg.LinearRegionItem(
                values=(lo, hi), pen="w", brush=(0, 0, 0, 0), movable=True
            )
            self.monoRegion.sigRegionChangeFinished.connect(self._onMonoRegionChanged)
        else:
            with QSignalBlocker(self.monoRegion):
                self.monoRegion.setRegion((lo, hi))
        self.monoPlot.addItem(self.monoRegion)

    def _onMonoRegionChanged(self):
        lo, hi = self.monoRegion.getRegion()
        self.imageRenderer.setStretchMinMax(0, lo, hi)

    def _syncRgbRegions(self, minMaxVals):
        if minMaxVals is None:
            self.rRegion = self.gRegion = self.bRegion = None
            return
        mins = np.ravel(minMaxVals[0])
        maxs = np.ravel(minMaxVals[1])
        specs = (
            ("rRegion", self.rPlot, "r", 0, self._onRRegionChanged),
            ("gRegion", self.gPlot, "g", 1, self._onGRegionChanged),
            ("bRegion", self.bPlot, "b", 2, self._onBRegionChanged),
        )
        for attr, plot, pen, channel, handler in specs:
            lo, hi = float(mins[channel]), float(maxs[channel])
            region = getattr(self, attr)
            if region is None:
                region = pg.LinearRegionItem(
                    values=(lo, hi), pen=pen, brush=(0, 0, 0, 0), movable=True
                )
                region.sigRegionChangeFinished.connect(handler)
                setattr(self, attr, region)
            else:
                with QSignalBlocker(region):
                    region.setRegion((lo, hi))
            plot.addItem(region)

    def _onRRegionChanged(self):
        lo, hi = self.rRegion.getRegion()
        self.imageRenderer.setStretchMinMax(0, lo, hi)

    def _onGRegionChanged(self):
        lo, hi = self.gRegion.getRegion()
        self.imageRenderer.setStretchMinMax(1, lo, hi)

    def _onBRegionChanged(self):
        lo, hi = self.bRegion.getRegion()
        self.imageRenderer.setStretchMinMax(2, lo, hi)
```

- [ ] **Step 4: Update the `__main__` block**

Replace the `if __name__ == "__main__":` block at the bottom with:

```python
if __name__ == "__main__":
    q_app = pg.mkQApp()
    image = varda.utilities.debug.generate_random_image((100, 100, 10), (10, 10, 10))
    renderSettings = RendererSettings(image)
    renderSettings.mode.set(RenderMode.RGB)
    renderer = ImageRenderer(image, renderSettings)
    settingsPanel = renderer.getSettingsPanel()

    view = NewHistogramView(renderer)
    renderer.sigShouldRefresh.connect(view._updateHistogram)
    view.show()
    settingsPanel.show()
    q_app.exec()
```

- [ ] **Step 5: Manually verify histogram drag drives the stretch**

Run: `uv run python -m varda.image_rendering.new_histogram_view`
Expected: A histogram window (R/G/B tabs in RGB mode) and the settings panel open. Dragging a region's edge on a channel and releasing switches the Stretch Algorithm combo to "Min-Max (Manual)" and the histogram redraws against the raw band data with the region reflecting your selection. Switching Mode to "Mono" in the settings panel shows a single histogram with one draggable region. Close windows to exit.

- [ ] **Step 6: Commit**

```bash
git add src/varda/image_rendering/new_histogram_view.py
git commit -m "feat: drag histogram regions to drive the manual stretch min/max"
```

---

## Task 9: Integration sweep — consumers, types, format, full suite

Confirm no consumer still uses the removed API, then run type checking, formatting, the full test suite, and a smoke launch of the real workspace.

**Files:**
- Modify: `src/varda/image_rendering/stretch_algorithms.py` (revert obsolete WIP stubs).
- Modify (only if grep finds hits): any file still referencing removed symbols.

- [ ] **Step 0: Revert the obsolete `setMinMaxVals` WIP stubs in `stretch_algorithms.py`**

The working tree has pre-existing WIP additions to `stretch_algorithms.py` (a `setMinMaxVals` stub on `StretchAlgorithm` and a broken `self.min` `setMinMaxVals` on `LinearPercentileStretch`) — the only uncommitted changes to that file. The migration's `StretchParameter` + `ImageRenderer` convenience methods supersede them and nothing calls `setMinMaxVals`. Revert the file to its committed state:

Run: `git checkout HEAD -- src/varda/image_rendering/stretch_algorithms.py`
Then confirm it's clean: `git diff --stat src/varda/image_rendering/stretch_algorithms.py` (expected: no output).

- [ ] **Step 1: Grep for removed/changed API usage**

Run:

```bash
cd /Users/jesse/PycharmProjects/Varda
grep -rn "RendererSettings.new\|\.updateSettings\|setMinMaxValues\|manuallySetStretch\|settings\.bands\|settings\.colorMap\|settings\.opacity\b\|settings\.mode ==\|settings\.stretch =" src --include="*.py" | grep -v "_tests"
```

Expected: no output. If any hit appears (outside the files this plan already rewrote), fix it to the new API:
- `RendererSettings.new(img)` → `RendererSettings(img)`
- `settings.mode == "mono"` → `settings.mode.get() == RenderMode.MONO`
- `settings.bands = ...` → set `settings.rgb.red/green/blue` (or `settings.mono.band`) values
- `renderer.updateSettings(s)` → assign params on `renderer.settings` directly (no replacement needed)

- [ ] **Step 2: Type-check the changed modules**

Run: `uv run ty check src/varda/common/parameter.py src/varda/image_rendering/render_parameters.py src/varda/image_rendering/image_renderer.py src/varda/image_rendering/new_histogram_view.py`
Expected: no errors. Fix any type issues reported (do not introduce `Any`; per project style, omit a hint rather than use `Any`).

- [ ] **Step 3: Format**

Run: `uv run ruff format src/varda/common/parameter.py src/varda/image_rendering/`
Then: `uv run ruff check src/varda/image_rendering/render_parameters.py src/varda/image_rendering/image_renderer.py src/varda/image_rendering/new_histogram_view.py`
Expected: formatting applied; `ruff check` reports no errors (fix any unused-import warnings from the import changes).

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest src/varda -q`
Expected: PASS (all green, including the pre-existing suites).

- [ ] **Step 5: Smoke-launch the real workspace**

Run: `uv run python -m varda.main`
Expected: The app launches. Open an image and a General Image Analysis workspace; the "Render Settings" dock shows the parameter-generated panel; changing Mode/Stretch/Opacity updates the raster view and histogram. Dragging a histogram region updates the image. Close the app.

- [ ] **Step 6: Commit integration fixes (explicit paths only)**

Do **not** use `git add -A` — the untracked `src/_experiments/vispy_varda_raster_viewer.py` is the user's experiment and must stay uncommitted. Stage only the files actually changed in this task (the `stretch_algorithms.py` revert is a working-tree change to a tracked file, so `git add` stages the reverted/clean content; include any files touched in Step 1):

```bash
git add src/varda/image_rendering/stretch_algorithms.py
# add any other files changed by Step 1 fixes, e.g.:
# git add src/varda/image_rendering/image_renderer.py
git commit -m "chore: drop obsolete setMinMaxVals stubs; integration fixes for renderer parameter migration"
```

(If Step 0's revert plus Steps 1–5 produced no staged changes, skip this commit.)

---

## Self-Review Notes

- **Spec coverage:** §1 data model → Task 5; §2 new param types → Tasks 2–4; §3 change propagation + nested-group fix → Tasks 1 & 6; §4 panel → Task 7; §5 histogram drag → Task 8; §6 programmatic API → Task 6; §7 consumer updates → Tasks 8 & 9.
- **Cross-task type consistency:** `StretchParameter.MANUAL_NAME`/`DEFAULT_NAME`, `option()`, `selectByName()`, `nameOf()`, `current`, `optionNames` defined in Task 4 and used in Tasks 6/8; `RenderMode` defined in Task 5 and used in Tasks 6/7/8; `setStretchMinMax(channel, lo, hi)` defined in Task 6 and called in Task 8; manual stretch's `config.redStretch/greenStretch/blueStretch` (`Vec2`) used consistently in Tasks 4/6.
- **Known limitation (documented in spec §6):** the manual stretch's spinbox range stays at the `Vec2Parameter` default (±100000); per-image range widening is deferred.
