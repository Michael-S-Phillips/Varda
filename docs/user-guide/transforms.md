# PCA, MNF and ICA: choosing how many components to keep

The forward transforms (**Processing → Transforms**) default to every
component and attach the eigenvalues and inverse to the result.

1. Open the result in a workspace and step through its bands to see where the
   components turn into noise.
2. Use **Transforms → Eigenvalue Plot…** to plot and tabulate the eigenvalues
   (with % and cumulative variance), and drag a cutoff to where they flatten
   out.
3. Its button opens **Transforms → Inverse Transform (Keep N Components)** with
   that N preset. This rebuilds a denoised image in the original bands from
   the chosen components, or keeps just those component bands.

The first N components are ticked by default. Untick any (for example
component 1, to drop albedo) or type a range such as `3-19, 22`.

## Wavelengths and weights

PCA, MNF and ICA each choose what goes in:

- **Wavelengths** (from, to) keeps the bands in that range, as the Spectral
  Hourglass does; drop noisy ranges such as detector edges or water bands.
  Bands marked bad in the image are always left out. Inverse Transform then
  rebuilds just those bands.
- **Weights** (optional; none by default) gives each value a weight from
  another image on the same grid: per band (an image with the same bands)
  or per pixel (one band). **Weights Are** says whether that image holds
  weights, such as the number of frames behind each value, or uncertainties
  σ (weighted 1/σ²).

Values with no weight change nothing: they don't bend the components, and
each pixel's scores are fitted to its weighted values only. Missing values
have no weight. Make the weights with Band Math from a pipeline's
products, leaving out flagged values by weighting them 0. For MISE's
products, whose COUNT is the number of frames left out of a stack of 20
and whose FLAG05 marks values with more than 5 left out, that's
`(20 - COUNT) * (FLAG05 == 0)`. With equal weights each transform is the
ordinary one.

The weighted covariance is Delchambre's (2015, *MNRAS* 446, 3545). MNF
estimates the noise from neighbor differences weighted as both of their
values are, and keeps that estimate positive by blending it with its
diagonal when needed. ICA whitens with the weighted PCA. Each pixel's
scores are a small fit, so weighting takes longer with more components:
about 2 seconds for 40 components of a 320 × 300 × 421-band cube, a couple
of minutes for all of them.
