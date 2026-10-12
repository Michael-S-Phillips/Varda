# Varda

Varda is a GUI based app to visualize and analyze image data, with an emphasis on supporting hyperspectral and multispectral data workflows.
It currently offers basic image visualization, and spectra exploration (viewing individual pixel spectra, and mean spectra of ROIs). There are many features we still plan to add, including richer ROI features and image processing/analysis pipelines. As well as continuing to improve the modularity and exposing plugin APIs for users to inject their own features.

This project is still very much a WIP! As such, things will be changing rapidly, and may feel a bit unpolished. If you encounter any issues or would like to request any features, feel free to contact me at jesseoved@arizona.edu, or you may open a new issue here on GitHub.


# Getting Started

## Download a release (no Python needed)
Each release on the [Releases page](https://github.com/Michael-S-Phillips/Varda/releases)
ships a zip per platform (`Varda-windows-x64.zip`, `Varda-macos-arm64.zip`,
`Varda-linux-x64.zip`). Unzip it and run the `Varda` executable inside.
- **macOS:** the build is not code-signed, so the first launch is blocked by
  Gatekeeper. Right-click the app → *Open* (once), or run
  `xattr -dr com.apple.quarantine <path to Varda>`.
- The packaged app does not include the optional extras below (HyPyRameter
  band parameters, PyTorch classifiers); run from source for those.

## Run from source

### Prerequisites
- Python 3.13
- the [uv package manager](https://docs.astral.sh/uv/)

### Setup
1. Clone the repository and navigate to the project directory.
2. Install the dependencies (add the optional extras you want):
```bash
uv sync
# with the optional extras (see below):
uv sync --extra hypyrameter --extra ml
```
`uv sync` on its own removes extras that were installed before — repeat the
`--extra` flags whenever you sync.

### Run Varda
```bash
uv run varda
```

## Sessions
**File → Save Session…** (⌘S) writes a `.varda` file recording the open
images (by path), the open workspaces and their ROIs; **File → Open Session…**
(⌘O) loads the images and reopens the workspaces alongside whatever is already
open. Images that exist only in memory (analysis results you have not exported)
are left out — export them first.

Varda also autosaves the session every three minutes and on quit (to
`autosave.varda` in its app-data folder, next to the logs); after a crash,
**File → Restore Last Session** brings it back.

## Choosing how many PCA / MNF / ICA components to keep
The forward transforms (**Processing → Transforms**) default to every
component and attach the eigenvalues and inverse to the result. Open the
result in a workspace and step through its bands to see where the components
turn into noise, and use **Transforms → Eigenvalue Plot…** to plot and tabulate
the eigenvalues (with % and cumulative variance) and drag a cutoff to where they
flatten out. Its button opens **Transforms → Inverse Transform (Keep N
Components)** with that N preset, which rebuilds a denoised image in the
original bands from the chosen components (or keeps just those component
bands). The first N are ticked by default; untick any (e.g. component 1 to
drop albedo) or type a range such as `3-19, 22`.

## Spectral Hourglass: finding, identifying and mapping endmembers
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
   corners you already have so the next stands out. Lassoed pixels are filled
   in the scene and their mean spectrum is plotted. Ctrl+Z undoes any edit.
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

### Preparing a spectral library
Wavelengths may be in nm or µm (values below 10 are read as µm). The library
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

## Saving results
Every Processing result joins the project's image list. Tick **Save result to
file** in the analysis dialog to also write it to disk (ENVI `.img`/`.hdr` or
GeoTIFF), or export any image later with **File → Export Image…** / right-click
an image → **Export Image…**.

## Optional: Band Parameters (HyPyRameter)
**Processing → Spectral Parameters → Band Parameters (HyPyRameter)** computes
CRISM-style spectral parameters with
[HyPyRameter](https://github.com/Michael-S-Phillips/HyPyRameter); the dialog
lists every parameter the image's wavelength range supports (hover a name for
its definition) and lets you pick which to compute. It is optional: without it
Varda runs normally and lists that analysis as unavailable. The `hypyrameter`
extra installs HyPyRameter from PyPI:
```bash
uv sync --extra hypyrameter
# or, with pip:  pip install "varda[hypyrameter]"
```

## Optional: CNN / ViT classifiers (PyTorch)
**Processing → Classification → Train CNN on ROIs / Train ViT on ROIs** train
small neural networks on spatial-spectral patches around your ROI pixels. They
need PyTorch, which is large, so it lives in the `ml` extra (the MLP classifier
is pure numpy and always available):
```bash
uv sync --extra ml
# or, with pip:  pip install "varda[ml]"
```
Training runs on CUDA or Apple MPS when available, otherwise on the CPU.
