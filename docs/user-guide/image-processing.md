# Image processing tools

Varda's everyday image processing, in the **Processing** menu: spatial
filters, texture, color, class map tools, terrain and geometry. Each opens a
dialog with its settings; results join your project as new images.

Most spatial tools work **band by band**: choose **All bands** (a result with
all of the image's bands) or **One band**. No-data pixels are filled from
their neighbors while filtering, so they don't smear across the image, and
are no-data again in the result.

If you need something that isn't here, you can describe it and have your AI
build it: see [Kindle a Feature](kindle-a-feature.md).

## Filtering

Filters are under **Filtering → Spatial** (across the image, band by band)
and **Filtering → Spectral** (along each pixel's spectrum).

### Spatial

| Tool | Methods |
|---|---|
| **Smoothing** | Mean (box), Gaussian, Median (removes spikes and speckle, keeps edges), Bilateral and Total variation (edge-preserving) |
| **Sharpening** | Unsharp mask and Laplacian sharpen add detail back; High pass and Gaussian high pass return only the detail |
| **Edge Detection** | Sobel, Prewitt, Scharr, Roberts (gradient magnitude, band units per pixel), Laplacian, Laplacian of Gaussian, Canny (an edge map of 1s and 0s), Directional (the gradient toward a compass direction) |
| **Morphology** | Dilate, Erode, Opening, Closing, White and Black top-hat, Morphological gradient, with a square or disk structuring element |
| **Speckle Filters** | Lee, Kuan (set by the number of looks) and Frost (set by damping): smooth uniform areas, keep edges and texture |
| **Frequency Filter (FFT)** | Low, high or band pass in the Fourier domain, with Gaussian, Butterworth or ideal cutoffs (fractions of the Nyquist frequency) |
| **Custom Kernel** | Your own kernel, written as rows separated by `;`, e.g. `0 -1 0; -1 5 -1; 0 -1 0` |

### Spectral

The Iterative Outlier Voting Filter (IOVF) removes isolated spikes, judging
each value against its neighbors in both space and wavelength. Spectral
filters added by plugins (a spectral smoothing filter, say) go here too.

## Convolve to sensor bands (Spectral Parameters)

**Convolve to Sensor Bands** turns a cube with wavelengths into another
sensor's bands: each band is the mean of the cube's bands weighted by that
band's spectral response. Bad bands and no-data values are left out. A band
the cube covers less than 90% of (HiRISE BG below CRISM's first band, say)
is skipped, and the result's description lists it.

Built in: MRO CTX, MRO HiRISE (BG, RED, NIR), Mars Odyssey THEMIS VIS,
Landsat 8-9 OLI and Sentinel-2 MSI. These are approximations (boxcars from
published band edges, or Gaussians from published centers and widths),
close enough to make a scene for matching. For values that matter, choose
**Custom bands** and give the sensor's response file: a CSV with a header
row, then wavelength (`wavelength_um` or `wavelength_nm` in the header
names the unit) and one column of response per band. Custom bands can also
be typed as center/FWHM in nm: `Red 650/40; NIR 860/30`.

A use: **aligning a hyperspectral product to a camera.** A CRISM parameter
map has little texture to match against CTX, but CRISM reflectance
convolved to the CTX band looks like CTX. In a 3D Terrain workspace, add the
parameter map as an overlay, set **Match using** to the CTX-like scene and
click **Auto Align**: the alignment found for the scene moves the parameter
map (see [3D Terrain](3d-terrain.md)). Over Jezero, matching CRISM's own
best band against the CTX orthoimage finds one false match; the CTX-like
scene finds ten tie points, RMS 11 m. (CTX's band, 500-800 nm, lies in
CRISM's VNIR detector, so use joined or VNIR data rather than an IR-only
cube.)

## Bit masks (Statistics)

**Decode Bit Mask** reads images whose values are sets of bits, such as a
pipeline's per-frame exclusions (bit *i* set where frame *i* of a stack was
left out) or a quality band, band by band: the **number of bits set**, **one
bit** (1 where it's set), or **any of the bits** (1 where any is set; bits
written like `0, 3-5`). No-data stays no-data.

For MISE's example products, the number of bits set in EXCLUDE reproduces
COUNT exactly, value for value: a check that the pipeline's two products
agree. One bit (frame 0, say) shows where that frame was left out.

## Texture (Statistics)

- **Local Statistics (Texture):** the mean, standard deviation, variance,
  minimum, maximum, data range or skewness in a window around each pixel.
- **Co-occurrence Texture (GLCM):** contrast, dissimilarity, homogeneity,
  second moment, entropy, correlation, mean or variance of the gray-level
  co-occurrence matrix in a window (Haralick et al. 1973), in one direction
  or averaged over four.
- **Spatial Entropy** remains for windowed entropy of one band.

## Color (Transforms)

These work on three bands, the image's display bands by default.

- **Color Transform:** RGB to HSV or HLS, and back.
- **Decorrelation Stretch:** exaggerates the color differences between
  correlated bands (Gillespie et al. 1986); each band keeps its mean and
  spread.
- **Saturation Stretch:** boosts color saturation.

## Class maps (Classification)

- **Density Slice:** turns one band into classes of value ranges, either
  equal intervals or quantiles.
- **Majority/Minority Filter:** replaces each pixel with the most (or least)
  common class around it, cleaning speckle out of a classification.
- **Sieve Classes:** removes groups smaller than a minimum size, leaving
  them unclassified or filling them from their neighbors.
- **Clump Classes:** fills holes and specks inside class regions without
  eating solid regions of other classes.

These work on any class map: a classification result or a density slice.

## Topography

**Terrain** works from an elevation band (a DTM). Its outputs are slope
(degrees), aspect (the compass direction a slope faces), hillshade, curvature
(positive is convex) and roughness. Distances come from the image's pixel
size, so the image needs a projected map coordinate system (such as meters
per pixel). Use the **Z Factor** when elevations are in other units (for
example, 1000 for kilometers of elevation over meters of pixel size).

## Geometry

- **Resample (Resize):** changes the number of pixels by a scale factor,
  with nearest neighbor (use it for class maps), bilinear or cubic
  interpolation.
- **Rotate / Flip:** quarter turns and mirrors.
- **Subset:** keeps a range of rows and columns and a list of bands such as
  `1-100, 150-200`.

- **Crop to ROI:** crops to the ROIs of the classes you tick. Pixels
  outside them can become no-data, so later processing sees only the ROIs.

These keep the georeferencing right, so pixels stay at their place on the
map, and carry the wavelengths, bad bands and FWHM along.

### Working on part of an image

To run anything, an analysis or a whole workspace such as the Spectral
Hourglass, on part of an image, crop it first:

- **Crop tool:** turn on **Crop** in an image's toolbar and drag a box. A
  cropped copy is added to the image list.
- **Crop to ROI:** draw an ROI, then run **Processing → Geometry → Crop to
  ROI**.

Then choose the crop in the analysis dialog, or open a new workspace for it.
