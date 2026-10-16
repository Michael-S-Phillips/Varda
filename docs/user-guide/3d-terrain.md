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

Draping images that aren't on the DEM's grid (a CRISM parameter map over a
CTX DEM, say), with alignment, is coming next.
