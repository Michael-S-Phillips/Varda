# ROI Ratioing (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user mark one ROI as the ratio "denominator" and plot any ROI's mean spectrum divided by that denominator's mean spectrum, via a right-click menu on the ROI table.

**Architecture:** A Qt-free pure function does the division; `ROICollection` gains a `getRatioSpectrum` method built on its existing mean-spectrum path. Plotting + denominator state move out of the workspaces and into `ROIManagerWidget` (the workspace just hands it the spectral image and the plot widget). The ROI table gets a plain row context menu (Plot Spectrum / Plot Ratio Spectrum / Set as Denominator / Clear Denominator) and a bold "÷" badge marking the denominator row.

**Tech Stack:** Python 3.13, PyQt6, NumPy, pytest + pytest-qt (`qtbot`), `uv` for running, ruff for formatting, ty for type checking.

**Design reference:** `docs/superpowers/specs/2026-06-07-roi-ratioing-and-templating-design.md` (Phase 1 sections).

**Testing notes:**
- Run tests with `uv run pytest`. Qt tests use the `qtbot` fixture; the repo's `_tests/conftest.py` already forces `QT_QPA_PLATFORM=offscreen`, so no display is needed.
- Logic lives in Qt-free units (`ratio.py`, `ROICollection.getRatioSpectrum`) so it is directly unit-tested. Widget/model behavior is tested by building menus/models under `qtbot` and triggering actions — never by popping modal dialogs.

---

## File Structure

- **Create** `src/varda/rois/ratio.py` — pure `computeRatioSpectrum` (Qt-free).
- **Create** `src/varda/rois/_tests/test_ratio.py` — tests for the pure function.
- **Modify** `src/varda/rois/roi_collection.py` — add `getRatioSpectrum`.
- **Modify** `src/varda/rois/_tests/test_roi_collection.py` — add a split-image helper + ratio tests.
- **Modify** `src/varda/rois/roi_table_model.py` — denominator state + bold "÷" badge.
- **Create** `src/varda/rois/_tests/test_roi_table_model.py` — badge/state tests.
- **Modify** `src/varda/rois/roi_table_view.py` — row context menu + action signals.
- **Create** `src/varda/rois/_tests/test_roi_table_view.py` — menu/signal tests.
- **Modify** `src/varda/rois/roi_manager_widget.py` — new constructor (image + plot widget), `plotSpectrum`/`plotRatioSpectrum`/`setDenominator`, wire the context menu.
- **Create** `src/varda/rois/_tests/test_roi_manager_widget.py` — manager behavior tests.
- **Modify** `src/varda/workspaces/general_image_analysis/general_image_analysis.py` — pass image + plot widget to the manager; delete `_onPlotRequested`.
- **Modify** `src/varda/workspaces/dual_image_workspace/dual_image_workspace.py` — same, using `image1` as the spectral image.

---

### Task 1: Pure `computeRatioSpectrum` function

**Files:**
- Create: `src/varda/rois/ratio.py`
- Test: `src/varda/rois/_tests/test_ratio.py`

- [ ] **Step 1: Write the failing tests**

Create `src/varda/rois/_tests/test_ratio.py`:

```python
"""Tests for the pure spectral ratio function."""

import numpy as np

from varda.rois.ratio import computeRatioSpectrum


def test_basic_division():
    num = np.array([2.0, 4.0, 6.0])
    den = np.array([1.0, 2.0, 3.0])
    np.testing.assert_array_almost_equal(
        computeRatioSpectrum(num, den), [2.0, 2.0, 2.0]
    )


def test_divide_by_zero_is_nan():
    result = computeRatioSpectrum(np.array([1.0, 2.0]), np.array([0.0, 2.0]))
    assert np.isnan(result[0])
    assert result[1] == 1.0


def test_zero_over_zero_is_nan():
    result = computeRatioSpectrum(np.array([0.0]), np.array([0.0]))
    assert np.isnan(result[0])


def test_nan_operands_propagate():
    result = computeRatioSpectrum(np.array([np.nan, 4.0]), np.array([2.0, np.nan]))
    assert np.isnan(result[0])
    assert np.isnan(result[1])


def test_shape_preserved():
    assert computeRatioSpectrum(np.ones(5), np.ones(5)).shape == (5,)


def test_integer_inputs_promoted_to_float():
    num = np.array([3, 6], dtype=np.int64)
    den = np.array([2, 2], dtype=np.int64)
    np.testing.assert_array_almost_equal(computeRatioSpectrum(num, den), [1.5, 3.0])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest src/varda/rois/_tests/test_ratio.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'varda.rois.ratio'`.

- [ ] **Step 3: Write the implementation**

Create `src/varda/rois/ratio.py`:

```python
"""Pure spectral ratio math (Qt-free, unit-tested)."""

from __future__ import annotations

import numpy as np


def computeRatioSpectrum(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    """Element-wise ratio of two spectra (numerator / denominator).

    Args:
        numerator: Per-band values.
        denominator: Per-band values, same shape as ``numerator``.

    Returns:
        A float64 array the same shape as the inputs. Any band where the
        denominator is zero, or where either operand is NaN, is NaN. No
        exceptions or warnings are raised.
    """
    num = np.asarray(numerator, dtype=np.float64)
    den = np.asarray(denominator, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = num / den
    ratio[~np.isfinite(ratio)] = np.nan
    return ratio
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest src/varda/rois/_tests/test_ratio.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/varda/rois/ratio.py src/varda/rois/_tests/test_ratio.py
git commit -m "feat(rois): add pure computeRatioSpectrum"
```

---

### Task 2: `ROICollection.getRatioSpectrum`

**Files:**
- Modify: `src/varda/rois/roi_collection.py` (add import near line 18; add method after `getMeanSpectrum`, ~line 294)
- Test: `src/varda/rois/_tests/test_roi_collection.py` (add helper + test class)

- [ ] **Step 1: Write the failing tests**

Add to the end of `src/varda/rois/_tests/test_roi_collection.py`:

```python
def _make_split_image(width, height, bands, left_fill, right_fill):
    """Fake image: left half filled with left_fill, right half with right_fill."""
    data = np.empty((height, width, bands), dtype=np.float64)
    half = width // 2
    data[:, :half, :] = left_fill
    data[:, half:, :] = right_fill
    return SimpleNamespace(
        width=width,
        height=height,
        bandCount=bands,
        nodata=None,
        wavelengths=np.arange(bands, dtype=np.float64),
        getData=lambda bandIndices=None, window=None: (
            data[
                window[0] : window[0] + window[2],
                window[1] : window[1] + window[3],
                :,
            ]
            if window is not None
            else data
        ),
    )


class TestRatioSpectrum:
    def test_ratio_of_two_rois(self, collection: ROICollection) -> None:
        # numerator ROI in the left half (value 8), denominator in right half (4)
        num_fid = collection.addROI(box(2, 2, 8, 8), "num", RED, ROIMode.RECTANGLE)
        den_fid = collection.addROI(box(31, 2, 38, 8), "den", BLUE, ROIMode.RECTANGLE)
        image = _make_split_image(40, 20, 3, left_fill=8.0, right_fill=4.0)
        ratio = collection.getRatioSpectrum(num_fid, den_fid, image)
        np.testing.assert_array_almost_equal(ratio.values, [2.0, 2.0, 2.0])

    def test_ratio_against_self_is_one(self, collection: ROICollection) -> None:
        fid = collection.addROI(box(2, 2, 8, 8), "roi", RED, ROIMode.RECTANGLE)
        image = _make_split_image(40, 20, 2, left_fill=5.0, right_fill=9.0)
        ratio = collection.getRatioSpectrum(fid, fid, image)
        np.testing.assert_array_almost_equal(ratio.values, [1.0, 1.0])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest src/varda/rois/_tests/test_roi_collection.py::TestRatioSpectrum -q`
Expected: FAIL — `AttributeError: 'ROICollection' object has no attribute 'getRatioSpectrum'`.

- [ ] **Step 3: Add the import**

In `src/varda/rois/roi_collection.py`, just after the existing line
`from varda.common.entities import ROIMode, Spectrum, VardaROI, VardaRaster, Color`
(line 18), add:

```python
from varda.rois.ratio import computeRatioSpectrum
```

(Module-level import — the project style avoids lazy imports, and `ratio.py` only depends on NumPy, so there is no circular-import risk.)

- [ ] **Step 4: Add the method**

In `src/varda/rois/roi_collection.py`, immediately after the `getMeanSpectrum` method (which ends around line 294, before `getStdDeviation`), insert:

```python
    def getRatioSpectrum(
        self, numeratorFid: int, denominatorFid: int, image: VardaRaster
    ) -> Spectrum:
        """Ratio of two ROIs' mean spectra (numerator / denominator).

        Bands where the denominator mean is zero, or where either mean is
        NaN, come out as NaN. See ``computeRatioSpectrum``.
        """
        numerator = self.getROIStatistics(numeratorFid, image)["mean"]
        denominator = self.getROIStatistics(denominatorFid, image)["mean"]
        return Spectrum(
            values=computeRatioSpectrum(numerator, denominator),
            wavelengths=image.wavelengths,
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest src/varda/rois/_tests/test_roi_collection.py -q`
Expected: PASS (all previous tests plus the 2 new ones).

- [ ] **Step 6: Commit**

```bash
git add src/varda/rois/roi_collection.py src/varda/rois/_tests/test_roi_collection.py
git commit -m "feat(rois): add ROICollection.getRatioSpectrum"
```

---

### Task 3: Denominator badge in `ROITableModel`

**Files:**
- Modify: `src/varda/rois/roi_table_model.py`
- Test: `src/varda/rois/_tests/test_roi_table_model.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `src/varda/rois/_tests/test_roi_table_model.py`:

```python
"""Tests for ROITableModel denominator badge/state."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from shapely.geometry import box

from varda.common.entities import Color, ROIMode
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_table_model import ROITableModel

RED = Color(1.0, 0.0, 0.0, 0.5)


def _collection_with_two() -> ROICollection:
    c = ROICollection()
    c.addROI(box(0, 0, 5, 5), "alpha", RED, ROIMode.RECTANGLE)
    c.addROI(box(0, 0, 5, 5), "beta", RED, ROIMode.RECTANGLE)
    return c


def test_default_no_denominator(qtbot):
    model = ROITableModel(_collection_with_two())
    assert model.denominatorFid is None


def test_set_denominator_marks_row(qtbot):
    model = ROITableModel(_collection_with_two())
    fid = model.fidForRow(0)
    model.setDenominatorFid(fid)
    assert model.denominatorFid == fid
    name_index = model.index(0, 1)
    display = model.data(name_index, Qt.ItemDataRole.DisplayRole)
    assert "÷" in display  # the ÷ marker
    font = model.data(name_index, Qt.ItemDataRole.FontRole)
    assert isinstance(font, QFont) and font.bold()


def test_non_denominator_row_unmarked(qtbot):
    model = ROITableModel(_collection_with_two())
    model.setDenominatorFid(model.fidForRow(0))
    other = model.index(1, 1)
    assert "÷" not in model.data(other, Qt.ItemDataRole.DisplayRole)


def test_set_denominator_emits_data_changed(qtbot):
    model = ROITableModel(_collection_with_two())
    with qtbot.waitSignal(model.dataChanged, timeout=500):
        model.setDenominatorFid(model.fidForRow(0))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest src/varda/rois/_tests/test_roi_table_model.py -q`
Expected: FAIL — `AttributeError: 'ROITableModel' object has no attribute 'denominatorFid'`.

- [ ] **Step 3: Add the `QFont` import**

In `src/varda/rois/roi_table_model.py`, change the line
`from PyQt6.QtGui import QColor`
to:

```python
from PyQt6.QtGui import QColor, QFont
```

- [ ] **Step 4: Initialize denominator state**

In `ROITableModel.__init__`, just after `self._collection = collection`, add:

```python
        self._denominatorFid: int | None = None
```

- [ ] **Step 5: Render the marker in `data()`**

In `data()`, replace the Name display branch:

```python
            if col == 1:
                return roi.name
```

with:

```python
            if col == 1:
                if roi.fid == self._denominatorFid:
                    return f"{roi.name}  ÷"
                return roi.name
```

Then, immediately after the existing `DecorationRole` block:

```python
        if role == Qt.ItemDataRole.DecorationRole and col == 2:
            return roi.color.toQColor()
```

add a `FontRole` block:

```python
        if role == Qt.ItemDataRole.FontRole and roi.fid == self._denominatorFid:
            font = QFont()
            font.setBold(True)
            return font
```

- [ ] **Step 6: Add the state accessor + mutator**

In `src/varda/rois/roi_table_model.py`, after the `collection` property (around line 36), add:

```python
    @property
    def denominatorFid(self) -> int | None:
        return self._denominatorFid

    def setDenominatorFid(self, fid: int | None) -> None:
        """Mark the row with this fid as the ratio denominator (or clear)."""
        if fid == self._denominatorFid:
            return
        self._denominatorFid = fid
        if self.rowCount() > 0:
            top = self.index(0, 0)
            bottom = self.index(self.rowCount() - 1, self.columnCount() - 1)
            self.dataChanged.emit(top, bottom)
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest src/varda/rois/_tests/test_roi_table_model.py -q`
Expected: PASS (4 passed).

- [ ] **Step 8: Commit**

```bash
git add src/varda/rois/roi_table_model.py src/varda/rois/_tests/test_roi_table_model.py
git commit -m "feat(rois): show denominator badge in ROI table model"
```

---

### Task 4: Row context menu + action signals in `ROITableView`

**Files:**
- Modify: `src/varda/rois/roi_table_view.py`
- Test: `src/varda/rois/_tests/test_roi_table_view.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `src/varda/rois/_tests/test_roi_table_view.py`:

```python
"""Tests for ROITableView row context menu actions."""

from PyQt6.QtWidgets import QMenu
from shapely.geometry import box

from varda.common.entities import Color, ROIMode
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_table_model import ROITableModel
from varda.rois.roi_table_view import ROITableView

RED = Color(1.0, 0.0, 0.0, 0.5)


def _view():
    c = ROICollection()
    c.addROI(box(0, 0, 5, 5), "alpha", RED, ROIMode.RECTANGLE)
    model = ROITableModel(c)
    return ROITableView(model), model


def _find_action(menu: QMenu, text: str):
    for a in menu.actions():
        if a.text() == text:
            return a
    raise AssertionError(f"action {text!r} not found")


def test_plot_spectrum_action_emits(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    menu = view._buildRowMenu(fid)
    with qtbot.waitSignal(view.sigPlotSpectrumRequested, timeout=500) as sig:
        _find_action(menu, "Plot Spectrum").trigger()
    assert sig.args == [fid]


def test_plot_ratio_action_emits(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    menu = view._buildRowMenu(fid)
    with qtbot.waitSignal(view.sigPlotRatioRequested, timeout=500) as sig:
        _find_action(menu, "Plot Ratio Spectrum").trigger()
    assert sig.args == [fid]


def test_set_denominator_action_emits(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    menu = view._buildRowMenu(fid)
    with qtbot.waitSignal(view.sigDenominatorSetRequested, timeout=500) as sig:
        _find_action(menu, "Set as Denominator").trigger()
    assert sig.args == [fid]


def test_set_denominator_disabled_when_already_denominator(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    model.setDenominatorFid(fid)
    menu = view._buildRowMenu(fid)
    assert not _find_action(menu, "Set as Denominator").isEnabled()


def test_clear_denominator_disabled_when_none(qtbot):
    view, model = _view()
    menu = view._buildRowMenu(model.fidForRow(0))
    assert not _find_action(menu, "Clear Denominator").isEnabled()


def test_clear_denominator_action_emits(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    model.setDenominatorFid(fid)
    menu = view._buildRowMenu(fid)
    with qtbot.waitSignal(view.sigDenominatorClearRequested, timeout=500):
        _find_action(menu, "Clear Denominator").trigger()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest src/varda/rois/_tests/test_roi_table_view.py -q`
Expected: FAIL — `AttributeError: 'ROITableView' object has no attribute '_buildRowMenu'` (or missing signal).

- [ ] **Step 3: Add the action signals**

In `src/varda/rois/roi_table_view.py`, in the `ROITableView` class body, just after:

```python
    roiSelected = pyqtSignal(int)  # emit fid
```

add:

```python
    sigPlotSpectrumRequested = pyqtSignal(int)
    sigPlotRatioRequested = pyqtSignal(int)
    sigDenominatorSetRequested = pyqtSignal(int)
    sigDenominatorClearRequested = pyqtSignal()
```

- [ ] **Step 4: Enable the row context menu**

In `ROITableView.__init__`, at the end of the method (after the `header` block), add:

```python
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._onRowContextMenu)
```

- [ ] **Step 5: Add the menu handlers**

In `src/varda/rois/roi_table_view.py`, add these methods to `ROITableView` (e.g. after `_onDoubleClick`):

```python
    def _onRowContextMenu(self, pos: QPoint) -> None:
        index = self.indexAt(pos)
        if not index.isValid():
            return
        fid = self._roiModel.fidForRow(index.row())
        if fid is None:
            return
        self._buildRowMenu(fid).popup(QCursor.pos())

    def _buildRowMenu(self, fid: int) -> QMenu:
        menu = QMenu(self)

        plotAction = QAction("Plot Spectrum", menu)
        plotAction.triggered.connect(lambda: self.sigPlotSpectrumRequested.emit(fid))
        menu.addAction(plotAction)

        ratioAction = QAction("Plot Ratio Spectrum", menu)
        ratioAction.triggered.connect(lambda: self.sigPlotRatioRequested.emit(fid))
        menu.addAction(ratioAction)

        menu.addSeparator()

        setDenomAction = QAction("Set as Denominator", menu)
        setDenomAction.setEnabled(fid != self._roiModel.denominatorFid)
        setDenomAction.triggered.connect(
            lambda: self.sigDenominatorSetRequested.emit(fid)
        )
        menu.addAction(setDenomAction)

        clearDenomAction = QAction("Clear Denominator", menu)
        clearDenomAction.setEnabled(self._roiModel.denominatorFid is not None)
        clearDenomAction.triggered.connect(
            lambda: self.sigDenominatorClearRequested.emit()
        )
        menu.addAction(clearDenomAction)

        return menu
```

(All of `QPoint`, `QCursor`, `QAction`, `QMenu`, and `Qt` are already imported at the top of this file.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest src/varda/rois/_tests/test_roi_table_view.py -q`
Expected: PASS (6 passed).

- [ ] **Step 7: Commit**

```bash
git add src/varda/rois/roi_table_view.py src/varda/rois/_tests/test_roi_table_view.py
git commit -m "feat(rois): add ROI table row context menu with ratio actions"
```

---

### Task 5: `ROIManagerWidget` owns plotting + denominator state

**Files:**
- Modify: `src/varda/rois/roi_manager_widget.py`
- Test: `src/varda/rois/_tests/test_roi_manager_widget.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `src/varda/rois/_tests/test_roi_manager_widget.py`:

```python
"""Tests for ROIManagerWidget plotting + denominator behavior."""

from types import SimpleNamespace

import numpy as np
from shapely.geometry import box

from varda.common.entities import Color, ROIMode
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_manager_widget import ROIManagerWidget

RED = Color(1.0, 0.0, 0.0, 0.5)
BLUE = Color(0.0, 0.0, 1.0, 0.5)


def _make_split_image(width, height, bands, left_fill, right_fill):
    data = np.empty((height, width, bands), dtype=np.float64)
    half = width // 2
    data[:, :half, :] = left_fill
    data[:, half:, :] = right_fill
    return SimpleNamespace(
        width=width,
        height=height,
        bandCount=bands,
        nodata=None,
        wavelengths=np.arange(bands, dtype=np.float64),
        wavelengthsType=float,
        getData=lambda bandIndices=None, window=None: (
            data[
                window[0] : window[0] + window[2],
                window[1] : window[1] + window[3],
                :,
            ]
            if window is not None
            else data
        ),
    )


class _FakePlot:
    """Records plot() calls instead of drawing."""

    def __init__(self):
        self.calls = []

    def plot(self, x, y, color=None, name=None, **kwargs):
        self.calls.append(
            SimpleNamespace(x=np.asarray(x), y=np.asarray(y), color=color, name=name)
        )


def test_plot_spectrum_records_curve(qtbot):
    c = ROICollection()
    fid = c.addROI(box(2, 2, 8, 8), "roi", RED, ROIMode.RECTANGLE)
    plot = _FakePlot()
    w = ROIManagerWidget(c, _make_split_image(40, 20, 3, 8.0, 4.0), plot)
    w.plotSpectrum(fid)
    assert len(plot.calls) == 1
    np.testing.assert_array_almost_equal(plot.calls[0].y, [8.0, 8.0, 8.0])
    assert plot.calls[0].name == "roi"


def test_set_denominator_updates_model_and_emits(qtbot):
    c = ROICollection()
    fid = c.addROI(box(2, 2, 8, 8), "roi", RED, ROIMode.RECTANGLE)
    w = ROIManagerWidget(c, _make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    with qtbot.waitSignal(w.sigDenominatorChanged, timeout=500) as sig:
        w.setDenominator(fid)
    assert w.denominatorFid == fid
    assert w.model.denominatorFid == fid
    assert sig.args == [fid]


def test_plot_ratio_without_denominator_does_nothing(qtbot, monkeypatch):
    import varda.rois.roi_manager_widget as mod

    monkeypatch.setattr(mod.QMessageBox, "information", lambda *a, **k: None)
    c = ROICollection()
    fid = c.addROI(box(2, 2, 8, 8), "roi", RED, ROIMode.RECTANGLE)
    plot = _FakePlot()
    w = ROIManagerWidget(c, _make_split_image(40, 20, 3, 8.0, 4.0), plot)
    w.plotRatioSpectrum(fid)
    assert plot.calls == []


def test_plot_ratio_with_denominator_records_ratio(qtbot):
    c = ROICollection()
    num = c.addROI(box(2, 2, 8, 8), "num", RED, ROIMode.RECTANGLE)
    den = c.addROI(box(31, 2, 38, 8), "den", BLUE, ROIMode.RECTANGLE)
    plot = _FakePlot()
    w = ROIManagerWidget(c, _make_split_image(40, 20, 3, 8.0, 4.0), plot)
    w.setDenominator(den)
    w.plotRatioSpectrum(num)
    assert len(plot.calls) == 1
    np.testing.assert_array_almost_equal(plot.calls[0].y, [2.0, 2.0, 2.0])
    assert plot.calls[0].name == "num / den"


def test_removing_denominator_clears_it(qtbot):
    c = ROICollection()
    den = c.addROI(box(31, 2, 38, 8), "den", BLUE, ROIMode.RECTANGLE)
    w = ROIManagerWidget(c, _make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    w.setDenominator(den)
    c.removeROI(den)
    assert w.denominatorFid is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest src/varda/rois/_tests/test_roi_manager_widget.py -q`
Expected: FAIL — `TypeError` on the constructor (it does not yet accept `image`/`plotWidget`).

- [ ] **Step 3: Replace the widget implementation**

Replace the entire contents of `src/varda/rois/roi_manager_widget.py` with:

```python
"""ROI manager widget: table + controls, owning ROI plotting + denominator state."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QInputDialog,
    QMessageBox,
)

from varda.plotting.plot import VardaPlotWidget
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_table_model import ROITableModel
from varda.rois.roi_table_view import ROITableView

if TYPE_CHECKING:
    from varda.common.entities import VardaRaster

logger = logging.getLogger(__name__)


class ROIManagerWidget(QWidget):
    """Table + controls for ROIs. Owns spectral plotting and denominator state.

    The workspace supplies the spectral ``image`` and the ``plotWidget`` to draw
    into; this widget computes mean and ratio spectra and plots them directly, so
    the plotting logic is not duplicated across workspaces.
    """

    sigSelectionChanged = pyqtSignal(object)  # emits fid (int) or None
    sigDenominatorChanged = pyqtSignal(object)  # emits fid (int) or None

    def __init__(
        self,
        collection: ROICollection,
        image: VardaRaster,
        plotWidget: VardaPlotWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._collection = collection
        self._image = image
        self._plotWidget = plotWidget
        self._denominatorFid: int | None = None

        # Model / View
        self._model = ROITableModel(collection, parent=self)
        self._table = ROITableView(self._model, parent=self)

        # Buttons
        self._deleteBtn = QPushButton("Delete Selected")
        self._deleteBtn.clicked.connect(self._deleteSelected)

        self._addColumnBtn = QPushButton("Add Column...")
        self._addColumnBtn.clicked.connect(self._addColumn)

        self._exportBtn = QPushButton("Export...")
        self._exportBtn.clicked.connect(self._exportCollection)

        self._plotBtn = QPushButton("Plot Spectrum")
        self._plotBtn.clicked.connect(self._plotSelected)
        self._plotBtn.setEnabled(False)

        # Layout
        btnRow = QHBoxLayout()
        btnRow.addWidget(self._deleteBtn)
        btnRow.addWidget(self._addColumnBtn)
        btnRow.addWidget(self._exportBtn)
        btnRow.addWidget(self._plotBtn)
        btnRow.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(btnRow)
        layout.addWidget(self._table)

        # Forward table selection changes as fid
        selModel = self._table.selectionModel()
        if selModel is not None:
            selModel.selectionChanged.connect(self._onSelectionChanged)

        # Wire row context-menu actions
        self._table.sigPlotSpectrumRequested.connect(self.plotSpectrum)
        self._table.sigPlotRatioRequested.connect(self.plotRatioSpectrum)
        self._table.sigDenominatorSetRequested.connect(self.setDenominator)
        self._table.sigDenominatorClearRequested.connect(
            lambda: self.setDenominator(None)
        )

        # Keep denominator state consistent if its ROI is deleted
        collection.sigROIRemoved.connect(self._onROIRemoved)

    @property
    def table(self) -> ROITableView:
        return self._table

    @property
    def model(self) -> ROITableModel:
        return self._model

    @property
    def denominatorFid(self) -> int | None:
        return self._denominatorFid

    def selectedFid(self) -> int | None:
        """Return the fid of the currently selected row, or None."""
        idxs = self._table.selectionModel().selectedRows()
        if not idxs:
            return None
        return self._model.fidForRow(idxs[0].row())

    # --- Plotting / ratio ---

    def setDenominator(self, fid: int | None) -> None:
        """Set (or clear, with None) the ratio reference ROI."""
        self._denominatorFid = fid
        self._model.setDenominatorFid(fid)
        self.sigDenominatorChanged.emit(fid)

    def plotSpectrum(self, fid: int) -> None:
        """Plot the mean spectrum of an ROI into the plot widget."""
        stats = self._collection.getROIStatistics(fid, self._image)
        if stats["pixel_count"] == 0:
            logger.warning("ROI fid=%d has no pixels", fid)
            return
        mean = stats["mean"]
        wavelengths = VardaPlotWidget.getPlottableWavelengths(self._image, len(mean))
        roi = self._collection.getROI(fid)
        self._plotWidget.plot(wavelengths, mean, color=roi.color, name=roi.name)

    def plotRatioSpectrum(self, fid: int) -> None:
        """Plot an ROI's mean spectrum divided by the denominator's mean."""
        if self._denominatorFid is None:
            QMessageBox.information(
                self,
                "No denominator set",
                "Right-click an ROI and choose 'Set as Denominator' first, "
                "then plot a ratio spectrum.",
            )
            return
        ratio = self._collection.getRatioSpectrum(
            fid, self._denominatorFid, self._image
        )
        numerator = self._collection.getROI(fid)
        denominator = self._collection.getROI(self._denominatorFid)
        wavelengths = VardaPlotWidget.getPlottableWavelengths(
            self._image, len(ratio.values)
        )
        self._plotWidget.plot(
            wavelengths,
            ratio.values,
            color=numerator.color,
            name=f"{numerator.name} / {denominator.name}",
        )

    # --- Internal handlers ---

    def _onSelectionChanged(self, selected, _deselected) -> None:
        if not selected.indexes():
            self.sigSelectionChanged.emit(None)
            self._plotBtn.setEnabled(False)
            return
        fid = self._model.fidForRow(selected.indexes()[0].row())
        self.sigSelectionChanged.emit(fid)
        self._plotBtn.setEnabled(fid is not None)

    def _onROIRemoved(self, fid: int) -> None:
        if fid == self._denominatorFid:
            self.setDenominator(None)

    def _plotSelected(self) -> None:
        fid = self.selectedFid()
        if fid is not None:
            self.plotSpectrum(fid)

    def _deleteSelected(self) -> None:
        fid = self.selectedFid()
        if fid is not None:
            self._collection.removeROI(fid)

    def _addColumn(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Column", "Column name:")
        if not ok or not name.strip():
            return
        try:
            self._collection.addColumn(name)
        except ValueError as e:
            QMessageBox.warning(self, "Cannot Add Column", str(e))

    def _exportCollection(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export ROIs",
            "",
            "GeoJSON (*.geojson);;GeoPackage (*.gpkg);;Shapefile (*.shp)",
        )
        if path:
            self._collection.toFile(path)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest src/varda/rois/_tests/test_roi_manager_widget.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/varda/rois/roi_manager_widget.py src/varda/rois/_tests/test_roi_manager_widget.py
git commit -m "feat(rois): move ROI plotting + denominator state into ROIManagerWidget"
```

---

### Task 6: Wire the new manager into the general image analysis workspace

**Files:**
- Modify: `src/varda/workspaces/general_image_analysis/general_image_analysis.py`

- [ ] **Step 1: Pass image + plot widget to the manager**

In `_initData`, replace this block (around lines 114-117):

```python
        self.roiManagerWidget = ROIManagerWidget(self.roiCollection, parent=self)

        # --- Spectral plot ---
        self.plotWidget = VardaPlotWidget(parent=self)
```

with (note the reorder — the plot widget must exist before the manager):

```python
        # --- Spectral plot ---
        self.plotWidget = VardaPlotWidget(parent=self)

        self.roiManagerWidget = ROIManagerWidget(
            self.roiCollection, image, self.plotWidget, parent=self
        )
```

(`image` is the local variable assigned earlier in `_initData` from `self.config.image.value`.)

- [ ] **Step 2: Remove the obsolete plot wiring**

In `_connectSignals`, delete these two lines:

```python
        # Wire ROI spectral plot
        self.roiManagerWidget.sigPlotRequested.connect(self._onPlotRequested)
```

- [ ] **Step 3: Delete the `_onPlotRequested` method**

Delete the entire `_onPlotRequested` method (the block starting `def _onPlotRequested(self, fid: int) -> None:` through the commented-out `plotWithFill` lines at the end of it).

- [ ] **Step 4: Smoke-check the import**

Run:
```bash
uv run python -c "import varda.workspaces.general_image_analysis.general_image_analysis as m; print('ok')"
```
Expected: `ok` (no `AttributeError`/`ImportError`).

- [ ] **Step 5: Commit**

```bash
git add src/varda/workspaces/general_image_analysis/general_image_analysis.py
git commit -m "refactor(workspace): delegate ROI plotting to ROIManagerWidget (general analysis)"
```

---

### Task 7: Wire the new manager into the dual image workspace

**Files:**
- Modify: `src/varda/workspaces/dual_image_workspace/dual_image_workspace.py`

This workspace builds its ROI collection from `image2` but extracts spectra from
`image1` (the primary spectral cube), so `image1` is the spectral image to pass.

- [ ] **Step 1: Pass image1 + plot widget to the manager**

In `_initComponents`, replace this block (around lines 92-93):

```python
        self.roiManagerWidget = ROIManagerWidget(self.roiCollection, parent=self)
        self.plotWidget = VardaPlotWidget(parent=self)
```

with:

```python
        self.plotWidget = VardaPlotWidget(parent=self)
        self.roiManagerWidget = ROIManagerWidget(
            self.roiCollection, self.image1, self.plotWidget, parent=self
        )
```

- [ ] **Step 2: Remove the obsolete plot wiring**

In `_connectSignals`, delete these two lines:

```python
        # Wire spectral plot
        self.roiManagerWidget.sigPlotRequested.connect(self._onPlotRequested)
```

- [ ] **Step 3: Delete the `_onPlotRequested` method**

Delete the entire `_onPlotRequested` method (the block starting
`def _onPlotRequested(self, fid: int) -> None:` through its `self.plotWidget.plot(...)` call).

- [ ] **Step 4: Smoke-check the import**

Run:
```bash
uv run python -c "import varda.workspaces.dual_image_workspace.dual_image_workspace as m; print('ok')"
```
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add src/varda/workspaces/dual_image_workspace/dual_image_workspace.py
git commit -m "refactor(workspace): delegate ROI plotting to ROIManagerWidget (dual image)"
```

---

### Task 8: Full verification (format, type-check, tests)

**Files:** none (verification only)

- [ ] **Step 1: Format**

Use the `astral:ruff` skill for guidance, then run:
```bash
uv run ruff format src/varda/rois src/varda/workspaces
uv run ruff check src/varda/rois
```
Expected: formatting applied; no lint errors introduced. If `ruff check` reports issues in the files you touched, fix them.

- [ ] **Step 2: Type-check**

Use the `astral:ty` skill for guidance, then run:
```bash
uv run ty check src/varda/rois/ratio.py src/varda/rois/roi_collection.py src/varda/rois/roi_manager_widget.py src/varda/rois/roi_table_model.py src/varda/rois/roi_table_view.py
```
Expected: no new type errors in these files. Fix any that your changes introduced.

- [ ] **Step 3: Run the full ROI test suite**

Run: `uv run pytest src/varda/rois -q`
Expected: PASS (all ROI tests, including the new ratio/menu/manager tests).

- [ ] **Step 4: Commit any format/type fixups**

```bash
git add -A
git commit -m "chore(rois): formatting and type-check fixups for ratioing"
```

(If Steps 1-3 produced no changes, skip this commit.)

---

### Task 9: Manual GUI verification

**Files:** none (manual — the author cannot run the GUI here; the user performs this)

- [ ] **Step 1: Launch and exercise ratioing**

Run the app (use the `run` skill or the project's normal launch command), open a
General Image Analysis workspace on a multi-band image, then:

1. Draw two ROIs over different areas.
2. Select a row and click **Plot Spectrum** → its mean spectrum appears in the ROI Plots dock.
3. Right-click an ROI row → **Set as Denominator**. That row shows a bold name with a "÷" marker.
4. Right-click the *other* ROI → **Plot Ratio Spectrum** → a curve named `"<that ROI> / <denominator>"` appears.
5. Right-click an ROI with no denominator set (use **Clear Denominator** first) → **Plot Ratio Spectrum** → an informational dialog appears, no crash, no curve added.
6. Delete the denominator ROI → the badge disappears and ratio plotting again prompts to set a denominator.
```
