# Spectral analysis tools

Tools that work along each pixel's spectrum: **Continuum Removal**
(**Processing → Spectral Parameters**), and **Spectral Derivative** and
**Spectral Slope** (**Processing → Derivatives**). Each makes a new image
over the same pixels and georeferencing.

What they share:

- **Wavelengths.** Varda converts the image's wavelengths to nm (from µm or
  cm⁻¹) before computing, so every "per nm" below is per nanometer whatever
  unit the image uses. Continuum Removal and Spectral Slope need numeric
  wavelengths with units; Spectral Derivative falls back to band numbers.
- **Missing values.** No-data values and bad bands (the ENVI `bbl` list) are
  filled by linear interpolation along each pixel's spectrum (the nearest
  value past the first or last good band). A pixel missing more than half of
  its good bands is no data in the result.
- **Bad bands.** Continuum Removal and Spectral Slope leave bad bands out.
  Spectral Derivative keeps every band, so at a bad band it uses the filled
  values (see below).

For band ratios, band depths and named spectral parameters, use **Band
Math** (see [Image processing](image-processing.md#image-math-and-masks))
and **Band Parameters (HyPyRameter)** (see [Optional
features](optional-features.md#band-parameters-hypyrameter)).

## Continuum Removal

Divides each spectrum by its continuum, so absorption bands show as dips
below 1. The continuum is the **upper convex hull** of the spectrum within a
wavelength window: straight lines (in reflectance against wavelength in nm)
between the spectrum's local high points, from the first band in the window
to the last.

| Setting | Meaning | Default |
|---|---|---|
| **Start Wavelength** | Start of the window, nm | 1000 |
| **End Wavelength** | End of the window, nm | 2500 |

The window is inclusive at both ends, and the two values can be given in
either order. At least three good bands must fall inside it.

**Output:** one band per good band in the window (bands outside it, and bad
bands, are dropped), with the original wavelengths, band names and FWHM.
Values are unitless ratios: 1 on the hull, below 1 inside an absorption.
Each hull point (including the first and last band of the window) is 1 by
construction. A pixel whose continuum is 0 at some band is no data there.

The hull depends on the window: its ends are always anchors, so moving
either end can change the continuum across the whole feature. Choose a
window that starts and ends on the continuum shoulders of the features you
want, and report it.

## Spectral Derivative

The derivative of each spectrum with respect to wavelength: the first
derivative (dR/dλ) shows absorption edges, the second (d²R/dλ²) band
centers and inflections.

| Setting | Meaning | Default | Range |
|---|---|---|---|
| **Order** | 1 = dR/dλ, 2 = d²R/dλ² | 1 | 1–2 |

**Method:** numpy's `gradient` along the spectrum, with each band's center
wavelength (nm) as x. Inside the spectrum this is a central difference that
is second-order accurate, also for uneven band spacing; the first and last
bands use a one-sided difference to their neighbor (first-order accurate).
The second derivative applies the same step twice, so for evenly spaced
bands it is (R₍ᵢ₊₂₎ − 2Rᵢ + R₍ᵢ₋₂₎) / (4h²): it spans five bands (two on
each side), not three, and the first and last two bands are affected by
the edges. Without numeric wavelengths, x is the band number and the result
is per band.

**Output:** the same bands, wavelengths, FWHM and bad-band list as the input.
Values are the input's units per nm (per nm² for the second derivative), or
per band without wavelengths; the result's description says which. At a bad
band, and across a gap of bad bands, the derivative is that of the
straight line the gap was filled with. The derivative isn't smoothed first,
and Varda has no built-in spectral smoothing (the **Iterative Outlier Voting
Filter (IOVF)** removes spikes only), so smooth the data yourself if you
need to and report how.

## Spectral Slope

The least-squares slope of each spectrum against wavelength between two
wavelengths: an ordinary straight-line fit, with every good band in the range
weighted equally.

| Setting | Meaning | Default |
|---|---|---|
| **Start Wavelength** | Start of the fitted range, nm | 1000 |
| **End Wavelength** | End of the fitted range, nm | 2000 |

The range is inclusive at both ends, the values can be given in either
order, and at least two good bands must fall inside it.

**Output:** one band, named "Slope *start*–*end* nm", in the input's units
per nm (reflectance per nm for reflectance data). Only the slope is kept:
there is no intercept, standard error or goodness of fit (see below).

## Reporting your results

What to state in a methods section, what the quality measures mean, and
what to cite. See also [Reporting results from Varda](reporting-results.md)
for what applies to every process.

### What to state

- The tool and its settings: the continuum window, the derivative order,
  the slope range, all in nm. Varda records these with each result.
- The bands actually used: list the bad bands you excluded (Image
  Properties shows them), and for a window or range, the first and last
  band centers inside it. The number of bands in a slope fit is the number
  of good bands in its range.
- For **Continuum Removal**, that the continuum is the upper convex hull,
  linear in wavelength (not in wavenumber or log reflectance), anchored at
  the first and last band of the window.
- For **Spectral Derivative**, the finite-difference scheme (central
  differences on the band centers, applied twice for the second
  derivative) and any smoothing you did beforehand.
- For **Spectral Slope**, that it's an unweighted least-squares fit.

Settings the tools use that aren't in the dialog:

| Tool | Setting |
|---|---|
| All | A pixel needs at least half of its good bands to be valid; missing bands are filled linearly along the spectrum |
| Continuum Removal | Hull by the monotone chain; points on a straight line between two hull points are not hull points |
| Spectral Derivative | numpy `gradient` with the default edge order (1) |

### Uncertainty and quality

- **None of these tools outputs an uncertainty.** They don't propagate the
  input's noise, and Continuum Removal doesn't record which bands it used
  as hull points for each pixel.
- **Measure the noise yourself.** Draw an ROI over a uniform area and add a
  **Zonal statistic of a raster** column (**std**) in the ROI Manager (**Add
  Column...**) for the result's band of interest. The spread includes real
  variation across the ROI, so it's an upper bound on the noise. Do the same
  on the input bands to get the per-band noise σ used below.
- **Derivatives amplify noise.** For evenly spaced bands h nm apart and
  independent noise σ in each band, the noise of the first derivative is
  σ / (√2 h) inside the spectrum and about √2 σ / h at its ends; of the
  second, √6 σ / (4h²). With hyperspectral spacing (h of a few nm), this is
  often larger than the signal, which is why derivatives are usually taken
  on smoothed spectra.
- **Slope standard error.** Varda doesn't output it. If the noise σ is the
  same in every band and independent between bands, the standard error of
  the slope is σ / √(Σ(λᵢ − λ̄)²), summing over the n good bands in the range
  (λ in nm). The sum depends only on the band centers, so you can compute it
  once from the wavelength list. To estimate σ from the fit itself, or to
  get R², export a pixel's or ROI's spectrum from the spectrum plot (CSV)
  and fit it in your own tools: σ² is the sum of squared residuals over
  n − 2.
- **Continuum-removed depths.** A band depth (1 minus the ratio) carries the
  noise of the band and of the hull points, which are different bands from
  pixel to pixel. Because each hull point is chosen as a local maximum,
  noise biases the continuum upward and the depths slightly deeper,
  especially at low SNR.
- **Filled bands** are interpolated, not measured. Report how many bad bands
  fell inside a window or range, and avoid reading derivatives across them.

### References

- Continuum removal: Clark, R. N., & Roush, T. L. (1984). Reflectance
  spectroscopy: quantitative analysis techniques for remote sensing
  applications. *Journal of Geophysical Research*, 89(B7), 6329–6340.
- Monotone chain convex hull: Andrew, A. M. (1979). Another efficient
  algorithm for convex hulls in two dimensions. *Information Processing
  Letters*, 9(5), 216–219.
- Finite differences: Harris, C. R., et al. (2020). Array programming with
  NumPy. *Nature*, 585, 357–362 (`numpy.gradient`).
