# Target detection

Tools in **Processing → Target Detection** that score every pixel: how
unusual it is (**RX Anomaly (Global)** and **RX Anomaly (Local)**), or how
much it looks like a target spectrum you give (**ACE Target Detection** and
**Matched Filter**). Each makes a new image of scores over the same pixels
and georeferencing. A score is not a probability or a detection: you choose
the threshold that turns scores into detections, and you report it.

What they share:

- **Background statistics.** The background is the whole scene: the mean
  and covariance of its valid pixels, from a random sample of at most
  200,000 of them on larger images (the sample is fixed, so runs repeat).
  The covariance is the sample covariance (dividing by N − 1). Target pixels
  are part of the background too.
- **Missing values.** No-data values and bad bands are filled by linear
  interpolation along each pixel's spectrum. A pixel missing more than half
  of its good bands is no data in the result.
- **Bad bands are kept** (as filled values), not removed; see [Uncertainty
  and quality](#uncertainty-and-quality). To leave them out, make a copy
  without them first with **Processing → Geometry → Subset (Crop Rows,
  Columns, Bands)**.

## RX Anomaly (Global)

The Reed–Xiaoli detector: each pixel's squared Mahalanobis distance from the
scene's mean, (x − μ)ᵀ C⁻¹ (x − μ), with μ and C the background mean and
covariance. Pixels unlike the rest of the scene score high. It has no
settings.

**Output:** one band, "RX score", unitless and 0 or more.

## RX Anomaly (Local)

The same distance, but from the mean of each pixel's surroundings: a square
outer window with a square inner (guard) window left out, so a small target
doesn't count toward its own background. The covariance is still the whole
scene's, not each window's.

| Setting | Meaning | Default | Range |
|---|---|---|---|
| **Inner Window** | Guard window, pixels on a side | 3 | 1–31 |
| **Outer Window** | Background window, pixels on a side | 15 | 3–101 |

Both must be odd: an even size is raised by one (4 becomes 5). The outer
window is made at least 2 pixels larger than the inner one. The sizes used
are in the result's name ("local RX 3/15"), so check them there. The
background mean is over the outer² − inner² pixels between the two windows
(15² − 3² = 216 by default). At the image's edges the windows are mirrored
back into the image, and no-data pixels inside a window count as the
scene's mean.

**Output:** one band, "Local RX *inner*/*outer*", unitless and 0 or more.

## ACE Target Detection

The adaptive coherence (or cosine) estimator. Both the pixel and the target
have the background mean subtracted and are whitened by the background
covariance; the score is the squared cosine of the angle between them:

(sᵀ C⁻¹ x)² / ((sᵀ C⁻¹ s)(xᵀ C⁻¹ x)), with s and x the target and pixel
minus the background mean.

It ignores brightness (scaling a pixel doesn't change its score).

| Setting | Meaning | Default |
|---|---|---|
| **Targets (ROI classes)** | The ROI classes to detect; each class's mean spectrum (over all its ROIs, valid pixels only) is one target | Every class |

Draw an ROI on the target material first.

**Output:** one band per target, named after its ROI class, from 0 (no
resemblance) to 1. Because the cosine is squared, a pixel pointing directly
*away* from the target also scores near 1; the Matched Filter's sign tells
them apart.

## Matched Filter

An estimate of how much of the target is in each pixel, suppressing the
background:

(s − μ)ᵀ C⁻¹ (x − μ) / ((s − μ)ᵀ C⁻¹ (s − μ)), with s the target and μ the
background mean.

| Setting | Meaning | Default |
|---|---|---|
| **Targets (ROI classes)** | As for ACE | Every class |

**Output:** one band per target, named after its ROI class: 1 at the target's
mean spectrum, 0 at the background mean. It isn't limited to 0–1: it is
negative where pixels lie on the other side of the background mean, and can
exceed 1. Unlike Mixture Tuned Matched Filtering, it has no infeasibility
score, so a pixel can score high without being a plausible mixture of target
and background. For that check, use **Processing → Endmembers → Mixture
Tuned Matched Filtering (ROI Endmembers)** or the [Spectral
Hourglass](spectral-hourglass.md).

## Reporting your results

What to state in a methods section, what the quality measures mean, and
what to cite. See also [Reporting results from Varda](reporting-results.md)
for what applies to every process.

### What to state

- The detector, and for Local RX the window sizes actually used (from the
  result's name).
- The bands used, and whether you removed bad bands first (Subset) or let
  Varda fill them.
- That the background mean and covariance are the whole scene's (for Local
  RX, a local mean with the scene's covariance), from at most 200,000
  sampled pixels.
- For ACE and the Matched Filter: each target's ROI class, its number of
  pixels, and how you chose them. The target is their mean spectrum.
- The **threshold** you applied to the scores, how you chose it, and the
  detection and false-alarm rates you measured (below).

### Uncertainty and quality

- **Scores aren't probabilities.** Varda outputs raw scores with no p-value,
  confidence or false-alarm rate. Choosing the threshold, and reporting
  what it means, is up to you.
- **A threshold for RX.** If the background were Gaussian, the global RX
  score of a background pixel would follow (approximately, since μ and C are
  estimated) a χ² distribution with B degrees of freedom, B being the number
  of bands. A threshold for a false-alarm rate α is then the χ² quantile at
  1 − α, e.g. in Python `scipy.stats.chi2.ppf(1 - 1e-3, B)`: 29.6 for 10
  bands, 149.4 for 100. Real backgrounds aren't Gaussian (they're mixtures of
  materials with heavier tails), so the actual false-alarm rate is usually
  higher than α. Check it on your data (below), and state the threshold as a
  score, not only as α. For Local RX the scores run somewhat higher, because
  the local mean is itself estimated from neighbors that are spatially
  correlated.
- **Bad bands and correlated bands.** Bands filled from their neighbors are
  copies or blends of other bands, which makes the covariance nearly
  singular: its inverse, and so every score, becomes numerically unstable,
  and the effective number of degrees of freedom drops to the number of
  good bands. Hundreds of highly correlated hyperspectral bands can do the
  same. Remove bad bands first (Subset), or reduce the data with [MNF or
  PCA](transforms.md) and run the detector on the leading components;
  report which.
- **Measure detection and false-alarm rates.** Make a 0/1 mask from a score
  band with **Processing → Image Math → Threshold to Mask**. Draw ROIs over
  areas you know to be background, and (if you have them) over known
  targets not used to define the target spectrum. In the ROI Manager, **Add
  Column...** → **Zonal statistic of a raster** → **mean** of the mask
  gives, for each ROI, the fraction of its pixels detected: the false-alarm
  rate over background ROIs, the detection rate over target ROIs. Report
  these with the threshold, and the number of pixels (**count**) behind each.
- **Target contamination.** The target pixels are part of the background
  statistics. A large or common target pulls the background mean and
  covariance toward itself and lowers its own scores. Keep this in mind when
  the target covers much of the scene.
- **The target is one mean spectrum.** Variation within the target class
  isn't modeled. Report the ROI's size and, if you can, its spectral spread
  (ROI statistics) so readers can judge how representative it is.
- **Matched Filter values as abundances.** A Matched Filter score near 0.3
  suggests about 30% of the target only if the pixel is a linear mixture of
  that target and the scene's background. Without an infeasibility check it
  can't tell that from a different material; prefer MTMF for abundance-like
  claims.

### References

- RX: Reed, I. S., & Yu, X. (1990). Adaptive multiple-band CFAR detection of
  an optical pattern with unknown spectral distribution. *IEEE Transactions
  on Acoustics, Speech, and Signal Processing*, 38(10), 1760–1770.
- ACE: Kraut, S., & Scharf, L. L. (1999). The CFAR adaptive subspace
  detector is a scale-invariant GLRT. *IEEE Transactions on Signal
  Processing*, 47(9), 2538–2541.
- Matched filter, ACE and detection in hyperspectral images: Manolakis, D.,
  & Shaw, G. (2002). Detection algorithms for hyperspectral imaging
  applications. *IEEE Signal Processing Magazine*, 19(1), 29–43.
- Implementation (global RX, ACE, Matched Filter and the background
  statistics): Spectral Python (SPy), by T. Boggs. Varda uses version 0.24
  (it accepts 0.24 to 0.25); **Help → Copy System Info** doesn't list it, so
  state the version from your installation (`pip show spectral`) if you ran
  Varda from source.
