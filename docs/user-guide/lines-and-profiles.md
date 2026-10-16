# Lines and profiles

Draw lines on an image and plot a band along them: most often a topographic
profile across a DEM. Lines work in the General Image Analysis workspace.

## Draw a line

1. In the **Lines** tab (beside the ROI Manager), pick what to draw:
   - **Straight**: drag from one end to the other, or click both ends.
   - **Polyline**: click each vertex; double-click, right-click or press
     Enter to finish. Backspace removes the last vertex.
   - **Freehand**: press, drag and release. The stroke is thinned to a
     polyline that follows it within a pixel.
2. Turn on **Draw Line** under any view and draw. It stays on, so you can draw
   line after line. Esc drops the line in progress; Cmd-drag (Ctrl-drag on
   Windows and Linux) pans the view, even partway through a line.

Each line is shown on every view in its color. In the Lines tab you can
rename a line (double-click its name), change its color (double-click the
swatch), delete lines, and export them as GeoJSON, GeoPackage or a
shapefile, in the image's map coordinates. Lines are saved with the session.
On a georeferenced image, a 3D Terrain workspace can drape them over a DEM
(its **Add Lines** menu lists the open workspaces' lines; see
[3D Terrain](3d-terrain.md)).

## Profiles

The **Profiles** tab plots the selected lines, or every line when none is
selected, one curve per line in the line's color. Choose the **band** to
sample (a DEM has one).

- Samples are about a pixel apart along the line, interpolated between pixel
  centers; no-data shows as gaps.
- Distance is in meters for georeferenced images: straight-line in a
  projected map, along the body's surface (geodesic) in longitude and
  latitude. Long profiles switch to kilometers. Without georeferencing,
  distance is in pixels.
- Hover over the plot to read the distance and each line's value there; a
  white × marks the same spot on the image.
- For a DEM in meters, the **vertical exaggeration** of the current view is
  shown under the plot and changes as you zoom.

**Export…** saves every sample as CSV (line, distance, pixel position, map
position and value), or the plot as PNG (at least 2000 px wide), SVG or PDF
for a figure.
