# Mosaicking workspace — Design

Status: approved 2026-10-15, with Michael's additions (SNR band selection, aesthetic options, a clean-room COSI-Corr re-implementation). Phase 1 merged (#155); phase 2 automatic alignment (tie points, refinement, RANSAC, displacement field) built; polynomial and TPS warps next.

## The idea

A **Mosaic workspace** combines overlapping images into one: grayscale (Mars
CTX, HiRISE) or spectral cubes (CRISM, hundreds of bands).

- **Alignment:** automatically, with data-driven matching, or by hand
  (nudging and tie points), with transforms from translation to rubber
  sheeting.
- **Radiometric reconciliation:** the user chooses a method.
- **Seams:** chosen between the images, and recorded.

It works on every platform with Varda's own dependencies. Where the Ames Stereo
Pipeline (ASP) or ISIS is installed, or ASP is downloaded as an optional
extra, they add stronger matching and camera-aware tools.

## What the research says

Three research passes (ASP and ISIS; COSI-Corr and alignment options;
mosaicking methods). Sources are listed at the end.

1. **ASP helps but cannot be the only path.**
   - `image_align` fits translation, rigid, similarity, affine or homography
     on plain map-projected GeoTIFFs. It needs no camera models.
   - ASP reads only the first band, so spectral cubes need "fit on one band,
     apply to all".
   - There are no native Windows builds of ASP or ISIS (WSL only).
   - Stable 3.7.0 ships as self-contained tarballs of 260–650 MB for macOS
     (arm64 and x86_64) and Linux, under Apache-2.0.
   - Camera-based steps (`mapproject`, `bundle_adjust`, `cam2map`) need ISIS
     and ISISDATA (40 GB or more).
2. **COSI-Corr can't be shipped, but its method can be re-implemented.**
   - The original is free for non-commercial academic use only.
   - The open re-implementation (geoCosiCorr3D) has the same license
     restriction, and its correlator is a prebuilt Linux binary.
   - The published algorithm (Leprince et al. 2007) is about 150 lines of
     numpy: phase correlation with raised-cosine windows, then a phase-plane
     fit with frequency masking and an SNR per measurement. It reaches about
     1/20–1/50 px.
3. **scikit-image covers the built-in tier.**
   - `phase_cross_correlation` gives masked, sub-pixel offsets.
   - ORB and SIFT handle large rotation or scale differences.
   - `measure.ransac` works with Euclidean, Similarity, Affine, Projective,
     Polynomial, PiecewiseAffine and ThinPlateSpline models.
   - `warp` resamples.
   - OpenCV (about 45–60 MB) and kornia (needs PyTorch) are worth offering
     only as optional extras.
4. **Science mosaics don't blend spectra.**
   - ENVI warns that color balancing and feathering "alter the data values".
   - The CRISM map-tile pipeline and the CTX global mosaic use hard
     seamlines with a quality order, plus documented per-band linear
     corrections.
   - Feathering mixes two spectra; pyramid blending can create values found
     in neither source.

## Principles

- **Non-destructive.** The mosaic is a *recipe*: inputs, transforms, tie
  points, radiometric coefficients and seams. The output is rendered only on
  export, so every decision stays editable and every pixel can be traced back
  to its source.
- **Spectral fidelity by default.** The defaults are nearest-neighbor
  resampling, hard seams and no radiometric change. Anything that changes
  values is opt-in, says so in the dialog, and is recorded in provenance.
  Blending is offered for browse and visual products and labeled as such.
- **Works everywhere; extras accelerate.** Every step has a built-in
  implementation. ASP, ISIS, OpenCV and kornia are used when present, and
  never required.
- **Logic without Qt.** The model and algorithms live in a Qt-free
  `mosaicking/` package covered by the import contract, so they're
  unit-tested headless, as the Spectral Hourglass model is.

## The workspace

Workspace → New Mosaic Workspace…: pick two or more images from the project.

| Area | Contents |
|---|---|
| **Inputs** (left) | The image stack in priority order (drag to reorder; top wins in overlaps). Each image has visibility, opacity, band for display, and a status (aligned, residual RMS, radiometry applied). |
| **Canvas** (center) | All inputs drawn on the target map grid. Comparison views for the selected pair: **blink**, **swipe**, **difference** and **checkerboard**. Tie points drawn as numbered pairs; seams drawn as lines. |
| **Steps** (right) | Pipeline pages, as in the Spectral Hourglass: **Grid → Align → Radiometry → Seams → Export**. Each shows its status and can be redone. |
| **Residuals** (bottom) | Tie-point table (source, target, origin auto/manual, weight, enabled, residual) and the displacement-field view. |

### 1. Grid
- **Target projection:** the first image's CRS by default; any CRS can be
  chosen.
- **Resolution:** the finest input's by default.
- **Bounds:** the union of the inputs.
- **Alignment:** snapped to a pixel grid (target-aligned pixels).
- **Reprojection:** inputs in other CRSs are reprojected on the fly for
  display (`rasterio.warp`), and properly at export.
- **Spectral mosaics:** inputs must share bands. If their wavelengths
  differ, the mosaic uses the bands they have in common, matched by
  wavelength, and says which.

### 2. Align
One **tie-point model** serves both manual and automatic alignment.

- **Nudge:** drag the selected image, or use the arrow keys (Shift for ×10).
  This sets a translation, and the initial offset for automatic matching.
- **Manual tie points:** click a point on one image, then the same point on
  another. Optionally snap it to sub-pixel accuracy with local phase
  correlation. Manual points get high weight and are always kept as inliers.
- **Automatic tie points (built-in):**
  1. A coarse global offset from masked phase correlation on downsampled
     images.
  2. A grid of tiles over each overlap, each one phase-correlated (upsampled
     about 100×). Each tile gives a tie point with a quality score.
  3. Optional **COSI-Corr-style refinement**: a phase-plane fit (Leprince et
     al. 2007) for about 1/20 px. This is a **clean-room** re-implementation:
     written from the published paper and the COSI-Corr user guide, never
     from geoCosiCorr3D's code (its license is non-commercial). Reverse
     Engineer Anything (REA) is not used: it works by decompiling binaries,
     so pointing it at geoCosiCorr3D's libraries would copy the very code
     we must not use. Accuracy is checked against the paper's reported
     results on synthetic shifts, and optionally by comparing outputs with a
     separately installed COSI-Corr as a black box.
  4. An ORB/SIFT fallback when rotation or scale differ a lot.
- **Fit:** RANSAC with the chosen transform: translation, rigid,
  similarity, affine, projective, polynomial (order 2–3) or thin-plate
  spline. Each tie point shows its residual and can be disabled or dragged.
  The fit updates live.
- **Displacement field:** the tile grid also yields dx, dy and SNR rasters,
  the same output COSI-Corr gives. They can be shown and added to the
  project, which makes them useful beyond mosaicking, for example for
  detecting change and deformation.
- **Which bands to align on (spectral cubes):** don't pick one band
  arbitrarily. A **noise analysis** estimates each band's SNR (signal over
  a noise estimate from shift differences, as MNF does) and picks the best
  *N* bands (default 5, spread across the range) inside the inputs' common
  wavelengths, skipping bad bands. Matching runs on each chosen band (or on
  their SNR-weighted mean for speed). The tie points are pooled, so the
  transform is fitted to all of them with RANSAC, and the residuals are
  reported per band. A band whose fit disagrees, for example because of an
  atmospheric band or a detector artifact, shows up and can be dropped.
  Grayscale inputs simply use their one band.
- **ASP backend (extra):** run `image_align` on each of the chosen high-SNR
  bands (interest points or dense disparity, ASP's choice of detector),
  then import the match points as auto tie points. Pooled with RANSAC, they
  give one transform that is applied to every band.
- **Guidance:** for map-projected inputs, the dialog says that translation
  (or affine) is usually right. For unprojected pushbroom images (raw CTX),
  it recommends map-projecting with ISIS `cam2map` (offered when ISIS is
  found), with polynomial or TPS as the fallback.

### 3. Radiometry
Per band, with the coefficients stored and exported.

- **None:** the default for spectral cubes.
- **Linear, to a reference:** gain and offset per band, fitted on
  co-located overlap pixels with a robust regression.
- **Linear, global least squares:** like ISIS `equalizer`. All overlaps are
  solved together; held images keep gain 1 and offset 0. Modes: gain,
  offset, or both. The overlap graph must be connected, and the dialog says
  when it isn't.
- **Histogram matching:** non-linear, so labeled "visual only (changes
  spectral shape)".

### 4. Seams
- **Priority:** the stack order. This is the default.
- **Voronoi:** each overlap split down its middle (as in ENVI's automatic
  seamlines).
- **Least difference:** a minimum-cost path through |A − B| over each
  overlap (`skimage.graph.route_through_array`), applied pairwise in
  priority order. Graph cut may come later.
- **Editing:** seams are editable as lines on the canvas.
- **Blending:** **none** (the default), **feather** over N pixels, or
  **multi-band (pyramid)**. Feather and multi-band are labeled "visual
  products".

### 5. Export
- **Rendering:** tile by tile with windowed writes, so mosaics larger than
  memory work.
- **Format:** GeoTIFF (tiled, compressed) or ENVI, keeping wavelengths, FWHM
  and band names.
- **Provenance:**
  - a **source-index band** (which input each pixel came from, like ISIS
    `automos` TRACK);
  - the transforms, radiometric coefficients and seam settings;
  - the software and version.

  These go in the metadata and a sidecar JSON file.
- **Result:** the mosaic joins the project as a new image. The recipe is
  saved with the workspace, so a reopened workspace can be edited and
  re-exported.

## Architecture

```
src/varda/mosaicking/          # no Qt (import contract)
  model.py        MosaicProject: grid, inputs (image, transform, order,
                  per-band gain/offset), tie points, seams; JSON save/load
  grid.py         target grid, reprojection helpers
  matching.py     phase correlation tiles, COSI-Corr-style refinement,
                  ORB/SIFT fallback, displacement field
  transforms.py   RANSAC fits for each model, residuals
  radiometry.py   pairwise and global least-squares gain/offset, histogram match
  seams.py        priority, Voronoi, least-difference; source-index raster
  render.py       tiled rendering with blending, provenance
  backends/asp.py detect, version, run image_align, import results
  backends/isis.py detect; cam2map, equalizer wrappers when present
src/varda/workspaces/mosaic/   # the GUI: canvas, step pages, residual table
```

- **Background work:** slow steps run through `runInBackground` with
  progress and cancellation. External tools run as subprocesses with live
  logs, as the PyTorch installer does.
- **Large images:** downsampled pyramids for the canvas, and matching on
  tiles. Statistics are computed on subsamples, as ISIS `equalizer`'s
  PERCENT parameter does.

## Ames Stereo Pipeline and ISIS

An **Optional Features** entry, **Ames Stereo Pipeline**, alongside PyTorch.

- **Detect first**, in this order: a path set in Settings; `image_align` or
  `ipfind` on PATH; conda environments named `asp` (or ones holding
  `stereo-pipeline`) under the usual miniconda, miniforge and anaconda
  roots; `~/StereoPipeline-*/bin`. Check the version (`--version`), since
  options change between releases.
- **Otherwise download** the pinned stable release (3.7.0) for the platform
  from GitHub into Varda's app-data folder, verify it, unpack it, and clear
  macOS quarantine.
- **Windows:** not offered. The page explains WSL and points to the built-in
  tools, which cover everything.
- **ISIS:** detected only (`ISISROOT`, `ISISDATA`, conda env `isis`), never
  downloaded, because of the size of its data. When found, it enables
  `cam2map` (map-project raw cubes) and `equalizer` (cross-check the
  built-in global radiometry).
- **Settings:** show what was found and where, with Re-detect and Remove
  buttons.

## Testing

Synthetic scenes with known answers, as for the analyses:

- **Alignment:** recover a planted translation to better than 0.05 px, an
  affine transform to 1e-3 per parameter, and a TPS-warped image to a known
  residual.
- **Radiometry:** recover planted per-band gains and offsets, including a
  global solve over a connected graph, and refuse a disconnected one.
- **Seams:** Voronoi and least-difference seams fall where expected on
  planted overlaps.
- **Spectral fidelity:** with nearest resampling and no blending or
  radiometry, every output spectrum equals its source pixel's exactly, and
  the source-index band names that source.
- **ASP backend:** argument building and result parsing tested against
  recorded outputs; one live test runs only where ASP is found.

## Phases

1. **Workspace and manual mosaics:** the model; Grid; nudge and manual tie
   points with translation, affine and projective fits; priority seams;
   nearest or bilinear export with the source-index band and provenance;
   session save and reopen. This is already useful for CTX strips and
   overlapping CRISM.
2. **Automatic alignment:** phase-correlation tie points, RANSAC for every
   transform including polynomial and TPS, residuals, the COSI-Corr-style
   refinement, the displacement field as an analysis output, and the ORB/SIFT
   fallback.
3. **Radiometry and seams:** pairwise and global gain/offset, histogram
   matching (visual), Voronoi and least-difference seams, seam editing,
   feather and pyramid blending (visual).
4. **Extras:** ASP detection and download, the `image_align` backend, ISIS
   detection with `cam2map` and `equalizer`, and optional OpenCV and kornia
   matchers (kornia through the PyTorch runtime).

## Decisions (2026-10-15)

1. **Data:** CTX and CRISM both, from phase 1.
2. **The ASP extra:** offered in-app, as with PyTorch, after detecting an
   existing install. Windows uses the built-in path (there is no native
   ASP).
3. **Graph-cut seams** are deferred; least difference covers most cases.
4. **Science defaults, aesthetic options.** The defaults are hard seams,
   per-band linear corrections only when asked, and nearest resampling.
   Aesthetic methods are available for visual products: histogram matching,
   feathering, multi-band blending, and bilinear or cubic resampling. Each
   is labeled, recorded in provenance, and changes the export's name
   ("… (visual)").
5. **Band selection** for alignment uses the noise analysis above: the best
   N SNR bands, pooled tie points, residuals per band.

## Sources

- ASP:
  [image_align](https://stereopipeline.readthedocs.io/en/latest/tools/image_align.html),
  [installation](https://stereopipeline.readthedocs.io/en/latest/installation.html),
  [releases](https://github.com/NeoGeographyToolkit/StereoPipeline/releases),
  [dem_mosaic](https://stereopipeline.readthedocs.io/en/latest/tools/dem_mosaic.html),
  [image_mosaic](https://stereopipeline.readthedocs.io/en/latest/tools/image_mosaic.html)
- ISIS:
  [automos](https://isis.astrogeology.usgs.gov/dev/Application/presentation/Tabbed/automos/automos.html),
  [equalizer](https://isis.astrogeology.usgs.gov/10.0.0/Application/presentation/Tabbed/equalizer/equalizer.html),
  [install via conda](https://astrogeology.usgs.gov/docs/how-to-guides/environment-setup-and-maintenance/installing-isis-via-anaconda)
- COSI-Corr:
  [Leprince et al. 2007](https://www.tectonics.caltech.edu/slip_history/spot_coseis/pdf_files/Leprince2007TGRS.pdf),
  [license](https://www.tectonics.caltech.edu/slip_history/spot_coseis/download_software.html),
  [geoCosiCorr3D](https://github.com/SaifAati/Geospatial-COSICorr3D)
- scikit-image:
  [registration](https://scikit-image.org/docs/stable/api/skimage.registration.html),
  [transform](https://scikit-image.org/docs/stable/api/skimage.transform.html),
  [measure (ransac)](https://scikit-image.org/docs/stable/api/skimage.measure.html),
  [graph](https://scikit-image.org/docs/dev/api/skimage.graph.html)
- Other alignment options:
  [AROSICS](https://github.com/GFZ/arosics),
  [opencv-python](https://github.com/opencv/opencv-python),
  [kornia](https://github.com/kornia/kornia)
- Mosaicking practice:
  [ENVI Seamless Mosaic](https://www.nv5geospatialsoftware.com/docs/MosaicSeamless.html),
  [Seelos et al. LPSC 2022 (CRISM map tiles)](https://www.hou.usra.edu/meetings/lpsc2022/pdf/2361.pdf),
  [Dickson et al. 2024 (CTX global mosaic)](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2024EA003555),
  [Pan et al. 2009 (Voronoi seamlines)](https://uwaterloo.ca/geospatial-intelligence/sites/default/files/uploads/files/automatic_generation_of_seamline_networks_using_area_voronoi_diagrams_with_overlap.pdf),
  [Burt & Adelson 1983](https://www.cs.princeton.edu/courses/archive/fall05/cos429/papers/burt_adelson.pdf),
  [Brown & Lowe 2007](https://matthewalunbrown.com/papers/ijcv2007.pdf)
- Tools:
  [gdalwarp](https://gdal.org/en/stable/programs/gdalwarp.html),
  [rasterio.merge](https://rasterio.readthedocs.io/en/stable/api/rasterio.merge.html)
