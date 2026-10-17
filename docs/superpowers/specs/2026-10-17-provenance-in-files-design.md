# Provenance in files — Design

**Date:** 2026-10-17
**Status:** Implemented on `feature/provenance-in-files`.

## Why

CLAUDE.md's standard: a user must be able to describe, and report the
uncertainties of, any process they ran in Varda from the docs and its
outputs alone. Before this change, only Processing-menu results had a record
(`extraMetadata["provenance"]`), it named only the immediate input, it was
reduced to one line in an exported file's description, and the scientific
metadata (class names, eigenvalues and the inverse transform, classifier
figures, the mosaic recipe, FATT settings) was lost on export. Workspace
results and downloads recorded nothing.

## The record (schema 1)

Built by one function, `common.provenance.makeProvenance`, used by the
analysis runner (`analysis.provenance.recordProvenance`) and by every
workspace that makes results. Plain JSON-friendly data (`plain` converts
enums, arrays, numpy scalars, dataclasses, images and colors):

```json
{
  "schema": 1,
  "process": "Band Math",
  "processId": "band_math",
  "parameters": {"Expression": "b2 - b1"},
  "inputs": [{"name": "scene", "path": "/data/scene.img", "provenance": {...}}],
  "vardaVersion": "0.9.0",
  "created": "2026-10-17T12:00:00+00:00",
  "plugin": "Ratios 1.2",
  "software": {"spectral": "0.24"},
  "source": {"catalog": "PDS ODE", "url": "...", "...": "..."}
}
```

- `inputs[].provenance` is the input's own record, so chains survive (in
  memory and on disk). Other images an analysis uses through an
  `ImageParameter` (weights, a second image) are inputs too.
- `plugin` and `software` appear only when they apply. `software` comes
  from `Analysis.software` (distribution names; versions via
  `importlib.metadata`), overridden where the version lives elsewhere (the
  PyTorch runtime's manifest). Workspaces add external tools (ISIS, the Ames
  Stereo Pipeline) when their results are used.
- `source` comes from a download record beside the file (below).
- `setProvenance` stores the record in the data source's metadata dict, so
  Image Properties overrides (which copy the dict) can't drop it.

## In files

`writeRaster` writes the `VARDA` GDAL metadata domain with two JSON keys:

- `provenance`: the record.
- `metadata`: the kept scientific keys (`KEPT_METADATA_KEYS`: `classes`,
  `classColors`, `explainedVariance`, `transform`, `layerSizes`,
  `finalLoss`, `patchSize`, `mapMethod`, `mosaic`, `displacement`, `fatt`).
  An explicit list, so header-derived ENVI keys aren't duplicated.

GeoTIFF keeps the domain inside the file; ENVI keeps it in
`<file>.img.aux.xml` (GDAL PAM). GDAL round-trips JSON with braces there,
unlike the ENVI header. Packaged projects already copy `*.aux.xml`. The
one-line description stays, now naming the plugin and shortening long
values.

`RasterioDataSource` and `ENVIDataSource` read the domain back into
`extraMetadata` (`fileMetadata`); files without it give `{}`, so they open
exactly as before. HDF5 (h5py) files aren't covered: Varda never writes them.

## Workspace outputs

| Output | Process | Parameters |
| --- | --- | --- |
| Mosaic | Mosaic | resampling, output grid, `project.state()` recipe; tools used |
| Source map | Mosaic Source Index | none; its input is the mosaic, with its record |
| Displacement field | Displacement Field | Auto Align's method asked for and used, bands, tile size, refine |
| Crop-tool crop | Crop | 0-based row, column, height, width |
| Hourglass MNF / PPI / maps | Spectral Hourglass MNF / PPI / Map | `HourglassModel.runSettings()`: window and kept bands, IOVF and its settings, MNF noise estimate and components, PPI iterations, threshold, seed (if the result has one) and candidate rule, endmembers with pixels; maps add method and setting |
| MTMF detections | MTMF Detections | endmember, score and infeasibility thresholds; input is the MTMF map |

The hourglass MNF image also carries `transformMetadata` for the kept
components (as the Processing-menu MNF does), so Eigenvalue Plot and
Inverse Transform work on it. The PPI seed is read with `getattr`, so this
works before and after the reproducible-seeds change adds one.

## Downloads

`downloadProduct(..., catalog=, product=)` writes
`<file>.varda-source.json` beside each downloaded file: catalog,
collection, product id and title, file, URL, size, checksum and what
verified the download, UTC time, Varda version. One per file (not per
product) so `companionFiles` packages it with its file and the loader finds
it by path. The loader adds it as the record's `source`.

## Also

- FATT's ranked table exports to CSV (`fatt.writeRanking`), with `#` lines
  giving the settings that made the ranking.
- Help → Copy System Info names Spectral Python's version.
- `GDAL_DRIVER_PATH` from a foreign installation is removed at import, like
  `PROJ_DATA` and `GDAL_DATA`.

## Not recorded

ROI polygons (training ROIs are named by class), Image Properties edits to
an input, random seeds a run didn't fix, and the device a PyTorch run used.
