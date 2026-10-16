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
  heights. **Side color** offers earth, light gray, white, dark gray, black
  or any color (Custom…).
- **Edges** shapes the outline where the data ends, in the view and in the
  printed solid: **Smooth** (the default) cuts the grid cells' corners and
  relaxes the outline, so a DEM whose footprint is tilted on the map gets
  clean sides; **Stepped** follows the grid cell by cell; **Trimmed to a
  rectangle** keeps the largest rectangle with data everywhere, for a block
  with straight sides and square corners.
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

## Lines

**Add Lines** drapes lines over the surface. Lines drawn with Draw Line in an
open General Image Analysis workspace are listed under its image's name
(any georeferenced image of the DEM's body, not only the DEM): add all of
them or one line at a time, each keeping its name and color. They're copied
in, so later edits in that workspace don't change them, and the session
keeps them even after that workspace is closed.

**From a File…** reads a vector file instead: a rover traverse or mapped
contacts (GeoJSON, GeoPackage, shapefile, KML). Polygons show as their
outlines. Longitude and latitude are taken as degrees on the DEM's body
(planetary GeoJSON files always claim Earth's), and other map projections
are converted to the DEM's. GeoJSON can't store a Mars map projection, so a
GeoJSON whose "degrees" are really projected coordinates is read in the
DEM's projection; a GeoPackage keeps the projection and is the safer choice.
Tick a layer to show or hide it; double-click it to change its color. Lines
follow the exaggeration and are saved with the session (files as their
paths).

The **Profiles** panel (below the view) plots the DEM along the selected
lines, or along every shown line when none is selected, with the same
readout, vertical exaggeration and CSV or image export as the Profiles tab
of General Image Analysis (see [Lines and profiles](lines-and-profiles.md)).

## Figures and web pages

- **Show** puts annotations on the view and in stills:
  - a **north arrow**, which turns with the camera;
  - a **scale bar**, the ground distance at the view's center (a
    perspective view has no single scale; it is most accurate in views from
    above), with the vertical exaggeration;
  - a **color bar** for the elevation colors drape: the color map over the
    elevation range it stretches across.

- **Export Still…** renders the view as a PNG at HD, 4K, 8K, a 3000 px
  square or any size up to 16384 px a side, optionally with a transparent
  background for compositing.
- **Export Animation…** renders a flyover: the camera circles the view's
  center (a full turn or a part of one) over as many frames as you choose,
  at HD, Full HD or square sizes. It's saved as an animated WebP (sharp and
  small), a GIF, or a folder of numbered PNG frames for a video editor.
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
2. The **Overlay Display** panel (it opens when you add an overlay;
   **Display…** brings it back) sets the selected overlay's mode, bands,
   stretch and color map as in the image views, with its histograms. Drag a
   histogram's edges to set the stretch. For a CRISM parameter cube, pick any
   three parameters for red, green and blue by name (OLINDEX3, LCPINDEX2,
   HCPINDEX2 for the MAF composite, say). The overlay redraws once you stop
   changing things. Like any panel, it can be docked beside the view or
   floated. **Opacity** and the tick box in the Overlays list change the
   view at once.
3. **Auto Align** matches the overlay's band with the best signal against
   **Align to**: an image on the DEM's grid (its orthoimage works best) or a
   hillshade of the DEM. It uses the Mosaic workspace's matching (phase
   correlation refined to a fraction of a pixel, with features as a
   fallback), and fits the **Model**: Translation by default, as
   map-projected products are mostly just offset, or rigid, similarity,
   affine, projective, polynomial or a thin-plate spline for warped ones.
   The panel reports the tie points used and their RMS residual.
   **Match using** chooses the image that is matched: the overlay itself,
   or another loaded image with the same georeferencing. A parameter map
   often has little texture to match, but a scene made from the same
   observation (its reflectance convolved to the reference camera's band,
   for example a CTX-like scene from CRISM) matches well, and the alignment
   found for it moves the overlay.
4. **Shift E, N** moves the overlay by hand, in meters, after the fit.
   **Alignment: Copy** and **Paste** give another overlay the same
   alignment (products of one observation share it); **Reset** returns the
   overlay to its georeferencing.

Overlays, their display settings and their alignments are saved with the
session, and they're
included in stills and exported web pages (with their opacity).

Over Jezero, a CRISM MTRDR (FRT00005850) aligns to the USGS CTX DTM's
orthoimage with about ten tie points and an RMS of 10 m, half a CRISM pixel;
its georeferencing was off by about 160 m west and 340 m north.
