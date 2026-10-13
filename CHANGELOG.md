# Changelog

Notable changes to Varda. Release notes on GitHub are generated from pull
requests; this file records what users need to know, especially changes that
can alter results.

## Unreleased

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
- **Bad bands are honoured.** Bands marked bad in an ENVI header (`bbl`) are
  ignored by analyses (filled along each spectrum), left out of Spectral Slope
  and of the Spectral Hourglass's Prepare step.
- **Scaled reflectance.** Band Parameters divides by the header's reflectance
  scale factor first, so integer-scaled products (e.g. × 10000) work.
- **Half-pixel alignment.** Map coordinates of analysis results now line up
  with their source image (they were half a pixel off). Drawn ROIs on
  map-referenced images keep their exact corners instead of snapping to pixel
  centres.

### Added

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
- **MNF noise estimate** can use vertical, diagonal or averaged neighbour
  differences, or a homogeneous ROI class (horizontal stays the default).
- Library spectra are resampled through each band's response when the image
  header gives band widths (FWHM), instead of being sampled at band centres.
- **Band Math** (Processing → Spectral Parameters): expressions such as
  `R2300 / R2200` (bands nearest 2300 and 2200 nm), `(b10 - b4) / (b10 + b4)`
  or `where(b3 > 0.2, R2300, 0)`. References are checked before anything is
  read, the result size is shown, large images are processed in chunks, and
  expressions can be saved for reuse.
- Images open in **true colour** when they cover the visible (bands nearest
  640, 550 and 470 nm), otherwise in a false colour spread over their range;
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

- ENVI files open whatever their data file is called: `.img`, `.dat`, `.raw`,
  `.bin`, `.bsq`/`.bil`/`.bip`, no extension, upper case, or `foo.img.hdr`.
  Opening the data file directly also works when its header sits beside it,
  and an `.img` without a header (e.g. Erdas or PDS) is no longer forced
  through the ENVI reader.
- ENVI headers written with capitalised keys (e.g. `Wavelength Units`) lost
  their wavelengths, units and band metadata.
- Integer ENVI files with a `data ignore value` failed to load.
- The Spectral Hourglass library preview was blank for µm images.
- User plugins in `plugins/user_plugins/` never loaded.
- Closing an image that had been loaded into memory left its file open.
- Saved plot curves kept their colour but lost its transparency.
- Settings changed after a dialog or panel closed could still reach its
  widgets.
- A session saved by a newer Varda is refused with a clear message.
