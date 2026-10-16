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

## Weighted PCA

**Transforms → Weighted PCA** is PCA in which each value counts by its
weight, taken from another image on the same grid: per band (an image with
the same bands) or per pixel (one band). **Weights Are** says whether the
image holds weights, such as the number of samples behind each value, or
uncertainties σ (weighted 1/σ²).

Values with no weight change nothing: they don't bend the components, and
each pixel's scores are fitted to its weighted values only. Missing values
and bad bands have no weight. To leave out flagged values, weight them 0:
for a pipeline's sample counts and flags, make the weights with Band Math
(`COUNT * (FLAGS == 0)`). With equal weights it is ordinary PCA.

The covariance is the weighted one of Delchambre (2015, *MNRAS* 446,
3545). Each pixel's scores are a small fit, so Weighted PCA starts at 10
components rather than all of them. The result works with the Eigenvalue
Plot and Inverse Transform like the others.
