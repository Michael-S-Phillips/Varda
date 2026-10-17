# Reporting results from Varda

Varda is meant to be described in a paper. Anything you do in it should be
something you can write up accurately, with its uncertainties, from these
guides and from what Varda gives you. This page covers what applies to every
process; each guide ends with a **Reporting your results** section for its
own methods, settings and references.

## Cite Varda, its version and the methods

- **Varda:** **Help → Cite Varda…** gives APA and BibTeX (also GitHub's
  **Cite this repository** button). Give the version: it's in the citation,
  in **Help → About Varda**, and in every result's record (below).
- **The methods:** cite the papers behind each method you used, listed in
  each guide's references. Varda implements them; it doesn't replace them.
- **Other software Varda ran for you:** HyPyRameter, ISIS, the Ames Stereo
  Pipeline and PyTorch have their own citations. **Help → Copy System Info**
  copies the versions of Varda, Python, Qt, numpy, GDAL, PROJ, HyPyRameter
  and PyTorch, which you can quote or keep with your notes.
- **The data:** cite the instrument teams' data products and spectral
  libraries as their providers ask.

## What Varda records, and what it doesn't

Every result of the **Processing** menu records how it was made: the
analysis, every setting, the input image (by name and file path), the Varda
version, the time, and the plugin and its version if a plugin made it.
Exporting the result keeps most of this as one line in the file's
description (the ENVI header's `description`, or the GeoTIFF's description
tag), such as
"Made with Varda 0.9.0: Band Math (Expression=…) from /data/scene.img on
2026-10-16T…".

Some things aren't recorded yet, so note them yourself:

- **Chains of results.** A result records its immediate input only. If that
  input was itself an unsaved result, its settings aren't carried along.
  Export each intermediate result (or [package the
  project](sessions-and-saving.md#sharing-a-project)) to keep the chain.
- **Workspace results.** Mosaics, displacement fields, crops made with the
  crop tool, and the Spectral Hourglass's MNF, PPI and maps carry a
  description but not the full record of settings. The mosaic's recipe is
  kept in Varda and in sessions, not in the exported file.
- **The plugin** that made a result isn't in the exported file's one-line
  description. Note its name and version yourself.
- **Detailed metadata** (classifier settings and training loss, class names
  and colors, eigenvalues and explained variance) exists only while the
  result is open in Varda. Sessions don't keep in-memory results, and
  exported files and packaged projects keep the pixels and band names but
  not this metadata. Copy what you need into your notes before closing.
- **Random seeds.** Processes that use random numbers (the Pixel Purity
  Index, and training the MLP, CNN and ViT classifiers) have a **Seed**
  setting, 0 by default, recorded with the other settings (in the Spectral
  Hourglass, in the PPI image's description and the saved workflow). The
  same seed and settings give the same result in the same Varda version;
  the CNN and ViT can still differ slightly between devices (CPU, CUDA,
  MPS) and PyTorch versions, which their results record (see
  [Classification](classification.md)). Results from Varda 0.9.0 and
  earlier, before these seeds, can't be reproduced exactly.
- **Edits to the input** made in Image Properties (no-data value,
  wavelengths, bad bands) aren't part of a result's record.

A [packaged project](sessions-and-saving.md#sharing-a-project) is the most
complete record: it has the session, every image, every in-memory result
(as files, with the one-line description) and a manifest with each file's
SHA-256 checksum.

## Precision is not accuracy

Many of Varda's quality numbers (tie-point RMS, unmixing RMS error, FATT
nRMSE, spectral angles) measure how well a model fits the data you gave it.
They're precision. Accuracy also depends on things Varda can't see:

- **Georeferencing.** Map positions, distances and linked-image locations
  are only as good as each image's own georeferencing. Report its source and
  stated accuracy, and use check points (see
  [Mosaicking](mosaicking.md#reporting-your-results)) when alignment matters.
- **Elevations.** Profiles, slopes and 3D terrain inherit the DEM's
  vertical error. Report the DEM's stated vertical precision (from its
  producer) along with anything you derive from it.
- **Calibration.** Spectra, band parameters and abundances inherit the
  calibration and atmospheric correction of the input. Varda adds none.
- **Libraries.** A library match is only as good as the library spectrum's
  resolution, grain size and measurement conditions.

## Results labeled "(visual)"

A result whose name ends in "(visual)" was made with a step that changes
spectral values for the sake of appearance: bilinear resampling, blending or
histogram matching. Use it for figures, not for measurements.

## Display stretches

Stretches only change how an image looks; they never change the data or the
results of analyses. If you state stretch limits in a figure caption, note
that percentile limits are estimated from a 1,024-bin histogram, so they're
approximate.

## Plugins and Kindle a Feature

A result made by a plugin records the plugin's name and version. A plugin
built with [Kindle a Feature](kindle-a-feature.md) was written by an AI and
checked only to run without errors: it hasn't been validated scientifically.
Before reporting its results, read its code and test it on data with a known
answer, and describe what it does in your own words.
