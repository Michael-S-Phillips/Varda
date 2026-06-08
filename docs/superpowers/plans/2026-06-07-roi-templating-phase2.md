# ROI Templating & Column-Locked Placement (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user mark an ROI as a "template", then right-click anywhere on the image to stamp a copy of it there — optionally snapping the copy to the same CRISM sensor column as the template.

**Architecture:** Three layers, all committed to the existing PR #88 branch (`feature/roi-ratioing`). (1) A pure, isolated CRISM geometry module that resolves the DDR backplane companion file and computes a column-locked horizontal shift. (2) Template selection state on `ROIManagerWidget` (mirroring the denominator), with a table badge and a `placeTemplate(...)` method that does the geometry math. (3) A modular, `app_model`-driven viewport context menu (the template-placement action is declared externally and injected into the viewport's menu, so the generic viewport never hardcodes template logic).

**Tech Stack:** Python 3.13, PyQt6, NumPy, rasterio, shapely, app_model 0.5.1, pytest + pytest-qt (`qtbot`), `uv`, ruff, ty.

**Design reference:** `docs/superpowers/specs/2026-06-07-roi-ratioing-and-templating-design.md` (Phase 2 sections).

**Decisions locked with the user:**
- One combined plan; commit to the existing PR #88 branch (no separate PR).
- Template state lives on `ROIManagerWidget` (like the denominator), set via a row context-menu action, shown with a table badge.
- When no CRISM DDR geometry resolves, the "Lock to sensor column" toggle is **disabled** and "Place template here" does a plain centroid paste. Non-CRISM images stay fully usable.

**Testing notes:**
- `uv run pytest`; Qt tests use `qtbot` (offscreen preconfigured in `_tests/conftest.py`).
- The CRISM geometry math and the placement translation are pure/Qt-free and get real unit tests. The viewport/app_model wiring (Tasks 9–11) is verified by import smoke-checks + manual GUI (consistent with how Phase 1 handled GUI wiring).
- After each code step run `uv run ruff check <file>` and `uv run ty check <file>` and fix any NEW errors your change introduces (pre-existing diagnostics in untouched code may remain).

---

## File Structure

- **Create** `src/varda/image_loading/crism_geometry.py` — isolated CRISM DDR reader + column-lock math (Qt-free).
- **Create** `src/varda/image_loading/_tests/test_crism_geometry.py` — tests.
- **Modify** `src/varda/rois/roi_table_model.py` — add a template badge (mirrors denominator).
- **Modify** `src/varda/rois/_tests/test_roi_table_model.py` — template badge tests.
- **Modify** `src/varda/rois/roi_table_view.py` — "Set as Template" / "Clear Template" row-menu signals.
- **Modify** `src/varda/rois/_tests/test_roi_table_view.py` — menu tests.
- **Modify** `src/varda/rois/roi_manager_widget.py` — template state + `placeTemplate(...)`.
- **Modify** `src/varda/rois/_tests/test_roi_manager_widget.py` — template + placement tests.
- **Create** `src/varda/image_rendering/raster_view/viewport_actions.py` — app_model menu id, click-context holder, `VIEWPORT_ACTIONS`.
- **Modify** `src/varda/app.py` — register `VIEWPORT_ACTIONS` + the click-context provider.
- **Modify** `src/varda/image_rendering/raster_view/image_viewport.py` — emit `sigContextMenuRequested` on unconsumed right-click.
- **Create** `src/varda/image_rendering/raster_view/viewport_context_menu_controller.py` — builds & pops the `QModelMenu`, owns the lock toggle state.
- **Modify** `src/varda/workspaces/general_image_analysis/general_image_analysis.py` — wire the controller.

---

### Task 1: CRISM geometry companion-file resolver

**Files:**
- Create: `src/varda/image_loading/crism_geometry.py`
- Test: `src/varda/image_loading/_tests/test_crism_geometry.py`

CRISM products have a geometry "DDR" backplane companion file. The mapping is by filename pattern (mosaic tiles `*_mrral_*` → `*_mrrde_*`; per-strip MTRDR `*_if166j_*` → `*_in166j_*`; VRDR `*_vrral_*` → `*_vrrde_*`).

- [ ] **Step 1: Write the failing tests**

Create `src/varda/image_loading/_tests/test_crism_geometry.py`:

```python
"""Tests for the isolated CRISM geometry module."""

from pathlib import Path

from varda.image_loading.crism_geometry import resolveGeometryFile


def _touch(p: Path) -> None:
    p.write_bytes(b"")


def test_resolves_per_strip_mtrdr(tmp_path):
    src = tmp_path / "frt00013000_07_if166j_mtr3.img"
    _touch(src)
    ddr = tmp_path / "frt00013000_07_in166j_mtr3.img"
    _touch(ddr)
    assert resolveGeometryFile(str(src)) == str(ddr)


def test_resolves_mosaic_tile(tmp_path):
    src = tmp_path / "t0886_mrral_05s058_0327_4.img"
    _touch(src)
    ddr = tmp_path / "t0886_mrrde_05s058_0327_4.img"
    _touch(ddr)
    assert resolveGeometryFile(str(src)) == str(ddr)


def test_returns_none_when_companion_missing(tmp_path):
    src = tmp_path / "frt00013000_07_if166j_mtr3.img"
    _touch(src)
    assert resolveGeometryFile(str(src)) is None


def test_returns_none_for_non_crism_name(tmp_path):
    src = tmp_path / "some_geotiff.tif"
    _touch(src)
    assert resolveGeometryFile(str(src)) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest src/varda/image_loading/_tests/test_crism_geometry.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'varda.image_loading.crism_geometry'`.

- [ ] **Step 3: Write the resolver**

Create `src/varda/image_loading/crism_geometry.py`:

```python
"""Isolated CRISM geometry (DDR backplane) support for column-locked ROI placement.

CRISM reflectance products ship a separate geometry "DDR" file whose bands give,
per pixel, the detector column ("IR Sample") and the source strip identity
("Target ID" + "Segment ID"). This module resolves that companion file and
computes the horizontal shift needed to place a copied ROI on the same detector
column as its template. It is deliberately CRISM-specific and self-contained: no
general multi-instrument abstraction until a second instrument needs one.
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

# (pattern, replacement) applied to the filename stem to find the DDR companion.
_GEOMETRY_NAME_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"_mrr(al|if|ir|sr|su|ra)_", re.IGNORECASE), "_mrrde_"),
    (re.compile(r"_vrr(al|if|ir|sr|su|ra)_", re.IGNORECASE), "_vrrde_"),
    (re.compile(r"_(if|sr|su)(\d{3}[a-z])", re.IGNORECASE), r"_in\2"),
]


def resolveGeometryFile(sourceFilename: str) -> str | None:
    """Map a CRISM source ``.img``/``.hdr`` path to its geometry companion path.

    Returns the companion ``.img`` path if it exists on disk, else None.
    """
    directory = os.path.dirname(sourceFilename)
    filename = os.path.basename(sourceFilename)
    stem, _ext = os.path.splitext(filename)

    for pattern, replacement in _GEOMETRY_NAME_PATTERNS:
        newStem, nSubs = pattern.subn(replacement, stem)
        if nSubs == 0 or newStem == stem:
            continue
        candidate = os.path.join(directory, newStem + ".img")
        if os.path.exists(candidate):
            return candidate
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest src/varda/image_loading/_tests/test_crism_geometry.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/varda/image_loading/crism_geometry.py src/varda/image_loading/_tests/test_crism_geometry.py
git commit -m "feat(crism): resolve CRISM DDR geometry companion file by name pattern"
```

---

### Task 2: Column-lock translation math (pure)

**Files:**
- Modify: `src/varda/image_loading/crism_geometry.py`
- Test: `src/varda/image_loading/_tests/test_crism_geometry.py`

This is the core of the feature: given the template polygon (pixel coords), the click location, and the per-pixel geometry arrays, compute the `(dx, dy)` pixel shift that lands the copy on the same detector column within the same strip.

- [ ] **Step 1: Write the failing tests**

Append to `src/varda/image_loading/_tests/test_crism_geometry.py`:

```python
import numpy as np

from varda.image_loading.crism_geometry import (
    ColumnGeometry,
    computeColumnLockedTranslation,
)


def _geometry():
    # 10 rows x 8 cols. IR Sample = detector column index = the column number,
    # constant down each column. One strip (target 1, segment 1) everywhere.
    h, w = 10, 8
    ir = np.tile(np.arange(w, dtype=np.float64), (h, 1))
    target = np.ones((h, w), dtype=np.float64)
    segment = np.ones((h, w), dtype=np.float64)
    return ColumnGeometry(ir_sample=ir, target_id=target, segment_id=segment)


def test_translation_keeps_same_column():
    geom = _geometry()
    # Template is a 2x2 box over columns 2..3, rows 1..2 -> mean IR sample ~2.5.
    template_px = np.array([[2, 1], [3, 1], [3, 2], [2, 2]], dtype=np.float64)
    # Click at row 7, column 6. Column-lock should pull dx back so the copy
    # sits on the template's detector column (~2-3), not at column 6.
    dxdy = computeColumnLockedTranslation(template_px, clickRow=7, clickCol=6, geometry=geom)
    assert dxdy is not None
    dx, dy = dxdy
    src_cx = float(template_px[:, 0].mean())  # ~2.5
    # New column = src_cx + dx must match the template's IR sample column (~2-3).
    assert abs((src_cx + dx) - 2.5) <= 1.0
    # dy moves the centroid row to the click row.
    src_cy = float(template_px[:, 1].mean())  # ~1.5
    assert abs((src_cy + dy) - 7) < 1e-6


def test_translation_none_when_strip_absent_at_dest_row():
    geom = _geometry()
    # Make destination row 7 a different strip than the template's.
    geom.target_id[7, :] = 99
    template_px = np.array([[2, 1], [3, 1], [3, 2], [2, 2]], dtype=np.float64)
    assert (
        computeColumnLockedTranslation(template_px, clickRow=7, clickCol=6, geometry=geom)
        is None
    )


def test_translation_none_when_dest_row_out_of_bounds():
    geom = _geometry()
    template_px = np.array([[2, 1], [3, 1], [3, 2], [2, 2]], dtype=np.float64)
    assert (
        computeColumnLockedTranslation(template_px, clickRow=999, clickCol=6, geometry=geom)
        is None
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest src/varda/image_loading/_tests/test_crism_geometry.py -q`
Expected: FAIL — `ImportError: cannot import name 'ColumnGeometry'`.

- [ ] **Step 3: Implement `ColumnGeometry` + `computeColumnLockedTranslation`**

Add to `src/varda/image_loading/crism_geometry.py` (add `import attrs` and `import numpy as np` at the top with the other imports):

```python
import attrs
import numpy as np


@attrs.define
class ColumnGeometry:
    """Per-pixel CRISM geometry arrays, all shape (height, width).

    ``ir_sample`` is the detector column index; ``target_id`` and ``segment_id``
    identify the source observation strip. Missing values are NaN.
    """

    ir_sample: np.ndarray
    target_id: np.ndarray | None = None
    segment_id: np.ndarray | None = None


def _modeUnderMask(arr: np.ndarray | None, mask: np.ndarray) -> int | None:
    """Most common (non-NaN) integer value of ``arr`` under a boolean mask."""
    if arr is None:
        return None
    vals = arr[mask]
    vals = vals[~np.isnan(vals)]
    if vals.size == 0:
        return None
    uniq, counts = np.unique(vals.astype(np.int64), return_counts=True)
    return int(uniq[int(np.argmax(counts))])


def computeColumnLockedTranslation(
    templatePolygonPixels: np.ndarray,
    clickRow: int,
    clickCol: int,
    geometry: ColumnGeometry,
) -> tuple[float, float] | None:
    """Compute the (dx, dy) pixel shift for a column-locked template paste.

    ``templatePolygonPixels`` is an (N, 2) array of (col, row) pixel coordinates.
    Returns (dx, dy) so that the template, shifted by it, sits on the same
    detector column within the same strip at the clicked row. Returns None if
    the lock cannot be satisfied (destination row out of bounds, the template's
    strip does not reach the destination row, or no geometry under the template).
    """
    import rasterio.features
    from shapely.geometry import Polygon
    from shapely.geometry import mapping as shapely_mapping

    ir = geometry.ir_sample
    nrows, ncols = ir.shape

    # Rasterize the template polygon footprint to a boolean mask. (Same approach
    # as ROICollection.getMask, so no extra dependency is needed.)
    poly = Polygon([(float(c), float(r)) for c, r in templatePolygonPixels])
    maskBool = rasterio.features.rasterize(
        [(shapely_mapping(poly), 1)],
        out_shape=(nrows, ncols),
        fill=0,
        dtype=np.uint8,
    ).astype(bool)

    srcIr = ir[maskBool]
    srcIr = srcIr[~np.isnan(srcIr)]
    if srcIr.size == 0:
        return None
    srcIrMean = float(np.mean(srcIr))
    srcTarget = _modeUnderMask(geometry.target_id, maskBool)
    srcSeg = _modeUnderMask(geometry.segment_id, maskBool)

    destY = int(clickRow)
    if not (0 <= destY < nrows):
        return None

    rowIr = ir[destY, :]
    valid = ~np.isnan(rowIr)
    if srcTarget is not None and geometry.target_id is not None:
        valid &= geometry.target_id[destY, :] == srcTarget
    if srcSeg is not None and geometry.segment_id is not None:
        valid &= geometry.segment_id[destY, :] == srcSeg
    validXs = np.where(valid)[0]
    if validXs.size == 0:
        return None

    bestX = int(validXs[int(np.argmin(np.abs(rowIr[validXs] - srcIrMean)))])

    srcCx = float(templatePolygonPixels[:, 0].mean())
    srcCy = float(templatePolygonPixels[:, 1].mean())
    dx = bestX - srcCx
    dy = float(clickRow) - srcCy
    return (dx, dy)
```

Note: `opencv-python` (`cv2`) is used to rasterize the polygon footprint, matching the SCAT reference. Confirm it is available:
Run: `uv run python -c "import cv2; print(cv2.__version__)"`
If it errors with `ModuleNotFoundError`, add it: `uv add opencv-python-headless` and note this in the commit.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest src/varda/image_loading/_tests/test_crism_geometry.py -q`
Expected: PASS (7 passed).

(No new dependency: the polygon footprint is rasterized with `rasterio.features.rasterize`, already a Varda dependency used in `ROICollection.getMask`.)

- [ ] **Step 5: Commit**

```bash
git add src/varda/image_loading/crism_geometry.py src/varda/image_loading/_tests/test_crism_geometry.py
git commit -m "feat(crism): compute column-locked translation from DDR geometry"
```

---

### Task 3: Load DDR geometry arrays from the companion file

**Files:**
- Modify: `src/varda/image_loading/crism_geometry.py`
- Test: `src/varda/image_loading/_tests/test_crism_geometry.py`

Reads the IR Sample / Target ID / Segment ID bands from the DDR `.img`, located by rasterio band **descriptions** (not fixed indices, since tile vs per-strip files differ), with the file nodata treated as NaN. The band-alias matching is the unit-tested part.

- [ ] **Step 1: Write the failing test (band-alias matching is the pure, testable core)**

Append to `src/varda/image_loading/_tests/test_crism_geometry.py`:

```python
from varda.image_loading.crism_geometry import findBandIndex


def test_find_band_index_matches_aliases():
    descriptions = ("IR (L-detector) Sample", "Target ID", "Segment ID (counter)")
    assert findBandIndex(descriptions, "ir_sample") == 1  # 1-indexed for rasterio
    assert findBandIndex(descriptions, "target_id") == 2
    assert findBandIndex(descriptions, "segment_id") == 3


def test_find_band_index_returns_none_when_absent():
    assert findBandIndex(("Latitude", "Longitude"), "ir_sample") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest src/varda/image_loading/_tests/test_crism_geometry.py::test_find_band_index_matches_aliases -q`
Expected: FAIL — `ImportError: cannot import name 'findBandIndex'`.

- [ ] **Step 3: Implement `findBandIndex` + `loadColumnGeometry`**

Add to `src/varda/image_loading/crism_geometry.py`:

```python
_BAND_ALIASES: dict[str, tuple[str, ...]] = {
    "ir_sample": (
        "ir (l-detector) sample",
        "ir sample",
        "l-detector sample",
        "sample",
    ),
    "target_id": ("target id",),
    "segment_id": ("segment id (counter)", "segment id", "segment"),
}


def findBandIndex(descriptions: tuple[str, ...], kind: str) -> int | None:
    """Return the 1-indexed band whose description matches an alias of ``kind``."""
    aliases = _BAND_ALIASES.get(kind, ())
    lowered = [
        (idx, desc.strip().lower())
        for idx, desc in enumerate(descriptions, start=1)
        if desc
    ]
    for alias in aliases:
        for idx, desc in lowered:
            if alias in desc:
                return idx
    return None


_geometry_cache: dict[str, ColumnGeometry | None] = {}


def loadColumnGeometry(sourceFilename: str) -> ColumnGeometry | None:
    """Resolve and read the DDR geometry for a CRISM source file, or None.

    Results (including None) are cached by source path so repeated placements do
    not re-read the (large) DDR file.
    """
    import rasterio as rio  # local import: keep module import-light

    if sourceFilename in _geometry_cache:
        return _geometry_cache[sourceFilename]

    geomPath = resolveGeometryFile(sourceFilename)
    if geomPath is None:
        _geometry_cache[sourceFilename] = None
        return None
    try:
        with rio.open(geomPath) as geom:
            descs = geom.descriptions or ()
            irIdx = findBandIndex(descs, "ir_sample")
            if irIdx is None:
                logger.warning("DDR %s has no IR Sample band; column-lock unavailable", geomPath)
                _geometry_cache[sourceFilename] = None
                return None
            tgtIdx = findBandIndex(descs, "target_id")
            segIdx = findBandIndex(descs, "segment_id")
            nodata = geom.nodata

            def _read(idx: int | None) -> np.ndarray | None:
                if idx is None:
                    return None
                arr = geom.read(idx).astype(np.float64)
                if nodata is not None:
                    arr = np.where(arr == nodata, np.nan, arr)
                return arr

            result = ColumnGeometry(
                ir_sample=_read(irIdx),
                target_id=_read(tgtIdx),
                segment_id=_read(segIdx),
            )
            _geometry_cache[sourceFilename] = result
            return result
    except Exception as e:  # pragma: no cover - I/O error path
        logger.warning("Failed to read DDR geometry %s: %s", geomPath, e)
        _geometry_cache[sourceFilename] = None
        return None
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest src/varda/image_loading/_tests/test_crism_geometry.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add src/varda/image_loading/crism_geometry.py src/varda/image_loading/_tests/test_crism_geometry.py
git commit -m "feat(crism): load DDR geometry bands by description alias"
```

---

### Task 4: Template badge in `ROITableModel`

**Files:**
- Modify: `src/varda/rois/roi_table_model.py`
- Test: `src/varda/rois/_tests/test_roi_table_model.py`

Mirror the existing denominator badge. The denominator shows a `"÷"` suffix; the template shows a `"⊞"` suffix. Both may be set independently.

- [ ] **Step 1: Write the failing tests**

Append to `src/varda/rois/_tests/test_roi_table_model.py`:

```python
def test_set_template_marks_row(qtbot):
    model = ROITableModel(_collection_with_two())
    fid = model.fidForRow(1)
    model.setTemplateFid(fid)
    assert model.templateFid == fid
    display = model.data(model.index(1, 1), Qt.ItemDataRole.DisplayRole)
    assert "⊞" in display


def test_template_and_denominator_independent(qtbot):
    model = ROITableModel(_collection_with_two())
    model.setDenominatorFid(model.fidForRow(0))
    model.setTemplateFid(model.fidForRow(1))
    assert model.denominatorFid == model.fidForRow(0)
    assert model.templateFid == model.fidForRow(1)
    assert "÷" in model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole)
    assert "⊞" in model.data(model.index(1, 1), Qt.ItemDataRole.DisplayRole)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest src/varda/rois/_tests/test_roi_table_model.py -q`
Expected: FAIL — `AttributeError: 'ROITableModel' object has no attribute 'setTemplateFid'`.

- [ ] **Step 3: Add template state + marker**

In `src/varda/rois/roi_table_model.py`, after `self._denominatorFid: int | None = None` in `__init__`, add:

```python
        self._templateFid: int | None = None
```

In `data()`, replace the Name display branch (which currently appends only the denominator marker):

```python
            if col == 1:
                if roi.fid == self._denominatorFid:
                    return f"{roi.name}  ÷"
                return roi.name
```

with:

```python
            if col == 1:
                suffix = ""
                if roi.fid == self._denominatorFid:
                    suffix += "  ÷"
                if roi.fid == self._templateFid:
                    suffix += "  ⊞"
                return f"{roi.name}{suffix}"
```

Update the existing `FontRole` branch so a template row is bold too:

```python
        if role == Qt.ItemDataRole.FontRole and roi.fid == self._denominatorFid:
            font = QFont()
            font.setBold(True)
            return font
```

becomes:

```python
        if role == Qt.ItemDataRole.FontRole and roi.fid in (
            self._denominatorFid,
            self._templateFid,
        ):
            font = QFont()
            font.setBold(True)
            return font
```

After the existing `setDenominatorFid` method, add the template equivalents:

```python
    @property
    def templateFid(self) -> int | None:
        return self._templateFid

    def setTemplateFid(self, fid: int | None) -> None:
        """Mark the row with this fid as the placement template (or clear)."""
        if fid == self._templateFid:
            return
        self._templateFid = fid
        if self.rowCount() > 0:
            top = self.index(0, 0)
            bottom = self.index(self.rowCount() - 1, self.columnCount() - 1)
            self.dataChanged.emit(top, bottom)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest src/varda/rois/_tests/test_roi_table_model.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/varda/rois/roi_table_model.py src/varda/rois/_tests/test_roi_table_model.py
git commit -m "feat(rois): show template badge in ROI table model"
```

---

### Task 5: "Set/Clear Template" actions in the row context menu

**Files:**
- Modify: `src/varda/rois/roi_table_view.py`
- Test: `src/varda/rois/_tests/test_roi_table_view.py`

- [ ] **Step 1: Write the failing tests**

Append to `src/varda/rois/_tests/test_roi_table_view.py`:

```python
def test_set_template_action_emits(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    menu = view._buildRowMenu(fid)
    with qtbot.waitSignal(view.sigTemplateSetRequested, timeout=500) as sig:
        _find_action(menu, "Set as Template").trigger()
    assert sig.args == [fid]


def test_set_template_disabled_when_already_template(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    model.setTemplateFid(fid)
    menu = view._buildRowMenu(fid)
    assert not _find_action(menu, "Set as Template").isEnabled()


def test_clear_template_disabled_when_none(qtbot):
    view, model = _view()
    menu = view._buildRowMenu(model.fidForRow(0))
    assert not _find_action(menu, "Clear Template").isEnabled()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest src/varda/rois/_tests/test_roi_table_view.py -q`
Expected: FAIL — missing `sigTemplateSetRequested`.

- [ ] **Step 3: Add the signals + menu items**

In `src/varda/rois/roi_table_view.py`, after the existing denominator signals, add:

```python
    sigTemplateSetRequested = pyqtSignal(int)
    sigTemplateClearRequested = pyqtSignal()
```

In `_buildRowMenu`, just before `return menu`, add a separator and the two template items:

```python
        menu.addSeparator()

        setTemplateAction = QAction("Set as Template", menu)
        setTemplateAction.setEnabled(fid != self._roiModel.templateFid)
        setTemplateAction.triggered.connect(
            lambda: self.sigTemplateSetRequested.emit(fid)
        )
        menu.addAction(setTemplateAction)

        clearTemplateAction = QAction("Clear Template", menu)
        clearTemplateAction.setEnabled(self._roiModel.templateFid is not None)
        clearTemplateAction.triggered.connect(
            lambda: self.sigTemplateClearRequested.emit()
        )
        menu.addAction(clearTemplateAction)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest src/varda/rois/_tests/test_roi_table_view.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add src/varda/rois/roi_table_view.py src/varda/rois/_tests/test_roi_table_view.py
git commit -m "feat(rois): add Set/Clear Template actions to ROI row menu"
```

---

### Task 6: Template state + `placeTemplate` on `ROIManagerWidget`

**Files:**
- Modify: `src/varda/rois/roi_manager_widget.py`
- Test: `src/varda/rois/_tests/test_roi_manager_widget.py`

`placeTemplate` is the heart of the feature and is fully unit-testable: it translates the template polygon (in pixel space) to the click, optionally column-locking the horizontal shift, then adds a new ROI in the collection's native coordinate system.

- [ ] **Step 1: Write the failing tests**

Append to `src/varda/rois/_tests/test_roi_manager_widget.py`:

```python
from shapely.geometry import box as _box


def test_set_template_updates_model_and_emits(qtbot, make_split_image):
    c = ROICollection()
    fid = c.addROI(_box(2, 2, 8, 8), "tmpl", RED, ROIMode.RECTANGLE)
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    with qtbot.waitSignal(w.sigTemplateChanged, timeout=500) as sig:
        w.setTemplate(fid)
    assert w.templateFid == fid
    assert w.model.templateFid == fid
    assert sig.args == [fid]


def test_place_template_plain_paste(qtbot, make_split_image):
    # Non-georeferenced collection -> geometries stored in pixel space.
    c = ROICollection()
    tmpl = c.addROI(_box(2, 2, 6, 6), "tmpl", RED, ROIMode.RECTANGLE)  # centroid (4,4)
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    w.setTemplate(tmpl)
    before = len(c)
    w.placeTemplate(clickRow=14, clickCol=20, lockColumn=False)
    assert len(c) == before + 1
    new_fid = c.fids[-1]
    coords = c.getPixelCoordinates(new_fid)
    cx, cy = coords[:, 0].mean(), coords[:, 1].mean()
    # Copy centroid lands at the click (dx = 20-4 = 16, dy = 14-4 = 10).
    assert abs(cx - 20) < 1e-6
    assert abs(cy - 14) < 1e-6


def test_place_template_noop_without_template(qtbot, make_split_image, monkeypatch):
    import varda.rois.roi_manager_widget as mod
    monkeypatch.setattr(mod.QMessageBox, "information", lambda *a, **k: None)
    c = ROICollection()
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    w.placeTemplate(clickRow=5, clickCol=5, lockColumn=False)
    assert len(c) == 0


def test_removing_template_clears_it(qtbot, make_split_image):
    c = ROICollection()
    fid = c.addROI(_box(2, 2, 6, 6), "tmpl", RED, ROIMode.RECTANGLE)
    w = ROIManagerWidget(c, make_split_image(40, 20, 3, 8.0, 4.0), _FakePlot())
    w.setTemplate(fid)
    c.removeROI(fid)
    assert w.templateFid is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest src/varda/rois/_tests/test_roi_manager_widget.py -q`
Expected: FAIL — `AttributeError: 'ROIManagerWidget' object has no attribute 'setTemplate'`.

- [ ] **Step 3: Implement template state + placement**

In `src/varda/rois/roi_manager_widget.py`:

Add imports near the top (with the existing imports):

```python
import numpy as np
from shapely.geometry import Polygon

from varda.image_loading.crism_geometry import (
    computeColumnLockedTranslation,
    loadColumnGeometry,
)
```

(`import numpy as np` already exists — do not duplicate it.)

Add a signal next to `sigDenominatorChanged`:

```python
    sigTemplateChanged = pyqtSignal(object)  # emits fid (int) or None
```

In `__init__`, after `self._denominatorFid: int | None = None`, add:

```python
        self._templateFid: int | None = None
```

Wire the new table signals in `__init__` (next to the existing `self._table.sig... .connect(...)` block):

```python
        self._table.sigTemplateSetRequested.connect(self.setTemplate)
        self._table.sigTemplateClearRequested.connect(lambda: self.setTemplate(None))
```

Extend `_onROIRemoved` so it also clears the template:

```python
    def _onROIRemoved(self, fid: int) -> None:
        if fid == self._denominatorFid:
            self.setDenominator(None)
        if fid == self._templateFid:
            self.setTemplate(None)
```

Add the template property/setter and `placeTemplate` (e.g. after `setDenominator`):

```python
    @property
    def templateFid(self) -> int | None:
        return self._templateFid

    def setTemplate(self, fid: int | None) -> None:
        """Set (or clear, with None) the ROI used as a placement template."""
        if fid == self._templateFid:
            return
        self._templateFid = fid
        self._model.setTemplateFid(fid)
        self.sigTemplateChanged.emit(fid)

    def placeTemplate(self, clickRow: int, clickCol: int, lockColumn: bool) -> None:
        """Stamp a copy of the template ROI centered on the clicked pixel.

        With ``lockColumn`` and a resolvable CRISM DDR, the horizontal shift is
        chosen so the copy sits on the template's detector column; otherwise a
        plain centroid-to-click translation is used.
        """
        if self._templateFid is None:
            QMessageBox.information(
                self,
                "No template set",
                "Right-click an ROI and choose 'Set as Template' first, then "
                "right-click the image to place a copy.",
            )
            return

        template = self._collection.getROI(self._templateFid)
        pixelCoords = self._collection.getPixelCoordinates(self._templateFid)  # (N,2) col,row
        srcCx = float(pixelCoords[:, 0].mean())
        srcCy = float(pixelCoords[:, 1].mean())
        dx = float(clickCol) - srcCx
        dy = float(clickRow) - srcCy

        if lockColumn:
            geometry = loadColumnGeometry(self._image.filePath) if self._image.filePath else None
            if geometry is not None:
                locked = computeColumnLockedTranslation(
                    pixelCoords, clickRow=clickRow, clickCol=clickCol, geometry=geometry
                )
                if locked is not None:
                    dx, dy = locked

        newPixels = pixelCoords + np.array([dx, dy])
        if self._image.hasGeospatialData:
            geoCoords = [
                self._image.pixelToGeo(int(round(c)), int(round(r))) for c, r in newPixels
            ]
            geometry = Polygon(geoCoords)
        else:
            geometry = Polygon(newPixels)

        self._collection.addROI(
            geometry=geometry,
            name=f"{template.name} copy",
            color=template.color,
            roiType=template.roiType,
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest src/varda/rois/_tests/test_roi_manager_widget.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add src/varda/rois/roi_manager_widget.py src/varda/rois/_tests/test_roi_manager_widget.py
git commit -m "feat(rois): template state + placeTemplate (with optional column-lock)"
```

---

### Task 7: app_model viewport context-menu module

**Files:**
- Create: `src/varda/image_rendering/raster_view/viewport_actions.py`

Defines, co-located with the viewport (NOT in `_actions/`): the viewport context-menu id, a transient click-context holder, and the `VIEWPORT_ACTIONS` list whose callbacks are injected by type.

- [ ] **Step 1: Write the failing test**

Create `src/varda/image_rendering/raster_view/_tests/test_viewport_actions.py` (the `_tests` dir already exists here):

```python
"""Tests for the viewport context-menu action module."""

from varda.image_rendering.raster_view import viewport_actions as va


def test_holder_roundtrip():
    va.setCurrentClickContext(None)
    assert va.getCurrentClickContext() is None
    ctx = va.ViewportClickContext(placeTemplate=lambda: None, lockColumn=False, hasTemplate=True)
    va.setCurrentClickContext(ctx)
    assert va.getCurrentClickContext() is ctx
    va.setCurrentClickContext(None)


def test_actions_registered_for_viewport_menu():
    ids = {a.id for a in va.VIEWPORT_ACTIONS}
    assert "varda.viewport.place_template" in ids
    # all actions target the viewport context menu
    for a in va.VIEWPORT_ACTIONS:
        assert any(rule.id == va.VIEWPORT_CONTEXT_MENU_ID for rule in a.menus)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest src/varda/image_rendering/raster_view/_tests/test_viewport_actions.py -q`
Expected: FAIL — `ModuleNotFoundError: ...viewport_actions`.

- [ ] **Step 3: Implement the module**

Create `src/varda/image_rendering/raster_view/viewport_actions.py`:

```python
"""Declarative app_model actions for the raster viewport's right-click menu.

Co-located with the viewport (not in the global ``_actions/`` package): each
subsystem owns its actions. The actions operate on a transient
``ViewportClickContext`` set just before the menu is shown, supplied to callbacks
via the app's injection store (app_model resolves callback args by type).
"""

from __future__ import annotations

from collections.abc import Callable

import attrs
from app_model.types import Action, MenuRule

VIEWPORT_CONTEXT_MENU_ID = "varda/viewport/context"


@attrs.define
class ViewportClickContext:
    """Transient state for the current right-click on a viewport."""

    placeTemplate: Callable[[], None]
    lockColumn: bool
    hasTemplate: bool


_current: ViewportClickContext | None = None


def setCurrentClickContext(ctx: ViewportClickContext | None) -> None:
    global _current
    _current = ctx


def getCurrentClickContext() -> ViewportClickContext | None:
    return _current


def _placeTemplateHere(ctx: ViewportClickContext) -> None:
    ctx.placeTemplate()


VIEWPORT_ACTIONS: list[Action] = [
    Action(
        id="varda.viewport.place_template",
        title="Place template here",
        callback=_placeTemplateHere,
        menus=[MenuRule(id=VIEWPORT_CONTEXT_MENU_ID)],
    ),
]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest src/varda/image_rendering/raster_view/_tests/test_viewport_actions.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/varda/image_rendering/raster_view/viewport_actions.py src/varda/image_rendering/raster_view/_tests/test_viewport_actions.py
git commit -m "feat(viewport): declarative app_model viewport context-menu actions"
```

---

### Task 8: Register viewport actions + click-context provider in the app

**Files:**
- Modify: `src/varda/app.py`

- [ ] **Step 1: Register the actions and the provider**

In `src/varda/app.py`, add the import near the top:

```python
from varda.image_rendering.raster_view.viewport_actions import (
    VIEWPORT_ACTIONS,
    ViewportClickContext,
    getCurrentClickContext,
)
```

In `VardaApplication.__init__`, after `self.register_actions(ALL_ACTIONS)`, add:

```python
        self.register_actions(VIEWPORT_ACTIONS)
        # Provider for the transient viewport right-click context. Called fresh
        # each time an action runs; the controller sets it just before exec.
        self.injection_store.register_provider(
            getCurrentClickContext, ViewportClickContext
        )
```

- [ ] **Step 2: Smoke-check the app constructs (registration is valid)**

Run:
```bash
uv run python -c "from varda.app import VardaApplication; a = VardaApplication(); print('ok', 'varda.viewport.place_template' in a.commands)"
```
Expected: `ok True` (the command id is registered).

- [ ] **Step 3: Commit**

```bash
git add src/varda/app.py
git commit -m "feat(app): register viewport actions + click-context provider"
```

---

### Task 9: Emit a generic context-menu request from the viewport

**Files:**
- Modify: `src/varda/image_rendering/raster_view/image_viewport.py`

The viewport stays generic: on a right-click PRESS that no active tool consumed, it emits `sigContextMenuRequested(imageCol, imageRow, globalPos)`. It does not know what's in the menu.

- [ ] **Step 1: Read the current event handling**

Open `src/varda/image_rendering/raster_view/image_viewport.py` and locate `eventFilter` / `_buildPointerEvent` and where `PointerEvent`s are dispatched to tools (the dispatch returns whether a tool consumed the event). Confirm the class is a `QObject`/widget with `pyqtSignal` available (it already defines signals).

- [ ] **Step 2: Add the signal**

In the `ImageViewport` class signal declarations, add:

```python
    sigContextMenuRequested = pyqtSignal(float, float, object)  # imageCol, imageRow, QPoint(global)
```

- [ ] **Step 3: Emit on unconsumed right-click**

In the mouse-press handling, after the active tool has been given the event and did NOT consume it, add a right-button branch. Concretely, where a press `PointerEvent` is built and dispatched (it currently returns/уses a `consumed` boolean from the tool manager), add:

```python
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QCursor

        if (
            event.action == PointerAction.PRESS
            and event.button == Qt.MouseButton.RightButton
            and not consumed
        ):
            self.sigContextMenuRequested.emit(
                float(event.imagePos.x()), float(event.imagePos.y()), QCursor.pos()
            )
            return True
```

(Adapt the variable names — `event`, `consumed` — to the actual ones in `eventFilter`. The intent: only fire when a right-click press was not already consumed by a drawing tool, so right-click-to-cancel-drawing still works.)

- [ ] **Step 4: Smoke-check the import**

Run:
```bash
uv run python -c "import varda.image_rendering.raster_view.image_viewport as m; print('ok')"
```
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add src/varda/image_rendering/raster_view/image_viewport.py
git commit -m "feat(viewport): emit sigContextMenuRequested on unconsumed right-click"
```

---

### Task 10: Viewport context-menu controller (builds & pops the QModelMenu)

**Files:**
- Create: `src/varda/image_rendering/raster_view/viewport_context_menu_controller.py`

Owns the "Lock to sensor column" toggle state, listens to a viewport's `sigContextMenuRequested`, sets the transient click context, and pops the app_model menu. This is the bridge that keeps template logic out of the viewport.

- [ ] **Step 1: Implement the controller**

Create `src/varda/image_rendering/raster_view/viewport_context_menu_controller.py`:

```python
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

    def __init__(self, roiManager: ROIManagerWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._roiManager = roiManager
        self._lockColumn = False

    def setLockColumn(self, enabled: bool) -> None:
        self._lockColumn = enabled

    @property
    def lockColumn(self) -> bool:
        return self._lockColumn

    def onContextMenuRequested(self, imageCol: float, imageRow: float, globalPos: QPoint) -> None:
        app = Application.get_app("varda")
        if app is None:
            logger.warning("No 'varda' app instance; cannot show viewport menu")
            return

        def _place() -> None:
            self._roiManager.placeTemplate(
                clickRow=int(round(imageRow)),
                clickCol=int(round(imageCol)),
                lockColumn=self._lockColumn,
            )

        setCurrentClickContext(
            ViewportClickContext(
                placeTemplate=_place,
                lockColumn=self._lockColumn,
                hasTemplate=self._roiManager.templateFid is not None,
            )
        )
        try:
            menu = QModelMenu(VIEWPORT_CONTEXT_MENU_ID, app)
            menu.exec(globalPos)
        finally:
            setCurrentClickContext(None)
```

- [ ] **Step 2: Smoke-check the import**

Run:
```bash
uv run python -c "import varda.image_rendering.raster_view.viewport_context_menu_controller as m; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/varda/image_rendering/raster_view/viewport_context_menu_controller.py
git commit -m "feat(viewport): controller to pop app_model context menu on right-click"
```

---

### Task 11: Wire the controller + lock toggle into the workspace

**Files:**
- Modify: `src/varda/workspaces/general_image_analysis/general_image_analysis.py`

- [ ] **Step 1: Construct the controller and connect each viewport**

In `general_image_analysis.py`, after `self.roiManagerWidget = ROIManagerWidget(...)` is created, add:

```python
        from varda.image_rendering.raster_view.viewport_context_menu_controller import (
            ViewportContextMenuController,
        )

        self.viewportContextMenuController = ViewportContextMenuController(
            self.roiManagerWidget, parent=self
        )
        for vp in (
            self.tripleRasterView.viewport1,
            self.tripleRasterView.viewport2,
            self.tripleRasterView.viewport3,
        ):
            vp.sigContextMenuRequested.connect(
                self.viewportContextMenuController.onContextMenuRequested
            )
```

- [ ] **Step 2: Add a "Lock to sensor column" toggle, disabled without DDR**

Add a checkable toolbar/checkbox control near the ROI manager. In `_initData` (or where UI controls are built), after the controller exists:

```python
        from PyQt6.QtWidgets import QCheckBox
        from varda.image_loading.crism_geometry import resolveGeometryFile

        self.lockColumnCheck = QCheckBox("Lock to sensor column")
        image = self.config.image.value
        hasDdr = bool(image.filePath) and resolveGeometryFile(image.filePath) is not None
        self.lockColumnCheck.setEnabled(hasDdr)
        if not hasDdr:
            self.lockColumnCheck.setToolTip("No CRISM DDR geometry found for this image")
        self.lockColumnCheck.toggled.connect(
            self.viewportContextMenuController.setLockColumn
        )
```

Add `self.lockColumnCheck` to the ROI dock layout (place it above or below `self.roiManagerWidget` in the dock — follow the existing dock-construction pattern in `_setupDocks`; e.g. wrap the manager + checkbox in a `QWidget`/`QVBoxLayout` and set that as the ROI dock widget).

- [ ] **Step 3: Smoke-check the import**

Run:
```bash
uv run python -c "import varda.workspaces.general_image_analysis.general_image_analysis as m; print('ok')"
```
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add src/varda/workspaces/general_image_analysis/general_image_analysis.py
git commit -m "feat(workspace): wire viewport context menu + column-lock toggle"
```

---

### Task 12: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Format + lint the touched areas**

```bash
uv run ruff format src/varda/image_loading src/varda/rois src/varda/image_rendering/raster_view src/varda/workspaces src/varda/app.py
uv run ruff check src/varda/image_loading/crism_geometry.py src/varda/rois src/varda/image_rendering/raster_view/viewport_actions.py src/varda/image_rendering/raster_view/viewport_context_menu_controller.py
```
Fix any issues in the files this plan touched.

- [ ] **Step 2: Type-check the new/changed logic modules**

```bash
uv run ty check src/varda/image_loading/crism_geometry.py src/varda/rois/roi_manager_widget.py src/varda/rois/roi_table_model.py src/varda/rois/roi_table_view.py src/varda/image_rendering/raster_view/viewport_actions.py
```
Fix any NEW errors introduced by this plan (pre-existing diagnostics elsewhere may remain).

- [ ] **Step 3: Run the full relevant test suites**

```bash
uv run pytest src/varda/rois src/varda/image_loading -q
```
Expected: PASS (all, including the new CRISM-geometry, template-badge, template-menu, and placeTemplate tests).

- [ ] **Step 4: Commit any fixups**

```bash
git add -A -- src/varda
git commit -m "chore: formatting and type-check fixups for ROI templating"
```
(Skip if nothing changed.)

---

### Task 13: Manual GUI verification

**Files:** none (manual — the user performs this)

- [ ] **Step 1: Exercise templating on a CRISM image with a DDR present**

Run the app, open a General Image Analysis workspace, then:
1. Draw an ROI. Right-click its row → **Set as Template** → row shows a `⊞` badge.
2. Right-click on the image → **Place template here** → a copy named `"<name> copy"` appears at the click.
3. Enable **Lock to sensor column** (enabled only if a DDR companion resolves). Place again at a different row → the copy snaps to the template's detector column rather than the click's column.
4. Right-click with no template set → an info dialog, no crash.
5. On a non-CRISM image (e.g. a GeoTIFF), confirm **Lock to sensor column** is disabled and "Place template here" still does a plain paste.
6. Right-click while a drawing tool is mid-draw → still cancels the draw (context menu does not hijack it).
