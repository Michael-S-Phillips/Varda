# 3D Terrain

Show a DEM as a lit, shadowed surface, drape an image on it, and export
figures and interactive web pages. Open it from **Workspace → New 3D Terrain
Workspace** with the DEM loaded.

## The surface

- **DEM**: any loaded elevation image (a single-band image is picked first);
  **Band** appears for multi-band images. No-data leaves holes.
- **Drape**: what covers the surface:
  - **None (shaded relief)**: a neutral surface, shaded by the sun;
  - **Elevation colors**, with a **Color map**;
  - any loaded image on the DEM's pixel grid, such as the orthoimage that
    comes with a USGS CTX or HiRISE DTM, rendered as it is in 2D (its bands,
    a 2-98 % stretch).
- **Detail**: how finely the surface follows the DEM: Low (512 points a
  side), Medium (1024) or High (2048). The status line says how the grid
  relates to the DEM's pixels.
- **Exaggeration** stretches the heights; **Sun azimuth** (clockwise from
  north) and **Sun elevation** place the light; **Cast shadows** and **Sky
  light** (which lifts the shadows) shape it; **Background** sets the color
  around the surface.

Drag to orbit, right-drag (or Shift-drag) to pan, and scroll to zoom.
**Reset View** returns to the starting view from the south. **Save View…**
keeps the current camera by name; double-click a saved view to return to it.
Views and settings are saved with the session.

## Block diagrams and 3D printing

- **Sides (block diagram)** stands the surface on walls down to a flat base,
  like a cut block. **Base depth** is how far below the lowest point the
  base is (Automatic: a quarter of the relief); it's exaggerated with the
  heights.
- **Fill gaps** (on by default) fills no-data gaps inside the DEM, such as a
  DTM's voids on steep slopes, from the heights around them, so they don't
  show as pits. No data around the outside of the DEM stays empty.
- **Export for 3D Printing…** saves the terrain as a closed solid in STL,
  the format slicers (Cura, PrusaSlicer, Bambu Studio and others) open.
  Choose the **width** in millimeters, the **exaggeration**, the **base**
  under the lowest point (3 mm by default), and the **detail** (points on
  the longer side; 512 suits most printers). The dialog shows the size it
  will print. The solid is watertight, with sides around any gaps left
  unfilled, so it's ready to slice.

## Figures and web pages

- **Export Still…** renders the view as a PNG at HD, 4K, 8K, a 3000 px
  square or any size up to 16384 px a side, optionally with a transparent
  background for compositing.
- **Export Web Page…** saves the view as one self-contained HTML file that
  opens in any modern web browser, with no server and nothing to install.
  Readers can orbit and zoom, and change the exaggeration, the sun and the
  shadows. It's suited to sharing with coauthors or publishing as
  supplementary material.

The 3D view needs WebGL 2 (any graphics from the last decade). If it isn't
available, the workspace says so; updating the graphics driver usually
helps.

## Overlays

Drape images that aren't on the DEM's grid, a CRISM parameter composite over
a CTX DEM say, on top of the surface:

1. **Add Overlay** lists the loaded, georeferenced images of the DEM's body.
   An overlay starts where its georeferencing puts it; images in another map
   projection are reprojected to the DEM's.
2. **Display…** sets its bands, stretch and color map as in the image views
   (for CRISM MTRDR summary products, e.g. OLINDEX3, LCPINDEX2, HCPINDEX2
   for the MAF composite). **Opacity** and the tick box change the view at
   once.
3. **Auto Align** matches the overlay's band with the best signal against
   **Align to**: an image on the DEM's grid (its orthoimage works best) or a
   hillshade of the DEM. It uses the Mosaic workspace's matching (phase
   correlation refined to a fraction of a pixel, with features as a
   fallback), and fits the **Model**: Translation by default, as
   map-projected products are mostly just offset, or rigid, similarity,
   affine, projective, polynomial or a thin-plate spline for warped ones.
   The panel reports the tie points used and their RMS residual.
4. **Shift E, N** moves the overlay by hand, in meters, after the fit;
   **Reset Alignment** returns it to its georeferencing.

Overlays and their alignments are saved with the session, and they're
included in stills and exported web pages (with their opacity).

Over Jezero, a CRISM MTRDR (FRT00005850) aligns to the USGS CTX DTM's
orthoimage with about ten tie points and an RMS of 10 m, half a CRISM pixel;
its georeferencing was off by about 160 m west and 340 m north.
