# Linked Images

**Workspace → New Linked Images Workspace…** views any number of images
side by side, linked so that one cursor and one line read them all. It's
made for checking the products of a processing pipeline against each other:
a result next to its sample counts, flags and exclusions, say, all on one
grid.

## Opening one

The dialog lists the loaded images, with those on the first image's pixel
grid already ticked. Choose two or more, and how to link them:

- **By pixel:** the same pixel in every image. Use it for products of one
  pipeline, which share a grid.
- **By map location:** the same place on the ground. Use it for images on
  different grids or map projections (each must be georeferenced; an image
  without georeferencing is linked by pixel).

## Reading every image at once

- The views pan and zoom together.
- **Ctrl+click** in any view puts the cursor (yellow) on every view, and the
  **Linked Spectra** panel plots each image's spectrum there, one plot per
  image so that each keeps its own units (a spectrum, a count, a flag); each
  plot pans and zooms on its own. **Ctrl+drag**
  updates the spectra as you go. Bad bands and no-data values show as gaps.
  **Export…** saves the spectra at the cursor as CSV.
- A **bit mask** shows as bits by wavelength instead of a number: a
  pipeline's per-frame exclusions (bit *i* set where frame *i* of a stack
  was left out) become a chart of which frames were left out at each
  wavelength, titled with how many. Whole-number images named like masks
  (EXCLUDE, MASK, BITS, QA, quality) start that way; the **As Bits** button
  switches any whole-number image. **Processing → Statistics → Decode Bit
  Mask** turns a mask into images: the number of bits set, one bit, or any
  of several.
- **Draw Line** in any view draws a line on all of them, and the **Linked
  Profiles** panel plots each image's profile along it (pick the band for
  each). The **Lines** panel renames, recolors, deletes and exports lines;
  selecting lines shows only their profiles. See
  [Lines and profiles](lines-and-profiles.md).
- The **Display** panel sets each image's bands, stretch and color map,
  with its histograms below.
- **Crop** makes a cropped copy of the image it's used on.

## Arranging the windows

Every view and panel is a window of its own inside the workspace: drag one
by its title to put it beside, above or below another, drop it on another
to share a tab, or float it (its title bar's button) and put it on a second
screen. The views start in a grid, with Display and Lines on the left and
the spectra and profiles on the right. Views can't be closed, so none gets
lost; panels can, and drawing a line brings Linked Profiles back.

The images, the link, the cursor, the lines and each image's display
settings are saved with the session.
