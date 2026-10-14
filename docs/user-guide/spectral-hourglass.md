# Spectral Hourglass: finding, identifying and mapping endmembers

**Workspace → New Spectral Hourglass Workspace…** (also under **Processing →
Endmembers**) runs ENVI's spectral hourglass workflow in one linked view. The
Pipeline panel walks through the steps; each is marked done, or "needs
re-running" when you change an earlier choice:

1. **Prepare** — pick a wavelength window (e.g. drop CRISM beyond 2.6 µm) and,
   for hyperspectral data, remove spikes with the IOVF filter (on by default
   for 100+ bands, as spikes otherwise pose as pure pixels).
2. **Reduce (MNF)** — drag the cutoff on the eigenvalue plot, or step through
   the components in the scene overlay to see where they turn to noise.
3. **Pixel Purity** — PPI counts how often each pixel is extreme in random
   projections; the top pixels (2,000 by default) go to the n-D view. **Run
   More** adds iterations to the current counts.
4. **Endmembers** — in the **n-D Visualizer**, press Play to tour the
   candidates through the kept MNF dimensions. Drag a lasso around a corner
   of the cloud to add it to the active endmember (Shift-drag removes);
   **Suggest** proposes one group per corner; **Collapse classes** hides the
   corners you already have so the next stands out. You can also pick pixels
   on the image: turn on **Draw on Image** in the scene's toolbar, choose a
   shape, and draw; each shape adds the valid pixels inside it to the active
   endmember (Shift while finishing removes them). This works from Prepare
   on, before Pixel Purity, so a region you already know can seed a class.
   Chosen pixels are filled in the scene and their mean spectrum is plotted.
   Ctrl+Z undoes any edit.
5. **Identify** — rank a spectral library against the active endmember by
   spectral angle, absorption shape and binary encoding; double-click a match
   to overlay it, then **Use as Name**. Two libraries are bundled: the CRISM
   MICA numerators (Viviano-Beck et al. 2014; picked automatically for CRISM
   products) and USGS splib07 minerals. **Load Library…** adds your own (see
   below; the **?** button beside it explains the formats).
6. **Map** — SAM (class + angle images), fully constrained linear unmixing
   (abundances + RMS error) or MTMF (matched-filter score + infeasibility,
   with a review plot whose threshold lines highlight detections live).

Maps join the project's images (as can the MNF and PPI images); endmember
classes can be saved as JSON or exported as a CSV spectral library, and the
workspace is part of saved sessions.

**Processing** also offers the pieces on their own: **Filtering → Iterative
Outlier Voting Filter (IOVF)**, **Endmembers → Pixel Purity Index**, and SAM,
unmixing and MTMF that use the workspace's ROIs as endmembers.

## Preparing a spectral library
Wavelengths may be in nm, µm or cm⁻¹. Name the unit in the wavelength column
(e.g. `wavelength_um`), in a `# units: µm` comment, or in an ENVI header's
`wavelength units`; otherwise Varda infers it and logs a warning. The library
is resampled to the image's bands and must overlap at least five of them;
matching ignores overall brightness, so reflectance, I/F or scaled values all
work.

- **CSV** (`.csv`/`.txt`): first column wavelength, one column per spectrum,
  names in the first non-comment row; lines starting with `#` are comments and
  empty cells are missing values.
  ```
  # optional comments
  wavelength_um,Kaolinite,Nontronite
  1.0010,0.512,0.430
  1.0075,0.515,0.431
  ```
- **ENVI spectral library** (`.sli` + `.hdr`) with `spectra names`,
  `wavelength` and `wavelength units` in the header.
- **USGS splib07 folder**: one sub-folder per spectrum holding its `.txt` and
  `*Wavelengths*.txt` files.

For CRISM, compare unratioed I/F endmembers with the MICA *numerators*;
ratioed type spectra only match ratioed data.
