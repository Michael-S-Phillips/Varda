# Lessons from napari, astropy, Spectral Python and WISER — Design

**Date:** 2026-10-13
**Status:** Proposed. Michael picks which items go to implementation plans. Don't start an item without his go-ahead.
**Source study:** four codebases, each read at a fixed commit and compared with Varda at `3214f92`:

| Project | Commit |
|---|---|
| napari | `012ee84` |
| astropy | `fb41ce6` |
| Spectral Python (SPy) | `7096411` |
| WISER (Ehlmann group) | `bb96c9c` |

The readable write-up is a separate Claude Doc. This file is the actionable version.

**How to use this:**

- Each item below says what to change and why, citing the comparison project.
- Each item names the Varda files involved and gives an acceptance check.
- Line numbers are from `3214f92` and may have drifted, so confirm each finding in the current code before acting on it.
- Effort: **S** = a few days, **M** = one to two weeks.

---

## A. Quick fixes (bugs found during the study) — S each

1. **User plugins never load.**
   - `plugins/plugin_manager.py:36` reads `if getattr(sys, "frozen", True): return`. The default should be `False`, so `user_plugins/` is skipped even when running from source.
   - *Check:* a test plugin in `user_plugins/` gets its `onLoad` called when not frozen.
2. **Session version is never checked.** `session.py` writes `"version": _VERSION`, but nothing reads it when loading.
   - Refuse files newer than the app can read, with a clear message.
   - Add a migration hook for older versions (see D3).
   - *Check:* tests for a too-new file and a current file.
3. **Dead `eval()`.** Delete the unused `eval()` path in `utilities/roi_utils/roi_functions.py` (around lines 206–252). Calculated columns already use the safe AST evaluator in `rois/roi_calculations.py`.
4. **Hourglass "Suggest" help text is wrong.** It says k-means (`endmember_table.py:76`, `pipeline_panel.py:324`), but `analysis/endmembers.py:suggestGroups` uses ATGP plus a radius. Fix the text, or implement k-means (see C3).
5. **Logging setup on import.** `log.py` calls `logging.basicConfig(level=DEBUG, ...)` at import, which turns on DEBUG output from every library.
   - Configure a named `varda` logger instead, and set third-party loggers to WARNING.
6. **Two classes named `VardaRaster`** (`common/entities.py:38` and `image_loading/varda_raster.py:33`). Rename or merge them so there is one.
7. **Half-pixel offset.**
   - `RasterioDataSource.pixelToGeo` uses `src.xy(row, col)`, which returns pixel centers.
   - `ArrayDataSource.pixelToGeo` (`array_data_source.py:192`) and the HDF5 source use `transform * (col, row)`, which returns pixel corners.
   - Every analysis result is an `ArrayDataSource`, so derived rasters are half a pixel off from their source image.
   - Choose one convention (pixel centers, as astropy and rasterio do), state it in the `DataSource` protocol docstring, and apply it everywhere.
   - *Check:* a round-trip test that `pixelToGeo` on a source image and on its derived raster return the same coordinate for the same pixel.

## B. Scientific correctness — highest value for users

1. **Make the spectral axis explicit (M).** From astropy (units as data), SPy (`BandInfo` with FWHM; ENVI `bbl` and `reflectance scale factor`) and WISER (units, bad bands and no-data honored throughout).
   - Today the declared `wavelengthUnits` is ignored in calculations, and four separate heuristics guess units from value size:
     - `analysis/spectral_library.py:98`
     - `analysis/hypyrameter_adapter.py:33`
     - `plotting/spectrum_matching.py:14`
     - `workspaces/spectral_hourglass/pipeline_panel.py:62`

     The "below 10 means µm" rule mislabels thermal-IR libraries, and images with 10 bands or fewer and no wavelengths have their band indices read as µm. Spectral Slope's nm defaults select no bands on µm images, and Spectral Derivative is labeled "per nm" on µm axes.
   - Add a small band model (attrs) carrying:
     - centers in a canonical unit plus the declared unit
     - FWHM
     - a bad-band mask
     - a scale factor
     - a no-data value
   - Parse unit strings once, in the readers. Use one normalizer everywhere and delete the four heuristics.
   - Treat `bbl == 0` bands as NaN in `analysis/rasters.py:readCube`. Log the float64 promotion and any band interpolation instead of doing them silently.
   - Carry the band model into derived rasters, and write `fwhm`, `bbl` and `data ignore value` on ENVI export (`image_loading/raster_writer.py`). Don't write `wavelength` for non-spectral products.
   - A small in-house unit table is enough for now. Never wrap whole cubes in `astropy.units.Quantity`.
   - *Check:* unit tests for nm, µm and wavenumber inputs; a µm image gives the same Spectral Slope result as its nm twin.
   - Results of existing analyses may change, so say so in the release notes.
2. **Validate against ENVI (M).** From WISER's `tests/test_mtmf.py::test_mtmf_matches_envi_ground_truth` and its `*_envi_gt` fixtures.
   - Commit tiny test cubes with ENVI reference outputs for PCA, MNF, SAM, FCLS, MTMF and continuum removal, with stated tolerances. For PPI, compare a seeded run or count rankings.
   - Put these in a new `analysis/_tests/test_ground_truth.py`. **[Michael]** needs one-time ENVI access to produce the references.
   - Later, publish a "validated against ENVI" table in the docs.
3. **ENVI reader test matrix, with SPy as the reference (S).**
   - Use `spectral.io.envi.save_image` / `create_image` to write fixtures across:
     - interleave (BSQ, BIL, BIP)
     - byte order
     - data type
     - header offset
     - data-file extensions (`.img`, `.dat`, `.raw`, none)
     - mixed-case keys
     - multi-line braces
     - `fwhm`, `bbl`, integer and float `data ignore value`, scale factor
   - Open each with `openDataSource` and compare the values with SPy's `open_memmap()`.
   - Varda has no direct `ENVIDataSource` tests today. Put them in `image_loading/data_sources/_tests/test_envi_data_source.py`.
4. **Fix ENVI data-file discovery (S).**
   - `envi_data_source.py:32` finds the data file with `filePath.replace(".hdr", ".img")`. That breaks `.HDR`, `foo.img.hdr`, data files named `.dat`, `.raw` or `.bin`, data files with no extension, and any directory name containing `.hdr`.
   - Search the way SPy does (`spectral/io/envi.py`, `KNOWN_EXTS`): try `''`, `img`, `dat`, `sli`, `hyspex`, `raw`, `bin` and the interleave extension, in both cases.
   - Route `.dat`, `.raw`, `.bin`, `.bsq`, `.bil` and `.bip` to the ENVI source when a sibling `.hdr` exists.
   - Covered by B3's matrix.
5. **Identify files by content, not extension (S–M).** From astropy's `io/registry` (content identification, priorities, an error when a file matches two formats) and WISER's `raster/format_registry.py` (`identify()` returns YES, MAYBE or NO, with a GDAL fallback at the lowest priority).
   - `image_loading_service.py:openDataSource` takes the first extension match, so PDS3 and CRISM `.IMG` files go to the ENVI reader.
   - Add a `canOpen(path)` check to each registered source in `data_sources/registry.py`. For example, ENVI needs a sibling `.hdr`, and PDS checks for `PDS_VERSION_ID`.
   - When more than one source claims a file, ask once and remember the choice (napari's reader dialog).

## C. Analyses worth adding

1. **Band math (M).** Following WISER's `bandmath/` design:
   - a safe grammar instead of `eval`
   - output type and shape checked before any data is read, with a memory estimate
   - evaluation in chunks
   - saved expressions

   Grow it from the safe AST evaluator in `rois/roi_calculations.py` into a new `analysis/band_math.py` registered in `analysis/registry.py`. Add wavelength-aware band references such as `R2300`, meaning the band nearest 2300 nm.
2. **SPy-backed detectors and resampling (S–M each).** Put every SPy call behind one adapter module, for example `analysis/_spy.py`. When it imports SPy, it should:
   - strip SPy's log handler (added at import)
   - set `settings.show_progress = False`
   - never use SPy's PySide6 viewers

   Pin `spectral>=0.24,<0.26`. Then add:
   - **FWHM-aware library resampling** with `spectral.resampling.create_resampling_matrix`, applied in a way that ignores NaN. This replaces the linear interpolation in `analysis/spectral_library.py:176-184`, and should use the library's declared band unit. Don't use SPy's `create_envi_spectral_library`, whose unit labels are buggy.
   - **RX, ACE and matched-filter detectors** in a new `analysis/detection.py`. Run SPy's vectorized global versions on `flattenValid` output in row blocks, so `reportProgress` and cancellation keep working. Write local-window RX in Varda, because SPy's loops pixel by pixel.
3. **Classifiers (M).** Add Gaussian maximum likelihood, Mahalanobis and k-means through SPy (`classifiers.py`, `clustering.py`). SPy silently drops ROI classes with fewer samples than bands, which is most ROIs on 400-band CRISM data. Run on MNF-reduced data, or raise a clear error.
4. **MNF noise options (S).** Varda estimates noise only from horizontal differences (`linear_algebra.py:155`). Offer vertical, diagonal and averaged differences, or a user-chosen homogeneous ROI (`spectral/algorithms/algorithms.py:noise_from_diffs`). Keep the current default.
5. **Display defaults (S each):**
   - default bands chosen as true color from wavelengths (WISER's `find_display_bands`; today `rasterio_data_source.defaultBands` returns `[0, 1, 2]`)
   - histogram-equalization, square-root and log stretches (WISER's `raster/stretch.py`)
   - publication-quality spectrum plot export to PNG, SVG, PDF and CSV
   - a continuum-removed image product

## D. Speed and architecture

1. **Separate reading data from stretching it (S–M).**
   - Any setting change in `image_rendering/image_renderer.py:render()` clears the cache and re-reads full-resolution bands.
   - `raster_view/image_region_item.py:144` bakes the stretch into 8-bit (`levels=(0, 255)`); the line above it is a commented-out `levels=self._stretch.toList()`.
   - Keep the raw bands cached until the band selection changes, and apply the stretch through pyqtgraph levels and lookup tables.
   - Sample before computing percentiles (`stretch_algorithms.py:360` has the subsample commented out).
   - This follows napari's `_vispy/layers/image.py` and `layers/utils/layer_utils.py:calc_data_range`.
2. **Read what the screen needs (M).**
   - Add an `outShape` option to `DataSource.getData` and `getBands`, using rasterio's `out_shape`, which uses GDAL overviews. Fold the scale into the item's `QTransform`, and keep `getPixelSpectrum` at full resolution.
   - Stop wrapping every source in `InMemoryDataSource` (`image_loading_service.py:324`). Read lazily, with a small cache for recent renders. Test that the cache actually returns stored items; WISER's caches never store anything because of a bug.
3. **Durable sessions and provenance (S–M).**
   - Add version migrations (after A2).
   - Add a "save self-contained" option that zips ENVI sidecar files for results that exist only in memory.
   - Record each result's analysis, parameters, inputs and Varda version (napari's `layers/_source.py`, WISER's `run_history.py`). Write the same record into the ENVI header `description` on export.
4. **Enforce the GUI/logic split (S, then M).**
   - Add import-linter contracts that forbid PyQt6 in `data_sources`, `analysis`, `rois.roi_collection`, `points` and `hourglass_model`, starting from an allowlist of today's violations: `QColor` in `entities.py`, `Analysis(QObject)`, `stretch_algorithms.py` and `image_renderer.py`.
   - Add a CI test job that runs without a display.
   - Then split `common/parameter.py` into state built on psygnal and a separate Qt widget factory.
   - Drop the unused dependencies `qtpy`, `pydantic` and `numpydantic` after confirming they're unused.
5. **One background-work model (M).**
   - Replace the separate worker helpers (`utilities/tasks.py`, `threading_helper.py`, `analysis/runner.py`, `spectral_hourglass/task_runner.py`, `image_loading_service.py`) with superqt's `thread_worker` and `ensure_main_thread`, using one worker where the newest request wins for rendering.
   - Rasterio file handles aren't thread-safe: use one handle per worker, or a lock.

## E. Project credibility (overlaps the varda-app spec)

Covered in `2026-10-13-varda-app-org-pypi-website-design.md`: the license, keeping package data inside the package, the single-source version, and the publish workflow. Beyond that:

1. Add `CITATION.cff` (validated in CI, as napari and astropy do) and a Zenodo DOI per release, `CONTRIBUTING.md`, a code of conduct, and issue and PR templates.
2. Add a **Help** menu (new `MenuID.HELP` in `_actions/`) with:
   - About, showing the version from package metadata
   - Cite Varda
   - Copy System Info
   - Open documentation
3. Have the packaged app test itself in `build.yml` before release (WISER's `--smoke` and `--test_mode`). Later, sign and notarize the macOS build and sign the Windows build. The README's `xattr` workaround undermines trust.
4. Make deprecation warnings visible: give each one a `since=` version, and turn `error::DeprecationWarning:varda` into a test error. Keep a changelog.

## Keep what's already ahead

These are strengths. Don't rewrite them toward the comparison projects:

- CRS-aware ROIs (`rois/roi_collection.py`)
- the Spectral Hourglass workflow (PPI, the n-D visualizer, Identify, mapping)
- Varda's numerics (eigh, NaN-aware, chunked), which are better than SPy's
- FCLS and MTMF
- the isolated PyTorch install
- session autosave
- the app-model menus with dependency injection
- a codebase about half WISER's size

## Don't copy

- napari's three overlapping event systems, its 2,000-line base classes, and its support for multiple Qt bindings
- WISER's 9,000-line scheduler and storage service
- astropy's uncertainty propagation and its formal enhancement-proposal process
- WISER's code itself: it is GPL-3, and copying it would make Varda GPL-3
