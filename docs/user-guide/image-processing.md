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

All three keep the georeferencing right, so pixels stay at their place on the
map, and Subset carries the wavelengths, bad bands and FWHM along.
