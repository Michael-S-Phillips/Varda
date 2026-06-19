# Viewport Pixel Readout HUD — Design

## Goal

Add a small always-on readout in the bottom-left corner of every image viewport
that, while the cursor hovers over the image, displays:

- the pixel coordinate (column, row)
- the geospatial coordinate, when the image has a CRS — both native CRS
  coordinates and reprojected WGS84 lat/lon degrees
- the raw band data value(s) for the currently-displayed band(s): a single
  `Value` in MONO mode, or `R`/`G`/`B` in RGB mode

## Scope decisions

- Built into `ImageViewport`, so every viewport (the three in `TripleRasterView`,
  dual-image view, etc.) gets the readout for free.
- Pixel values shown are **raw band data values** for the displayed bands (the
  actual underlying data, not the stretched 0–255 display values).
- HUD sits **bottom-left, always on** — visible whenever the cursor is over the
  image, hidden otherwise. No toolbar toggle.
- Geospatial display shows **native CRS coordinates and lat/lon degrees**.

## Architecture

Two touched files. No new files. No unit tests for the readout (simple
high-level glue).

### 1. `VardaRaster` — reprojection method (`varda_raster.py`)

Reprojection to lat/lon must NOT live in the readout code. Add it to
`VardaRaster`, which already exposes `crs` and `pixelToGeo()`:

```python
@cached_property
def _wgs84Transformer(self) -> Transformer | None:
    if self.crs is None:
        return None
    return Transformer.from_crs(self.crs, CRS.from_epsg(4326), always_xy=True)

def pixelToLatLon(self, col: int, row: int) -> tuple[float, float] | None:
    """Pixel center as (lat, lon) in WGS84 degrees, or None if no CRS."""
    if self._wgs84Transformer is None:
        return None
    x, y = self.pixelToGeo(col, row)
    lon, lat = self._wgs84Transformer.transform(x, y)
    return lat, lon
```

`pixelToGeo()` already returns native-CRS coordinates (verified: rasterio source
calls `src.xy()` with no reprojection). The readout calls `pixelToGeo()` for the
native pair and `pixelToLatLon()` for degrees — it never touches pyproj directly.

### 2. `ImageViewport` — overlay, hover wiring, formatting (`image_viewport.py`)

- **`_PixelReadoutOverlay(QLabel)`** — a semi-transparent dark label parented to
  `ImageViewport` (not added to the pyqtgraph scene, so pan/zoom never moves it).
  Floated to the bottom-left in the viewport's `resizeEvent`. Methods:
  `showReadout(text)` / `hideReadout()`.

- **`_buildReadoutText(col, row) -> str`** — formats the readout lines. Reads
  displayed-band raw values from the image, native geo via `pixelToGeo()`, degrees
  via `pixelToLatLon()`.

- **Hover wiring** in `__init__`: connect `self._gv.scene().sigMouseMoved` to
  `_onHover`. `_onHover` maps scene → imageItem-local → full-image pixel
  (reusing the existing `imageItem.mapFromScene` + `localToImage` path), hides the
  overlay when the pixel is outside `[0, width) × [0, height)`, otherwise updates
  it. The GraphicsView `leaveEvent` also hides the overlay.

## Data flow

```
GraphicsScene.sigMouseMoved(scenePos)
  -> ImageViewport._onHover(scenePos):
       local = imageItem.mapFromScene(scenePos)
       col, row = imageItem.localToImage(local)   # handles region display
       if out of [0,width) x [0,height): overlay.hideReadout()
       else: overlay.showReadout(self._buildReadoutText(col, row))
GraphicsView leaveEvent -> overlay.hideReadout()
```

Displayed bands are read live from `self._imageRenderer.settings` each hover so a
band/mode change is reflected immediately:

- MONO: one entry, label `Value`, index `settings.mono.band`
- RGB: three entries `R`/`G`/`B` from `settings.rgb.red/green/blue`

## Example output

RGB, geospatial image:

```
px 1024, 768
UTM  412300.0, 3905120.0
lat/lon  35.2841°, -111.6531°
R 0.182  G 0.204  B 0.155
```

MONO, no CRS:

```
px 512, 300
Value 1432
```

## Edge cases

- **No geospatial data** (`hasGeospatialData` false) → omit the geo lines.
- **CRS already geographic** (`crs.is_geographic`) → show only the lat/lon line,
  skip the duplicate native line.
- **nodata / masked pixel** → show the value as `nodata`.
- **Region display mode** → `localToImage` already maps region-local coords to
  full-image coords, so the readout works unchanged.
- **Float vs integer values** → integers shown plain; floats to a few significant
  figures.

## Testing

No automated tests. Manual verification: hover over geospatial and non-geospatial
images in MONO and RGB modes, confirm coordinates/values update and the HUD hides
when the cursor leaves the image.
