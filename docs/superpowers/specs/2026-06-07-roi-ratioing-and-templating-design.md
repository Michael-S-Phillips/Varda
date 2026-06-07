# ROI Ratioing & Column-Locked Templating — Design

**Date:** 2026-06-07
**Status:** Approved (design)
**Phasing:** Phase 1 (ROI ratioing) goes to an implementation plan now. Phase 2
(template + column-lock + the viewport context-menu capability) is designed here
but stays design-only until greenlit.

## Background

Varda is a PyQt6 hyperspectral/multispectral viewer. This feature ports two
capabilities from the SCAT prototype (`SCAT/scat.py`, a ~6.7k-line Tkinter
monolith) into Varda in a clean, modular form:

1. **ROI ratioing** — plotting one ROI's mean spectrum divided by a reference
   ("denominator") ROI's mean spectrum.
2. **ROI templating with same-sensor-column placement** — marking an ROI as a
   template and stamping copies of it elsewhere on the image, optionally snapped
   to the same detector columns using CRISM geometry metadata.

### Scientific model (the shared foundation)

A **ratio spectrum** is the element-wise division of one ROI's mean spectrum by a
reference ROI's mean spectrum:

```
ratio[band] = numerator_mean[band] / denominator_mean[band]
```

For CRISM, the reference ("denominator") should be a spectrally *bland* region
drawn from the **same detector columns** as the target, so that
column-correlated instrument artifacts and atmospheric/photometric effects
cancel, leaving real mineral absorption features. There is exactly **one** active
denominator at a time. Column-locked templating (Phase 2) exists to place that
denominator in the same columns as the target — which is why the two features
are one workflow:

> draw target ROI → stamp a same-column copy over a bland area → mark it the
> denominator → plot the ratio.

### How SCAT does it (reference)

- **Ratio math:** `ratio_polygon_spectra()` (`scat.py:4610`) divides each
  polygon's mean spectrum by `self.polygon_spectra[self.denominator_index]`.
  Means come from a NaN/sentinel-aware average over a rasterized polygon mask
  (`_nanmean_over_mask`, `scat.py:43`; CRISM valid range clipped to 0–1.5).
- **Denominator selection:** a radio-style "Denominator" checkbox column in the
  polygon table (`scat.py:2818`).
- **Template:** a "Template" checkbox marks one polygon (`scat.py:2830`);
  right-click on the canvas (`on_right_press`, `scat.py:2172`) stamps a copy
  translated by the centroid→click delta.
- **Column-lock:** `_compute_column_lock_dx()` (`scat.py:3056`) reads a CRISM DDR
  geometry companion file (resolved by filename pattern, e.g. `_mrral_`→`_mrrde_`,
  `scat.py:124`) exposing per-pixel *IR Sample* (detector column), *Target ID*
  and *Segment ID* (strip identity) bands, located by rasterio band
  *descriptions*. It finds, at the destination row and within the same
  target+segment strip, the pixel whose IR Sample is closest to the template's
  mean, and returns the resulting horizontal shift.

## Existing Varda seams (verified)

- `ROICollection` (`src/varda/rois/roi_collection.py`) is the GUI-free source of
  truth (GeoPandas-backed, psygnal signals). It already exposes
  `getROIStatistics(fid, image)`, `getMeanSpectrum`, `getMask`, `getROI`,
  `setProperty`/`addColumn`, and `fromImage`.
- `VardaPlotWidget` (`src/varda/plotting/plot.py`) plots curves
  (`plot(x, y, color, name)`, `plotWithFill`, `getPlottableWavelengths`).
- Today the **workspace** computes and plots ROI spectra: `_onPlotRequested`
  (`src/varda/workspaces/general_image_analysis/general_image_analysis.py:236`)
  calls `getROIStatistics` and `plotWidget.plot(...)`, wired via
  `roiManagerWidget.sigPlotRequested`. This couples plotting logic into the
  workspace and would have to be duplicated per workspace — Phase 1 moves it out.
- `ROITableView` (`src/varda/rois/roi_table_view.py`) currently has only a
  *header* context menu; no row context menu exists yet.
- `VardaRaster` wraps a `DataSource`; the original file path survives the
  in-memory load via `_dataSource.filePath` (`InMemoryDataSource` delegates it),
  but there is no public accessor yet.
- `app_model` is already in use: `VardaApplication(Application)`
  (`src/varda/app.py`) holds the command/menu/keybinding registries plus a
  dependency `injection_store` (callbacks receive args by type). Actions are
  declared as `Action(id, title, callback, enablement, menus=[MenuRule(...)])`
  and currently centralized in `src/varda/_actions/`. `app_model.backends.qt`
  provides `QModelMenu`, which builds a `QMenu` from a `MenuId` — the same
  mechanism Napari uses for context menus.

## Architectural decisions

- **A — Plotting + denominator state live in `ROIManagerWidget`, not the
  workspace.** The workspace's only job is to hand the widget references
  (the image and the plot widget). This keeps the logic in one self-contained,
  reusable place rather than duplicated across workspaces.
- **B — Two different context menus.** The ROI *table* menu (Phase 1) is a plain
  `QMenu` inside `ROIManagerWidget` (it operates on the selected row, which the
  widget already owns). The *viewport* menu (Phase 2) is built declaratively with
  `app_model` + `QModelMenu`, so template-placement logic is not hardcoded into
  the generic viewport.
- **C — CRISM specifics stay in one isolated module** (YAGNI). No general
  "sensor geometry provider" protocol until a second instrument needs one.
- **D — Actions are co-located with their subsystem**, not dumped in a global
  `_actions/` directory. Subsystems export an `*_ACTIONS` list; the app
  aggregates them at startup. Viewport actions live under
  `image_rendering/raster_view/`.

---

## Phase 1 — ROI Ratioing (build now)

### 1. Pure ratio math (Qt-free, unit-tested)

- New `src/varda/rois/ratio.py`:
  ```python
  def computeRatioSpectrum(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray
  ```
  Element-wise division. Where `denominator == 0`, or either operand is `NaN`,
  the result is `NaN`. No warnings, no exceptions (use masked / `np.errstate`
  handling). Returns an array the same shape as the inputs.
- New method on the (GUI-free) collection:
  ```python
  ROICollection.getRatioSpectrum(numeratorFid, denominatorFid, image) -> Spectrum
  ```
  Fetches both mean spectra via the existing stats path and calls
  `computeRatioSpectrum`. Returns a `Spectrum` (ratio values + wavelengths).

### 2. `ROIManagerWidget` owns plotting + denominator state

- Constructor gains `image: VardaRaster` and `plotWidget: VardaPlotWidget`
  references, provided by the workspace.
- Holds `_denominatorFid: int | None`; emits `sigDenominatorChanged(object)`.
- Methods (the logic currently in the workspace's `_onPlotRequested` moves here):
  - `plotSpectrum(fid)` — mean spectrum, as today (`plot(wavelengths, mean,
    color=roi.color, name=roi.name)`); skips empty ROIs.
  - `setDenominator(fid | None)` — updates state, emits the signal.
  - `plotRatioSpectrum(fid)` — if no denominator is set, show a brief inline hint
    and no-op. Otherwise compute via `getRatioSpectrum` and plot a plain line
    named `"{numerator.name} / {denominator.name}"` in the numerator's color.
    Optional: a faint horizontal reference line at y = 1.0.
- The existing "Plot Spectrum" button calls `plotSpectrum(selectedFid)`.

### 3. Plain table row context menu

- Right-clicking an ROI row in `ROITableView` pops a plain `QMenu`:
  **Plot Spectrum**, **Plot Ratio Spectrum**, **Set as denominator** (checkable,
  reflecting current state), **Clear denominator**. Items are wired to the
  `ROIManagerWidget` methods above. (The existing header context menu is
  unchanged.)

### 4. Denominator badge in the table

- `ROITableModel` is told the current denominator fid (the manager pushes it on
  `sigDenominatorChanged`) and marks that row with a distinct decoration (e.g. a
  "÷" icon and/or bold text) via the model's decoration/display role. No new
  column.

### 5. Workspace gets thinner

- `general_image_analysis.py` constructs
  `ROIManagerWidget(collection, image, plotWidget)` and **removes**
  `_onPlotRequested` and the `sigPlotRequested` connection. The workspace only
  wires references together. Any future workspace gets ratioing for free by
  passing the same references.

### Phase 1 testing

- **Unit (GUI-free):**
  - `computeRatioSpectrum` — normal division, divide-by-zero → NaN, NaN operands
    propagate, shape preserved.
  - `ROICollection.getRatioSpectrum` — small synthetic `InMemoryDataSource` with
    two ROIs; assert ratio equals `mean_a / mean_b`.
- **Manual GUI:** draw two ROIs, set one as denominator (badge appears),
  Plot Spectrum and Plot Ratio Spectrum from the row menu, Plot Ratio with no
  denominator set (hint, no crash).

---

## Phase 2 — Template + Column-Lock (design only for now)

### 1. Modular viewport context menus via `app_model`

- New `src/varda/image_rendering/raster_view/viewport_actions.py` exporting a
  `VIEWPORT_ACTIONS: list[Action]` list and a `MenuId.VIEWPORT_CONTEXT`. **Not**
  in `_actions/`.
- The raster view's right-click handler builds
  `QModelMenu(MenuId.VIEWPORT_CONTEXT, app)` and pops it up at the cursor. The
  viewport stays generic: it knows "show the viewport context menu," not its
  contents.
- Transient click context (pixel coordinates, current image, ROI collection,
  template fid) is made available to action callbacks via a
  stash-before-popup provider registered on the `injection_store` (the Napari
  pattern), since `app_model` injects callback args by type and click position is
  transient.

### 2. Co-located action registration

- Establish the pattern: subsystems export `*_ACTIONS` and the app aggregates
  them at startup, instead of centralizing in `_actions/`.
- Optional exemplar cleanup (sets the pattern Phase 2 follows): move
  `WORKSPACE_ACTIONS` next to the workspaces package.

### 3. Isolated CRISM geometry module

- New `src/varda/image_loading/crism_geometry.py`:
  - `resolveGeometryFile(sourcePath) -> Path | None` — filename-pattern map
    (`_mrral_`→`_mrrde_`, per-strip `_if###x_`→`_in###x_`, etc.).
  - `loadColumnGeometry(sourcePath) -> ColumnGeometry | None` — reads
    *IR Sample / Target ID / Segment ID* bands located by rasterio band
    *descriptions* (alias matching), applies nodata→NaN, caches by path.
  - `computeColumnLockedTranslation(templatePolygonPixels, clickRowCol,
    geometry) -> tuple[float, float]` — at the destination row, restrict to the
    template's strip (matching target+segment), pick the column whose IR Sample
    is closest to the template's mean, return `(dx, dy)`.
  - Unit-testable with synthetic arrays.
- Add a public `VardaRaster.filePath` property delegating to
  `_dataSource.filePath`, so the module can locate the companion file.

### 4. Placement + lock toggle

- "Set as template" (ROI table context menu) tracks a `templateFid`.
- "Place template here" (viewport action) copies the template polygon translated
  to the click location. Math runs in **pixel space** (convert via
  `geoToPixel`/`pixelToGeo`; store back in the collection's native CRS), then
  adds the new ROI through `ROICollection`.
- A checkable **"Lock to sensor column"** action. With lock on, `dx` comes from
  `computeColumnLockedTranslation`; off, it's a plain centroid→click delta. When
  no CRISM geometry resolves for the current image, the toggle is
  disabled/no-op with a hint.

### Phase 2 testing

- **Unit:** `resolveGeometryFile` (filename patterns, missing companion);
  `computeColumnLockedTranslation` (synthetic IR Sample / Target / Segment grids,
  including the wrong-strip rejection case).
- **Manual GUI:** mark a template, stamp copies with lock off and on, verify
  same-column snapping on a real CRISM cube, and graceful behavior on a
  non-CRISM image.

---

## Out of scope / non-goals

- Persisting the denominator or template selection to the saved ROI file (kept as
  runtime analysis state for now).
- A general multi-instrument sensor-geometry abstraction.
- Per-numerator denominators (single global denominator only).
- Std-deviation fill band on ratio plots (std-of-ratio is not well defined from
  mean/std alone).
- Keyboard shortcuts for the new actions.

## Open questions (resolve at Phase 2 detailed-design time)

- Where `templateFid` lives (likely `ROIManagerWidget`, mirroring the
  denominator) and how the viewport action reads it without over-coupling.
- Exact look of the denominator badge.
