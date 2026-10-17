# Spectral Hourglass: finding, identifying and mapping endmembers

**Workspace → New Spectral Hourglass Workspace…** (also under **Processing →
Endmembers**) runs ENVI's spectral hourglass workflow in one linked view. The
Pipeline panel walks through the steps; each is marked done, or "needs
re-running" when you change an earlier choice:

1. **Prepare** — pick a wavelength window (e.g. drop CRISM beyond 2.6 µm) and,
   for hyperspectral data, remove spikes with the IOVF filter (on by default
   for 100+ bands, as spikes otherwise pose as pure pixels). Bands marked bad
   in the header are always left out.
2. **Reduce (MNF)** — drag the cutoff on the eigenvalue plot, or step through
   the components in the scene overlay to see where they turn to noise.
3. **Pixel Purity** — PPI counts how often each pixel is extreme in random
   projections; the top pixels with at least **Min. PPI count** (2,000 pixels
   with a count of 1 or more, by default) go to the n-D view. **Run More**
   adds iterations to the current counts; use **Run PPI** instead if you have
   changed the threshold or the number of components (see
   [below](#reporting-your-results)).
4. **Endmembers** — in the **n-D Visualizer**, press Play to tour the
   candidates through the kept MNF dimensions. Drag a lasso around a corner
   of the cloud to add it to the active endmember (Shift-drag removes);
   **Suggest** proposes one group per corner (5 by default; corners with
   fewer than 3 candidates are skipped); **Collapse classes** hides the
   corners you already have so the next stands out. You can also pick pixels
   on the image: turn on **Draw on Image** in the scene's toolbar, choose a
   shape, and draw; each shape adds the valid pixels inside it to the active
   endmember (Shift while finishing removes them). This works from Prepare
   on, before Pixel Purity, so a region you already know can seed a class.
   Chosen pixels are filled in the scene and their mean spectrum is plotted.
   Ctrl+Z undoes any edit.
5. **Identify** — rank a spectral library against the active endmember by
   spectral angle, absorption shape and binary encoding; select a match to
   overlay it, then **Use as Name** (**Identify All** records every
   endmember's best match). **Only** limits the comparison to a wavelength
   window. Two libraries are bundled: the CRISM
   MICA numerators (Viviano-Beck et al. 2014; picked automatically for CRISM
   products) and USGS splib07 minerals. **Load Library…** adds your own (see
   below; the **?** button beside it explains the formats).
6. **Map** — SAM (class + angle images), linear unmixing (abundances + RMS
   error; fully constrained by default, or sum-to-one or unconstrained) or
   MTMF (matched-filter score + infeasibility, with a review plot whose
   threshold lines highlight detections live).

Maps join the project's images (as can the MNF and PPI images); endmember
classes can be saved as JSON or exported as a CSV spectral library.
**Save Workflow…** keeps the settings, endmembers and PPI counts in one file,
and the workspace is part of saved sessions.

**Processing** also offers the pieces on their own: **Filtering → Iterative
Outlier Voting Filter (IOVF)**, **Endmembers → Pixel Purity Index (PPI)**, and
**Endmembers → Spectral Angle Mapper**, **Linear Spectral Unmixing** and
**Mixture Tuned Matched Filtering (ROI Endmembers)**, which take each ticked
ROI class's mean spectrum (over all its ROIs) as one endmember. They use the
same code as the workspace; [Reporting your results](#reporting-your-results)
covers them too.

## Preparing a spectral library
Wavelengths may be in nm, µm or cm⁻¹. Name the unit in the wavelength column
(e.g. `wavelength_um`), in a `# units: µm` comment, or in an ENVI header's
`wavelength units`; otherwise Varda infers it and logs a warning. The library
is resampled to the image's bands and must overlap at least five of them;
matching ignores overall brightness, so reflectance, I/F or scaled values all
work.

- **CSV** (`.csv`/`.txt`): first column wavelength, one column per spectrum,
  names in the first non-comment row; lines starting with `#` are comments and
  empty cells are missing values.
  ```
  # optional comments
  wavelength_um,Kaolinite,Nontronite
  1.0010,0.512,0.430
  1.0075,0.515,0.431
  ```
- **ENVI spectral library** (`.sli` + `.hdr`) with `spectra names`,
  `wavelength` and `wavelength units` in the header.
- **USGS splib07 folder**: one sub-folder per spectrum holding its `.txt` and
  `*Wavelengths*.txt` files.

For CRISM, compare unratioed I/F endmembers with the MICA *numerators*;
ratioed type spectra only match ratioed data.

## Reporting your results

What to state in a methods section, what the quality measures mean, and
what to cite. See also [Reporting results from Varda](reporting-results.md)
for what applies to every process. The Processing menu's PPI, SAM,
unmixing and MTMF run the same code as the workspace, so this section
covers them too; where they differ, it says so.

### What to state

- **Prepare:** the wavelength window (in the image's own unit, inclusive),
  that header bad bands were left out, and whether IOVF was on. The kept
  band count and usable pixel count are on the Prepare page.
- **MNF:** the number of components kept, and that the noise was estimated
  from horizontal neighbor differences (below).
- **PPI:** the threshold, the **total** iterations (the Pixel Purity page
  shows them, e.g. "20,000 iterations: …", after any **Run More**), and the
  candidate rule (**Min. PPI count**, **Max. pixels in n-D view**).
- **Endmembers:** how you chose them (lasso in the n-D view, **Suggest**,
  drawn on the image), and each class's pixel count (the **Pixels**
  column). Each endmember spectrum is the mean of its pixels in the
  prepared (windowed, filtered) image.
- **Identify:** the library and its version, any spectra you excluded, the
  comparison window if **Only** was on, and for each name the score, angle
  and fit RMS, plus any "close" matches.
- **Maps:** the method and its setting (SAM's maximum angle, the unmixing
  constraint, or MTMF's component count and the detection thresholds you
  kept).

Hourglass results (the MNF, PPI and map images, and MTMF detections) carry
only a one-line description, such as "Spectral Angle Mapper (SAM) of scene
(max angle 0.1 rad)", not the Processing menu's full record. The
description doesn't mention the wavelength window, IOVF, or which pixels
made each endmember. Keep these yourself:

- **Save Workflow…** writes a JSON file with the image's name and path, the
  wavelength window, IOVF on or off, the kept components, the PPI settings,
  counts and total iterations, the endmember classes with their pixels, and
  the excluded library spectra. It doesn't keep the library chosen, the
  **Only** window or the map settings.
- **Save…** (endmember table) keeps each class's name, color,
  identification and pixel list. Pixels are 0-based flat indices (row ×
  image width + column), so you can recompute each class's mean and spread
  elsewhere. **Export Spectra…** writes the mean spectra only.
- The MNF image added to the project has no eigenvalues or inverse attached,
  so **Eigenvalue Plot** and **Inverse Transform** can't use it. Read the
  eigenvalues from the Reduce page's plot, or run **Processing → Transforms
  → MNF** (see [PCA, MNF and ICA](transforms.md)) for a result that keeps
  them.
- Class values in a SAM map are 0, 1, 2… in the order of the endmembers
  (the order of the `Angle(…)` bands); unclassified pixels are NaN. The
  names travel with the result in Varda and sessions, not in exported files.

Settings that aren't in the workspace:

| Step | Setting |
| --- | --- |
| Prepare | Bands marked bad in the header are dropped; a pixel's no-data bands are filled by linear interpolation along its spectrum, and pixels missing more than half their good bands are left out |
| IOVF | Window 7 rows × 5 columns × 5 bands; reference spectrum a 19-band running median, then a Savitzky–Golay smooth (9 bands, cubic); two-sided Grubbs test at α = 0.125 (0.05 for edge windows under 45 voxels); a voxel is replaced with 5 or more votes, by the Gaussian-weighted mean of its unflagged, valid neighbors (weights renormalized over them; the reference value when none is left); stops when a round replaces under 1% of the first round's voxels, or after 200 rounds |
| MNF | Noise covariance from differences between each pixel and the next one in its row, divided by √2 (Green et al. 1988); every component is computed |
| Suggested components | Those with an MNF eigenvalue above 2 (eigenvalues are about SNR + 1), but no more than the elbow of the eigenvalue curve (the point of the log curve farthest from the line joining its ends); at least 1 |
| PPI | Skewers are random unit vectors (normalized Gaussian draws); a pixel scores once per skewer if its projection is within the threshold of either end. The seed is random and not recorded |
| Suggest | Corners found by successive projection (ATGP-style, after Ren & Chang 2003), starting from the candidate farthest from the centroid; each candidate joins its nearest corner if within 0.2 × the shortest corner-to-corner distance, others stay unassigned |
| Identify | Library resampled to the image's bands with a Gaussian band response when the header gives FWHM, otherwise linearly interpolated at band centers; library spectra overlapping fewer than 5 bands are skipped |
| Unmixing (fully constrained) | Exact for up to 10 endmembers (every subset of endmembers is solved); above 10, ADMM with simplex projection (Duchi et al. 2008), up to 2,000 iterations, stopping when abundances change by less than 10⁻⁶ |
| MTMF | Runs on the kept MNF components; the target is the mean MNF position of the endmember's pixels; the background mean and covariance come from every valid pixel |
| MTMF review | Lines start at MF ≥ 0.5 and infeasibility ≤ 5.0; the plot shows at most 30,000 pixels (a fixed random sample), but the count and detections use every pixel |

**The Processing menu versions** differ as follows:

- They read every good band: bands marked bad in the header are left out,
  as here. There's no wavelength window or IOVF unless you ran them first.
- Each endmember is a ROI class's mean over the union of its ROIs.
- **Pixel Purity Index (PPI)** runs on the leading **Bands Used** (default
  10) good bands of any image. Its **Threshold** (default 2.5) is in that image's data
  units: noise sigmas only for an MNF result.
- **MTMF** computes its own MNF from all good bands with the horizontal noise
  estimate (not selectable), keeping **MNF Components** (default 10).
- Their results do carry the full Processing record (settings, input,
  Varda version).

### Uncertainty and quality

- **PPI is random and not reproducible.** Its seed isn't set or recorded,
  so a second run gives different counts and can change which pixels
  become candidates. A count is a sampled frequency: for a pixel that is
  extreme with probability *p*, a count from *N* skewers has a standard
  deviation of √(*N p* (1 − *p*)). Report the total iterations and keep
  the pixel lists (endmember **Save…** or **Save Workflow…**); they, not
  the counts, are what later steps used. To check stability, start over
  from Pixel Purity, run again, and compare the candidates.
- **Run More adds to the existing counts as they are.** If you changed the
  threshold or the kept components in between, the counts mix two
  settings, and only the last threshold is recorded. Use **Run PPI** after
  any change.
- **The MNF eigenvalues** are about SNR + 1 under the noise estimate, so 1
  is pure noise. The horizontal estimate assumes the scene is smooth from
  one pixel to the next and the noise isn't correlated between neighbors;
  stripes along rows or columns make the floor sit above 1. The PPI
  threshold and MTMF infeasibility are in noise sigmas of this estimate.
- **Endmembers are image spectra, not pure minerals.** They're means of the
  pixels you picked, which may themselves be mixtures. Varda doesn't report
  their spread; compute it from the saved pixel lists if you need it, and
  report the pixel counts. **Suggest** is deterministic for a given set of
  candidates, but the candidates depend on the PPI run.
- **The Identify score** ranks; it isn't a probability or a significance
  test. It's the mean of three parts, each 0 to 1:
  - *Angle:* 1 − angle / 0.25 rad, clipped to 0 to 1 (0.25 rad or more
    scores 0). The **Angle** column is the spectral angle in radians.
  - *Absorption shape:* the correlation between the two spectra's
    continuum-removed depth profiles (1 − continuum-removed value, the
    continuum being each spectrum's upper convex hull over the compared
    bands), with negative correlations scored 0. Two featureless spectra
    (no depth of 0.01 or more) score 1; one featureless and one with
    features score 0.
  - *Binary encoding:* the fraction *f* of bands where both spectra are on
    the same side of their own mean, scored (*f* − 0.5) / 0.5 and clipped,
    so chance agreement (0.5) scores 0. It isn't shown in the table.

  **Fit RMS** isn't part of the score. It's the RMS difference between the
  endmember's continuum-removed depths and the library's, after scaling the
  library's depths by least squares: unitless, as a fraction of the
  continuum. A match within 10% of the best score is shaded as "close";
  report close matches as alternatives, since the score can't tell them
  apart. Matching ignores overall brightness but not additive offsets,
  and depends on the library's grain size and conditions (see
  [Precision is not accuracy](reporting-results.md#precision-is-not-accuracy)).
- **SAM** angles are in radians. The class map depends on the maximum angle
  (default 0.10 rad, ENVI's default): report it, and check how the
  classified area changes if you vary it. Varda gives no angle expected
  from noise alone.
- **Unmixing RMS Error** is each pixel's root mean square residual over the
  bands, in the input's data units. Compare it with the noise level (for
  example the standard deviation in a uniform area, from ROI statistics);
  spatial structure in it points to a missing endmember. Varda reports no
  uncertainty on the abundances themselves. Unconstrained and sum-to-one
  abundances can fall below 0 or above 1, which also flags a poor
  endmember set; the fully constrained fit hides that, so check its RMS
  error. Above 10 endmembers, whether ADMM converged isn't reported.
- **MTMF**: the MF score estimates the target's abundance (0 = background,
  1 = the target's mean spectrum) and can fall outside 0 to 1.
  Infeasibility is the pixel's distance, in noise sigmas, from where a
  mixture of background and that much target should lie. Trust high scores
  only with low infeasibility. Thresholds are your choice: report them (the
  detections image's description records them) and the detected pixel
  count.

### References

- MNF: Green, A. A., Berman, M., Switzer, P., & Craig, M. D. (1988). A
  transformation for ordering multispectral data in terms of image quality
  with implications for noise removal. *IEEE Transactions on Geoscience
  and Remote Sensing*, 26(1), 65–74.
- PPI: Boardman, J. W., Kruse, F. A., & Green, R. O. (1995). Mapping
  target signatures via partial unmixing of AVIRIS data. *Summaries of the
  Fifth Annual JPL Airborne Earth Science Workshop*, JPL Publication 95-1,
  23–26.
- n-D visualization and MTMF: Boardman, J. W., & Kruse, F. A. (2011).
  Analysis of imaging spectrometer data using N-dimensional geometry and a
  mixture-tuned matched filtering approach. *IEEE Transactions on
  Geoscience and Remote Sensing*, 49(11), 4138–4152.
- ATGP: Ren, H., & Chang, C.-I. (2003). Automatic spectral target
  recognition in hyperspectral imagery. *IEEE Transactions on Aerospace and
  Electronic Systems*, 39(4), 1232–1249.
- SAM: Kruse, F. A., Lefkoff, A. B., Boardman, J. W., Heidebrecht, K. B.,
  Shapiro, A. T., Barloon, P. J., & Goetz, A. F. H. (1993). The spectral
  image processing system (SIPS)—interactive visualization and analysis of
  imaging spectrometer data. *Remote Sensing of Environment*, 44(2–3),
  145–163.
- FCLS: Heinz, D. C., & Chang, C.-I. (2001). Fully constrained least
  squares linear spectral mixture analysis method for material
  quantification in hyperspectral imagery. *IEEE Transactions on
  Geoscience and Remote Sensing*, 39(3), 529–545.
- Simplex projection (ADMM unmixing): Duchi, J., Shalev-Shwartz, S.,
  Singer, Y., & Chandra, T. (2008). Efficient projections onto the
  l1-ball for learning in high dimensions. *Proc. 25th International
  Conference on Machine Learning*, 272–279.
- IOVF: Phillips, M. S., Murchie, S. L., Seelos, F. P., Hancock, K. M.,
  Selby, C., Poffenbarger, R. T., Stephens, D. C., & Kawamura, M. (2024). A
  first look at CRISM hyperspectral mapping mosaicked data: results from
  Mawrth Vallis. *Icarus*, 419, 115712.
  https://doi.org/10.1016/j.icarus.2023.115712 (section 2.2 describes the
  filter, there called an iterative kernel filter).
  Its parts: Grubbs, F. E. (1969).
  Procedures for detecting outlying observations in samples.
  *Technometrics*, 11(1), 1–21; Savitzky, A., & Golay, M. J. E. (1964).
  Smoothing and differentiation of data by simplified least squares
  procedures. *Analytical Chemistry*, 36(8), 1627–1639.
- CRISM MICA library: Viviano-Beck, C. E., Seelos, F. P., Murchie, S. L.,
  et al. (2014). Revised CRISM spectral parameters and summary products
  based on the currently detected mineral diversity on Mars. *Journal of
  Geophysical Research: Planets*, 119(6), 1403–1431.
- USGS library (bundled splib07a): Kokaly, R. F., Clark, R. N., Swayze,
  G. A., et al. (2017). *USGS Spectral Library Version 7*. U.S. Geological
  Survey Data Series 1035.
