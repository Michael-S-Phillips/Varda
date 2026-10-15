# Factor Analysis Target Transformation (FATT)

**Processing → Endmembers → Factor Analysis Target Transformation…** asks
which library spectra could be components of an image. The image's spectra
are treated as mixtures of a few components. Factor analysis finds the space
those mixtures span. A library spectrum that the space reproduces well (its
*target transformation*) is a candidate component (Bandfield et al. 2000;
Thomas & Bandfield 2017; Lin, Tarnas et al. 2021).

FATT finds **candidates, not detections**. Confirm a target, for example
with ratioed spectra, before reporting it.

## Ranking library targets

1. Choose the image and the spectra to analyze:
   - every Nth pixel of the whole image (every 3rd by default);
   - or the pixels of an ROI class in the current workspace.
2. Set the wavelength range. The default is 1.7–2.6 µm, where most
   diagnostic hydrated-mineral features are, when the image covers it. The
   image's bad bands are left out.
3. Choose the decomposition:
   - **Covariance (mean removed)**: the eigenvectors of the covariance matrix
     plus the mean spectrum (Bandfield, Thomas).
   - **Hysime**: the signal subspace of the correlation matrix, with its size
     chosen by comparing signal and noise power (Lin, Tarnas et al.).
4. Press **Analyze**. The plot shows Malinowski's indicator function (IND).
   Its minimum, or Hysime's count, suggests how many factors to keep; drag
   the cutoff to change it. More factors fit the targets better, but they
   also fit noise and processing artifacts, so expect more false positives.
   10–15 is typical for CRISM.
5. Pick a library (MICA numerators for CRISM, USGS minerals, or **Load
   Library…**). Every spectrum is resampled to the image's bands and ranked
   by **normalized RMSE**: the RMSE after dividing both spectra by their sum,
   so brightness doesn't matter. Targets below the threshold are shaded
   green. Select a target to compare it with its target transformation.

The default threshold, 1.5 × 10⁻⁴, was set by Lin, Tarnas et al. (2021) for
CRISM I/F over 1.7–2.6 µm (about 130 bands). It scales with the number of
bands, and in principle each mineral deserves its own, so treat it as a
starting point.

## Mapping where targets fit

Tick targets in the **Map** column and press **Map Ticked Targets…**. This
runs DAFA/TT (Lin, Tarnas et al. 2021):

- FATT runs in small moving windows of about 50 pixels in three shapes
  (7×7, 5×10 and 10×5), stepped one pixel at a time.
- A pixel counts for a target only when every shape has a window containing
  it in which the target fits.

The result joins the image list. Its first band is the number of targets
detected at each pixel; then there's one band per target with its
normalized RMSE, so you can threshold a target differently later.
*Factors per window* (15 by default) is the dimension of each window's
factor space.

A phase must add variance to the spectra in a window to be found: a phase
spread evenly across the window, under about half a pixel, or masked in a
mixture can be missed.
