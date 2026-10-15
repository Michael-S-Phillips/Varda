# Mosaicking

**Workspace → New Mosaic Workspace…** joins overlapping images into one. Pick
two or more images with the same bands and map projection: spectral cubes
(such as CRISM strips) or grayscale images (such as CTX). Nothing is
resampled until you export, so you can reorder and realign the images as
often as you like.

The workspace has three panels:

- **Images** lists the inputs in priority order. Where images overlap, the
  one higher in the list wins (**Move Up**/**Move Down** to reorder). Uncheck
  an image to hide it from the preview.
- **Mosaic** previews the result in map coordinates, with the selected image's
  footprint outlined in yellow.
- **Tie Points** shows the reference image and the selected (moving) image
  side by side, for matching features between them.

## Aligning an image

Images start where their georeferencing puts them. To correct one, select it
in the Images list, then:

- **Nudge it**: click the mosaic, then use the arrow keys to move the image by
  one output pixel (Shift: ten).
- **Fit it to tie points**: choose the reference image, then click a feature
  on the reference and the same feature on the moving image. Repeat for a few
  well-spread features, choose a transform and press **Fit to Tie Points**.
  The status line reports the fit's RMS error in pixels, and the table shows
  each point's residual; uncheck **Use** to leave a poor point out of the next
  fit.

| Transform | What it corrects | Tie points needed |
| --- | --- | --- |
| Translation | A shift | 1 |
| Rigid | Shift and rotation | 2 |
| Similarity | Shift, rotation and uniform scale | 2 |
| Affine | Also shear and different x and y scales | 3 |
| Projective | Also perspective | 4 |

Pick the simplest transform that removes the misalignment: a model with more
freedom fits the points you placed but can bend the image between them.
**Reset Alignment** returns the image to its original georeferencing.

## Exporting

**Export Mosaic…** renders the mosaic and adds it to the image list:

- **Resampling**: *Nearest neighbor* (the default) copies each output pixel
  from one input pixel, so every spectrum in the mosaic is a real measured
  spectrum. *Bilinear* looks smoother but blends neighboring spectra; its
  result is named "(visual)" so it isn't mistaken for science data.
- **Pixel size**: defaults to the top image's. The output grid is aligned
  with the top image's pixels, so at that size its pixels are copied
  unchanged (unless you rotate or warp it).
- **Source map**: a class map of which image each mosaic pixel came from,
  useful for checking seams and tracing a spectrum back to its strip.

Seams are hard (no blending), so spectra are never mixed across them. The
mosaic's metadata records the inputs, the resampling and the full recipe.

Saving the session keeps each Mosaic workspace's recipe (order, visibility,
alignments and tie points), so you can reopen it and keep working.
