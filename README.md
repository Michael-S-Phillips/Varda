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
