# Changelog

Notable changes to Varda. Release notes on GitHub are generated from pull
requests; this file records what users need to know, especially changes that
can alter results.

## Unreleased

### Fixed

- **The histogram keeps its zoom when the stretch changes.** Dragging a
  stretch region (or changing the stretch) snapped the histogram back to the
  full range, which also undid a span you'd just zoomed to.

## 0.7.2 (2026-10-15)

### Added

- **Cropping, to work on part of an image.** The **Crop** tool in an
  image's toolbar adds a cropped copy of the box you drag to the image
  list. **Geometry → Crop to ROI** crops to ROI classes, optionally making
  pixels outside them no-data. Run any analysis or workspace (such as the
  Spectral Hourglass) on the crop.
- **Pixel Select windows.** The Pixel Spectra panel has Window Width and
  Height settings (like the Ratio Explorer's boxes): 1×1 selects one pixel;
  larger plots the region's mean spectrum with a ±1 σ band (no-data pixels
  left out), and the window is outlined while you Ctrl-drag.

### Changed

- **Plotted spectra are marked with circles** in their curve's color
  (a region with its outline), and selecting a spectrum on the plot
  highlights its marker on the image. Markers follow a change of color.

## 0.7.1 (2026-10-15)

### Changed

- **Filtering is split into Spatial and Spectral submenus.** The spatial
  filters are under Processing → Filtering → Spatial; IOVF and spectral
  filters from plugins are under Filtering → Spectral. Plugins can nest
  their own submenus with a "/" in their category ("Filtering/Spectral").

## 0.7.0 (2026-10-15)

### Added

- **Image processing tools** (see the user guide's Image processing page):
  - Filtering: Smoothing, Sharpening, Edge Detection, Morphology, Speckle
    Filters (Lee, Kuan, Frost), Frequency Filter (FFT) and Custom Kernel,
    on all bands or one.
  - Statistics: Local Statistics and Co-occurrence (GLCM) texture.
  - Transforms: Color Transform (RGB ↔ HSV/HLS), Decorrelation Stretch and
    Saturation Stretch.
  - Classification: Density Slice, Majority/Minority Filter, Sieve and
    Clump for class maps.
  - Topography (new): Terrain, which computes slope, aspect, hillshade,
    curvature and roughness from a DTM.
  - Geometry (new): Resample, Rotate / Flip and Subset, keeping the
    georeferencing and band metadata.

## 0.6.0 (2026-10-14)

### Added

- **Update check.** A few seconds after starting, Varda asks GitHub whether
  a newer version is out, and offers to open its release page (or skip that
  version). **Help → Check for Updates…** checks at any time, and the check
  at startup can be turned off.
- **Spectral Hourglass: Draw on Image.** Draw shapes on the scene to add the
  pixels inside to the active endmember (Shift removes them), alongside the
  n-D lasso.
- **Kindle a Feature.** Describe a feature in plain language and your own AI
  (Anthropic, with your API key in the system keychain) builds it as a
  plugin. Varda checks it on a synthetic image and a crop of yours in a
  separate process, then shows a summary, where it appears, warnings, the
  checks and the code to Enable, Ask for Changes or Discard. Only the
  description, the plugin docs and the image's metadata are sent, never its
  pixels. Plugins → Kindle a Feature… and AI Assistant Settings….

### Fixed

- **A closed image list can be reopened**, from the new **View → Image
  List**, which is checked while the list is showing.
- **Manage Plugins has a Close button** (on macOS it had no way to close
  except Escape).
- **Spectral plots follow a spectrum taller than the view.** Hovering a point
  in the Spectral Hourglass n-D view didn't grow Y for a pixel brighter than
  the plotted spectra, in Auto or Fit Y To X Range; a pixel with bad (NaN)
  bands froze the range entirely.

## 0.5.2 (2026-10-14)

### Fixed

- **macOS: double-clicking the disk image showed nothing.** The 0.5.1 image
  mounted without opening a window. The image now opens a window with
  **Varda** and the **Applications** shortcut, like other apps' disk images.

## 0.5.1 (2026-10-14)

### Fixed

- **macOS: the download didn't open.** macOS blocked each library inside the
  downloaded folder ("library load disallowed by system policy"), and
  right-click → Open couldn't help. The macOS download is now a disk image
  with **Varda.app**: drag it to Applications and approve it once (see the
  install guide).
- **Windows: no more console window** behind Varda; it's a normal windowed
  app now.
- **Linux:** the download is a `.tar.gz` (it keeps file permissions), with
  an `install.sh` that adds Varda to your applications menu.
- Every release build now unpacks each platform's actual download and
  self-tests that copy before publishing.

## 0.5.0 (2026-10-14)

### Changed

- Varda's home is now **github.com/varda-pro/Varda** (the old address
  redirects), and the Help menu links there.
- On-screen text uses American spelling throughout.

### Added

- **Plugins work.** A new **Plugins** menu installs plugins from a folder or zip
  and manages them (enable, disable, reload, remove, and see why one didn't
  load), in the downloadable app as well as from source. Plugins add
  analyses to the Processing menu or new file formats, using the stable
  `varda.api`. See `docs/plugins/authoring.md` and the band depth example.
- **Remove images from the project:** right-click in the Image List →
  **Remove from Project…**, or press Delete. Workspaces showing them close,
  and Varda asks first when that, or losing an unsaved result, would happen.

### Fixed

- The New Dual Image Workspace and New General Analysis Workspace dialogs
  could vanish a moment after opening.
- The large view now follows the overview's region box to its final
  position; it lagged one change behind.
- Fit Y To X Range now fits ROI spectra that have their ±1σ shading.

## 0.4.0 (2026-10-13)

### Changed: results may differ from earlier versions

- **Wavelength units are read, not guessed.** Varda now reads each file's
  declared wavelength unit (nm, µm or cm⁻¹) and does every calculation in
  nanometres. Before, several analyses guessed the unit from how big the
  numbers were ("below 10 means µm"). Affected:
  - **Spectral Slope** now works on µm images (it found no bands before) and
    gives the same result as on the nm version of the same image.
  - **Spectral Derivative** is per nm whatever the image's unit; its result
    keeps the source's wavelengths.
  - **Spectral libraries**: a thermal-IR library in µm (e.g. 8-14 µm) is no
    longer read as nm. CSV libraries can name their unit in the wavelength
    column (`wavelength_um`) or a `# units:` comment.
  - A file that declares no unit gets one inferred from its values, with a
    warning in the log.
- **Bad bands are honored.** Bands marked bad in an ENVI header (`bbl`) are
  ignored by analyses (filled along each spectrum), left out of Spectral Slope
  and of the Spectral Hourglass's Prepare step.
- **Scaled reflectance.** Band Parameters divides by the header's reflectance
  scale factor first, so integer-scaled products (e.g. × 10000) work.
- **Half-pixel alignment.** Map coordinates of analysis results now line up
  with their source image (they were half a pixel off). Drawn ROIs on
  map-referenced images keep their exact corners instead of snapping to pixel
  centers.

### Added

- **Hide and show ROIs:** untick an ROI in the ROI table to hide it on the
  image, use **Hide All / Show All**, or right-click a row for **Show Only
  This ROI**. Hidden ROIs stay in the table and in saved sessions.
- **Duplicate Workspace** (Workspace menu, or right-click a workspace's tab):
  opens a copy on the same images with its own copies of the ROIs and
  display settings.
- The class legend of an overlaid classification sits over the image instead
  of crowding the overlay toolbar.
- **File → Save Session (Self-Contained)** writes one `.varda.zip` holding
  the session and every result that exists only in memory (as ENVI files);
  **Open Session** reopens it from anywhere. Paths inside a session folder
  are now stored relative to the session file.
- **Provenance**: every analysis result records the analysis, its settings,
  its input, the Varda version and the time; exported files carry the same
  record in their description.
- **Target Detection** (new Processing submenu): RX anomaly (global and
  local window), ACE and matched filter, the last two targeting the mean
  spectrum of ROI classes.
- **Classifiers**: Gaussian maximum likelihood and Mahalanobis distance
  (trained on ROI classes; small classes are handled by reducing to principal
  components instead of being dropped) and k-means clustering.
- **MNF noise estimate** can use vertical, diagonal or averaged neighbor
  differences, or a homogeneous ROI class (horizontal stays the default).
- Library spectra are resampled through each band's response when the image
  header gives band widths (FWHM), instead of being sampled at band centers.
- **Band Math** (Processing → Spectral Parameters): expressions such as
  `R2300 / R2200` (bands nearest 2300 and 2200 nm), `(b10 - b4) / (b10 + b4)`
  or `where(b3 > 0.2, R2300, 0)`. References are checked before anything is
  read, the result size is shown, large images are processed in chunks, and
  expressions can be saved for reuse.
- Images open in **true color** when they cover the visible (bands nearest
  640, 550 and 470 nm), otherwise in a false color spread over their range;
  a file's own default bands still win.
- **Histogram equalization, square-root and logarithmic stretches.**
- **Export spectral plots** as PNG (high resolution), SVG, PDF or CSV (the
  **Export…** button in the plot's View section).
- **Continuum Removal** (Processing → Spectral Parameters): each spectrum
  divided by its upper hull within a wavelength window.
- **Help menu**: About Varda, Cite Varda (APA and BibTeX), Copy System Info
  (for bug reports), Documentation and Report an Issue.
- Varda is licensed under the GNU GPL v3 or later; the repository has a
  citation file, contributing guide, code of conduct and issue templates.
- ENVI export writes `fwhm`, `bbl` and `reflectance scale factor`, and no
  longer writes a `wavelength` list for products that aren't spectra.
- Spectral plots label their x axis with the unit, and library spectra are
  shown in the plotted image's unit.
- The Hourglass endmember export names its wavelength unit, so it loads back
  as a library.

### Deprecated

- `VardaRaster.raster` (deprecated since 0.0.2) now says so with a
  `VardaDeprecationWarning` naming its replacements: `getBands()`,
  `getData()` or `getSpectrum()`. These read only what they need rather than
  the whole image.

### Faster

- **Very large images open quickly.** An image that would take more than a
  quarter of the computer's memory is read from disk on demand (recent band
  reads are cached) instead of being loaded whole; smaller images still load
  into memory as before.
- Changing the stretch no longer re-reads the image, and changing opacity
  no longer re-reads or re-stretches it (about 70 ms to under 25 ms on a
  3000 × 3000 RGB view). Only a new band selection reads bands again.
- Numba's compiled stretch kernels are cached on disk when running from
  source, so the first stretch of a session no longer compiles for seconds.

### Fixed

- The splash appears as soon as Varda starts and animates while it loads; it
  used to flash up only once loading had finished.
- A new splash animation: one continuous pen writes the wordmark, with no jump
  or pause, and finishes smoothly even when Varda is ready early.
- Hints and analysis descriptions were too dark to read in dark mode.
- ENVI files open whatever their data file is called: `.img`, `.dat`, `.raw`,
  `.bin`, `.bsq`/`.bil`/`.bip`, no extension, upper case, or `foo.img.hdr`.
  Opening the data file directly also works when its header sits beside it,
  and an `.img` without a header (e.g. Erdas or PDS) is no longer forced
  through the ENVI reader.
- ENVI headers written with capitalized keys (e.g. `Wavelength Units`) lost
  their wavelengths, units and band metadata.
- Integer ENVI files with a `data ignore value` failed to load.
- The Spectral Hourglass library preview was blank for µm images.
- User plugins in `plugins/user_plugins/` never loaded.
- Closing an image that had been loaded into memory left its file open.
- An analysis could fail with a read error, or read wrong values, if the display
  read the same file at the same time. Each thread now has its own file handle.
- Opening a large file no longer blocks the window while it loads.
- An unexpected error while installing PyTorch left the Optional Features
  dialog busy forever.
- Saved plot curves kept their color but lost its transparency.
- Settings changed after a dialog or panel closed could still reach its
  widgets.
- A session saved by a newer Varda is refused with a clear message.
