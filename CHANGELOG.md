# Changelog

Notable changes to Varda. Release notes on GitHub are generated from pull
requests; this file records what users need to know, especially changes that
can alter results.

## Unreleased

## 0.9.0 (2026-10-16)

### Added

- **3D Terrain workspace** (Workspace → New 3D Terrain Workspace): a DEM as
  a lit surface with soft shadows, draped with shaded relief, elevation
  colors or an image on its grid (e.g. a DTM's orthoimage); vertical
  exaggeration, sun azimuth and elevation, saved camera views, stills up to
  16384 px (transparent background optional), and **Export Web Page**: a
  self-contained interactive HTML file for any browser. Built on three.js in
  Qt WebEngine, which Varda now includes.
  - **Overlays:** drape images that aren't on the DEM's grid (e.g. a CRISM
    parameter composite over a CTX DEM), each with its display settings and
    opacity, aligned by **Auto Align** against the DEM's orthoimage or a
    hillshade (the Mosaic workspace's matching; translation by default, up to
    polynomial and thin-plate-spline warps) and a manual shift in meters.
    Saved with the session and included in stills and web pages.
  - **Block diagrams and 3D printing:** **Sides** stands the surface on walls
    down to a base; **Export for 3D Printing** saves a watertight STL in
    millimeters (width, exaggeration, base and detail chosen, the printed
    size shown). **Fill gaps** fills no-data voids inside a DEM for both.
    **Edges** makes the outline smooth (the default: no more staircase
    sides on tilted footprints), stepped, or trimmed to a rectangle, and
    **Side color** chooses the walls' color.
  - **Figures:** a north arrow, a scale bar (at the view's center, with the
    exaggeration) and a color bar for elevation colors, on the view and in
    stills; lines from GIS files draped on the surface; and **Export
    Animation**, a flyover as an animated WebP, a GIF or PNG frames.
  - **Overlay Display** panel: the selected overlay's mode, bands (any three
    parameters of a cube by name), stretch and color map, with histograms
    whose stretch ranges can be dragged, in a dockable panel; these
    settings are now saved with the session.
  - **Lines from other workspaces:** **Add Lines** lists the lines drawn in
    open General Image Analysis workspaces (on any georeferenced image of the
    DEM's body), to drape all or one at a time, with no file in between; a
    **Profiles** panel plots the DEM along the lines.
  - **Alignment transfer:** **Match using** runs Auto Align on another image
    with the overlay's georeferencing (e.g. a CTX-like scene simulated from
    the same CRISM observation) and moves the overlay (e.g. its parameter
    map) by the result; **Copy** and **Paste** give another overlay the
    same alignment.
- **Linked Images workspace** (Workspace → New Linked Images Workspace…):
  any number of images side by side, linked by pixel or by map location,
  panning and zooming together. Ctrl+click or Ctrl+drag puts one cursor on
  every view and plots every image's spectrum there, each in its own plot
  (a product, its counts, its flags); a line drawn on any view gives every
  image's profile. Made for checking pipeline products, such as MISE's
  synthetic data, against each other. Every view and panel is a dock to
  drag, tab or float, and the Display panel shows each image's histograms.
- **Bit masks:** **Decode Bit Mask** (Processing → Statistics) turns a
  mask (a pipeline's per-frame exclusions, a QA band) into the number of
  bits set, one bit, or any of several, band by band; in Linked Images a
  mask shows as bits by wavelength at the cursor. On MISE's example
  products, EXCLUDE's set bits reproduce COUNT exactly.
- **Wavelengths and weights for PCA, MNF and ICA** (Processing →
  Transforms): each takes a wavelength range (as the Spectral Hourglass
  does; bands marked bad are always left out) and, optionally, weights: an
  image on the same grid giving each value a weight (frames used, or
  uncertainties as 1/σ²). Values with no weight (flagged, missing) move
  neither the components nor a pixel's scores: Delchambre's (2015)
  weighted covariance, with each pixel's scores a weighted least-squares
  fit (MNF's noise from weighted neighbor differences).
- **Convolve to Sensor Bands** (Processing → Spectral Parameters): a cube
  with wavelengths in another sensor's bands, each weighted by its spectral
  response (bad bands and no-data left out, uncovered bands skipped):
  the measured responses of Landsat 8 OLI, Landsat 9 OLI-2 and
  Sentinel-2A/B/C MSI (NASA/USGS and ESA, bundled), CTX's measured passband
  (Bell et al. 2013), approximate HiRISE and THEMIS VIS bands, a response
  file, or typed center/FWHM bands. CRISM reflectance as a CTX scene aligns
  to a CTX orthoimage near the known offset, where the cube's own bands
  land kilometers off.
- **Package Project** (File → Package Project…, replacing Save Session
  (Self-Contained)): one `.varda.zip` with everything a project needs to
  open on another computer: the session, every image with its companion
  files (ENVI headers, PDS labels, `.aux.xml`, world files), files
  workspaces use, results held in memory, and a manifest of every file's
  size and SHA-256 with the Varda version, for replicability. Packages over
  1 GB ask first; it's written in the background.
- **Subset with a preview** (Processing → Geometry → Subset): drag a box
  on the image to choose the part to keep, and drag ranges on the box's
  mean spectrum to choose the bands; both stay in step with the typed rows,
  columns and bands.
- **Workspace tabs work like a browser's:** drag them into order (sessions
  keep it), drag one out of the tab bar to open it in its own window, and
  middle-click to close.
- **Lines and profiles** (General Image Analysis): draw straight lines,
  polylines or freehand lines with **Draw Line**, listed in the new **Lines**
  tab (rename, recolor, delete, export to GIS files) and saved with the
  session. The **Profiles** tab plots a band along them, e.g. a topographic
  profile of a DEM: distance in meters (geodesic for longitude-latitude
  images), the pointer's spot marked on the image, the vertical
  exaggeration, and export as CSV, PNG, SVG or PDF.
- **Overlay colors:** a single-band overlay's **Colors** menu chooses its
  color map (Viridis, Magma, Inferno, Plasma, Cividis, Turbo, Gray or a
  diverging Blue-White-Red), reverses it, and stretches it over the full
  range or 2-98 % or 5-95 %. Clicking a class's swatch in the legend changes
  its color; the new color is saved with the result and every view showing it
  follows.
- **Stretch From** (General Image Analysis, Render Settings): the stretch and
  the histogram can take their statistics from the full image, the main view
  or the zoom view, as in ENVI; the stretch then applies to the whole image.
  It follows the views as you pan and zoom.
- **Kindle a Feature checks before it builds.** If Varda already does what
  you describe (a menu item, an installed plugin, a file format or catalog),
  the AI says what and where instead of building; **Build Anyway** builds it
  regardless. Requests a plugin can't do (changing the interface or built-in
  features, reworking the app, reaching the network or other programs) are
  declined with the reason and the closest thing it could build.
- **Find and Fetch Data** (Workspace → Find and Fetch Data…): search catalogs
  for observations of a place and see their footprints on a map, over a
  loaded image and vector overlays (a rover traverse, a geologic map), with
  the results in a sortable table and a preview. Varda ships three catalogs:
  STAC (USGS Astrogeology for Mars, the Moon and Europa, and Earth Search, by
  default), the PDS Orbital Data Explorer, and footprint files (offline);
  plugins can add more with a `registerCatalogs` hook.
  - **Downloads:** add checked products to the download list, choose their
    files (the essential ones come checked) and download them into one folder
    per product, with progress, Cancel and resuming; finished data opens in
    Varda. The list also exports as a CSV or a script of resumable `curl`
    commands.
  - The download list's columns can be dragged wider to show full names.
    **Check** checks all files, only the essential ones, none, or every file
    of a type (data, labels, browse images); **Select** picks products by
    status (e.g. the failed ones). Check, Download and Remove act on the
    selected products, or on all when none are selected.
  - Catalogs that need a login ask for it once and keep it in the system
    keychain; the STAC APIs searched can be edited (STAC APIs…).
  - **Map projections:** equirectangular, or north or south polar
    stereographic, with a graticule that gets finer as you zoom in and the
    pointer's latitude and longitude below the map. Basemaps, overlays and
    the search box follow the projection; a view around a pole searches
    every longitude.
  - **Finding a collection:** the Collection menu opens a search over the
    collections, grouped by body and then by mission and instrument with
    counts; every word typed must match (e.g. "mars crism", "mars express",
    "kaguya dtm"). ODE's mission abbreviations are spelled out for searching.
  - **Selecting on the map:** click selects the footprints under the
    pointer, Shift-click adds, Cmd-click (Ctrl-click) removes, and
    Shift-drag adds every footprint a box touches. **Show only selected**
    narrows the results table to the selection.

### Fixed

- **Stretches on whole-number images** (DN products such as MISE's int16
  aggregate): dragging a histogram's stretch range, and the Linear,
  Square Root and Logarithmic Percentile stretches, turned the image
  black, as the stretched fractions were stored as integers (all 0).
- A product file that can't be downloaded (e.g. a catalog's broken link,
  404) no longer stops the product's other files: they download, the product
  is marked failed with the reason, and each missing file says "not
  downloaded". The 404 message now says the archive doesn't have the file.
- Collections with the same title (USGS's HiRISE DTMs and their test copy)
  show their ids, so they can be told apart.
- Ratio Explorer's numerator and denominator boxes now stay on their pixels
  when the view is panned or zoomed, instead of moving with it.
- Closing a Find Data workspace while it was drawing a basemap, listing
  collections, searching or downloading could raise an error when the work
  finished; such results are now dropped.
- Very large images read on demand now serialize every read (windows, pixel
  spectra, whole-image reads), not only band reads, so the display and an
  analysis can't read the same file at once.
- **Find Data basemaps** were drawn mirrored across their diagonal (in the
  right place, but transposed); they are now north up as in the image.
- Images loaded after a Find Data workspace opened (a finished download, for
  instance) now appear in its Basemap and Area image lists.

## 0.8.0 (2026-10-15)

### Added

- **Auto Align in the Mosaic workspace.** Finds tie points between an image
  and the images it overlaps:
  - phase-correlated tiles on the bands with the best SNR, spread across the
    spectrum;
  - refined to about 1/50 px with the phase-plane fit of Leprince et al.
    (2007), the method behind COSI-Corr, re-implemented from the paper;
  - ORB features when rotation or scale differ.

  The points are fitted robustly (RANSAC), with outliers shown. A per-band
  report lets you drop a band that disagrees. The tile shifts can be added
  to the image list as a displacement field (east, north, quality).
- **Polynomial and thin-plate-spline alignment** for mosaic images whose
  distortion varies across them (2nd or 3rd order polynomials, and a
  thin-plate spline for local warps), fitted robustly like the other
  transforms and saved with the session.
- **Radiometric balancing in the Mosaic workspace** (the Radiometry tab), per
  band, from the overlaps: linear to held images (robust regression), a
  global least-squares solve like ISIS equalizer (which refuses images not
  connected to a held one), or histogram matching (labeled visual). None
  remains the default, keeping every spectrum exact.
- **Seams in the Mosaic workspace** (the Seams and Blending tab): split each
  overlap down its middle (Voronoi) or along the path where the images
  differ least, instead of letting the top image win. Seams are outlined on
  the mosaic, can be edited by dragging, are kept in map coordinates and
  saved with the session; spectra stay exact.
- **Blending for visual mosaics:** feathering over a chosen width, or
  multi-band (pyramid) blending, across the seams. Blended mosaics are
  labeled visual; hard seams remain the default.
- **The Ames Stereo Pipeline in Auto Align.** Optional Features finds an ASP
  you already have (PATH, a conda environment named asp,
  ~/StereoPipeline-*) or downloads ASP 3.7.0, verified against its
  published checksum (macOS and Linux). Auto Align can then match each
  chosen band with ASP's image_align and fit the pooled matches like its
  own.
- **ISIS, when installed:** Processing → Geometry → Map-Project with ISIS
  (cam2map) projects raw camera cubes so they can be mosaicked (nearest
  neighbor by default), and the Radiometry tab can compare its balance with
  ISIS equalizer's and use it. Varda finds ISIS through ISISROOT or a conda
  environment, and never downloads it.
- **LoFTR and SIFT matchers in Auto Align**, run in the PyTorch environment
  (Optional Features): LoFTR is a learned matcher that finds matches where
  hand-crafted features struggle. The PyTorch environment now includes
  kornia and OpenCV for them; an existing install offers an Update.
- **Mosaic workspace.** **Workspace → New Mosaic Workspace…** joins
  overlapping images (spectral cubes or grayscale) with the same bands and
  projection. Order the images (the top one wins where they overlap), align
  each by nudging it with the arrow keys or by fitting a translation, rigid,
  similarity, affine or projective transform to tie points, and export. The
  default nearest-neighbor export keeps every spectrum exact; an optional map
  shows which image each pixel came from. See the
  [mosaicking guide](docs/user-guide/mosaicking.md).
- **Factor Analysis Target Transformation (FATT).** **Processing →
  Endmembers → Factor Analysis Target Transformation…** finds the factor
  space of an image's spectra (covariance or Hysime, with Malinowski's
  indicator function to choose the number of factors) and ranks library
  spectra by how well it reproduces them (normalized RMSE, as Lin, Tarnas et
  al. 2021). **Map Ticked Targets…** maps where they fit with DAFA/TT moving
  windows. Results are candidates to confirm. See the
  [FATT guide](docs/user-guide/fatt.md).
- **Kindle a Feature works with OpenAI and local models.** Plugins → AI
  Assistant Settings offers OpenAI and any OpenAI-compatible server,
  including Ollama and LM Studio on your own computer (no key needed), with
  Load Models to list a server's models. Each provider keeps its own key in
  the keychain. See [Kindle a Feature](docs/user-guide/kindle-a-feature.md).

### Fixed

- **Mosaics no longer have gashes where an image misses a few bands.** A
  pixel missing data in some bands (a bad CRISM detector column, say) was
  dropped whole, leaving holes, or the image below, in the export (the
  display-band preview didn't show it). A pixel now counts when at least half
  its bands have data, as analyses treat it, and is copied as measured;
  radiometric balancing, seams and feathering handle missing bands per band.
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
