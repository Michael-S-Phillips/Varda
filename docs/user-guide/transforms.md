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
