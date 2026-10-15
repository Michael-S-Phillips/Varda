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

Images need to be map-projected (raw camera cubes can be projected with
ISIS cam2map: see [Optional Features](optional-features.md#isis-mosaicking)).
They start where their georeferencing puts them. To correct one, select it
in the Images list, then align it automatically, nudge it, or place tie
points by hand.

### Auto Align

**Auto Align…** finds tie points between the selected image and the images
it overlaps, and fits them:

1. **Bands:** for spectral cubes, Varda estimates each band's SNR (scene
   contrast over noise, from neighboring-pixel differences) and matches on
   the best few bands (5 by default), spread across the spectrum and
   skipping bad bands. Grayscale images use their one band.
2. **Matching:** both images are resampled onto their overlap. A coarse
   offset comes from phase correlation on a reduced copy, then a grid of
   tiles (64 px by default, overlapping) is phase-correlated to about
   0.1 px. Tiles without enough texture, or that correlate poorly once
   aligned, are dropped.
3. **Sub-pixel refinement** (on by default) refines each tile to about
   1/50 px with the phase-plane fit of Leprince et al. (2007), the method
   behind COSI-Corr, re-implemented from the paper.
4. **Features:** when phase correlation finds too few matches (a large
   rotation or scale difference, say), ORB features are matched instead.
   Choose **Features** to use them directly, or **Ames Stereo Pipeline**
   to have ASP's `image_align` match each chosen band (set it up in
   [Optional Features](optional-features.md#ames-stereo-pipeline-mosaicking)).
   With PyTorch installed (Optional Features), two more matchers run in its
   environment: **Learned features (LoFTR)**, which finds matches where
   hand-crafted features struggle (its weights download once), and **SIFT**.
5. **Fit:** the tie points from every band are fitted together with the
   image's transform, robustly (RANSAC): points farther off than the
   **outlier threshold** (1 px by default) are left out and shown in red.
   Manual tie points are never left out.

The results list each band's points, how many the fit kept and their RMS.
A band whose points disagree (an atmospheric band or a detector artifact,
say) shows up with a high RMS or few kept points: untick it to fit without
it. Running Auto Align again replaces the image's automatic tie points and
keeps the manual ones; **Delete Automatic** removes them.

**Add Displacement Field to Images** adds the tile shifts as an image: east
and north displacement (map units) and match quality, tile by tile over the
overlap, as COSI-Corr produces. It's useful beyond mosaicking, for example
to look for change or deformation between two dates.

### By hand

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
| Polynomial (2nd or 3rd order) | Distortion that varies smoothly across the image | 6 or 10 |
| Thin-plate spline | Local warps: bends through every tie point | 4 (many more in practice) |

Pick the simplest transform that removes the misalignment (for
map-projected images, usually translation or affine). Polynomials and
thin-plate splines are for images whose distortion varies across them, such
as pushbroom strips that weren't map-projected; map-projecting them first
(ISIS `cam2map` for CTX) is better when you can. A thin-plate spline needs
tie points spread over the whole overlap, and is only trustworthy between
them; Auto Align provides that density: a model with more
freedom fits the points you placed but can bend the image between them.
**Reset Alignment** returns the image to its original georeferencing.

## Balancing brightness

Images taken at different times or angles differ in brightness. The
**Radiometry** tab (beside Tie Points) corrects that from the overlaps, band
by band, without changing the images themselves:

- **None** (the default): every spectrum stays exactly as measured.
- **Linear, to the held images:** each image overlapping a held image gets
  a gain and offset per band, from a robust regression of the held image's
  values on its own in their overlap.
- **Linear, global least squares** (as ISIS `equalizer`): every overlap is
  solved together, so images that only overlap each other are balanced
  through their neighbors. Gains make each overlap's standard deviations
  agree, then offsets make its means agree. Every image must connect,
  through overlaps, to a held image; Varda says which don't.
- **Histogram matching:** maps each image's values onto its neighbor's,
  outward from the held images. It's non-linear and changes spectral shape,
  so the exported mosaic is labeled "(visual)".

**Fit** chooses gain and offset, gain only or offset only for the linear
methods. **Held** images keep their values (the top image, by default).
With [ISIS](optional-features.md#isis-mosaicking) installed, **Compare with
ISIS equalizer** solves the same balance with ISIS and shows its gains and
offsets beside Varda's (and **Use ISIS's Corrections** applies them).
Statistics come from a subsample of each overlap. The table shows each
image's mean gain and offset; hover for every band. The corrections are
saved with the session and recorded in the exported mosaic's metadata.

## Seams

By default the stack order decides: where images overlap, the top one wins.
The **Seams** tab can split each overlap between the two images instead:

- **Middle of each overlap (Voronoi):** each overlap pixel goes to the image
  whose own part of the scene is nearer, so the seam runs down the middle.
- **Least difference:** the seam follows the path where the two images
  differ least (after any radiometric balancing), so it's hard to see.

**Find Seams** computes them (from a reduced copy of each overlap) and
outlines, on the mosaic, the area where the lower image takes over. **Edit on
Mosaic** makes the outlines draggable: move a corner, or double-click an
edge to add one. **Clear** returns to the stack order. Seams are kept in map
coordinates, so they look the same at any export resolution; find them again
after changing the alignment.

Seams only choose which image each pixel comes from: spectra stay exact.

### Blending (visual)

For a mosaic meant to be looked at, **Blending** (in the same tab) softens
the seams, or the stack order's edges when there are no seams:

- **Feather:** each image fades into the next over the **feather width**
  (in pixels of the finest image), centered on the seam.
- **Multi-band:** coarse detail (overall brightness) mixes over a wide band
  and fine detail over a narrow one (Burt and Adelson's method), which hides
  brightness differences without blurring texture. **Levels** sets how wide
  the coarsest band is: each level doubles it.

Blending mixes the images' spectra near the seams, so a blended mosaic is
labeled "(visual)". Keep **None** for analysis.

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
mosaic's metadata records the inputs, the resampling, the radiometric
corrections, the seams and the full recipe.

Saving the session keeps each Mosaic workspace's recipe (order, visibility,
alignments and tie points), so you can reopen it and keep working.
