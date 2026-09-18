# Varda

Varda is a GUI based app to visualize and analyze image data, with an emphasis on supporting hyperspectral and multispectral data workflows.
It currently offers basic image visualization, and spectra exploration (viewing individual pixel spectra, and mean spectra of ROIs). There are many features we still plan to add, including richer ROI features and image processing/analysis pipelines. As well as continuing to improve the modularity and exposing plugin APIs for users to inject their own features.

This project is still very much a WIP! As such, things will be changing rapidly, and may feel a bit unpolished. If you encounter any issues or would like to request any features, feel free to contact me at jesseoved@arizona.edu, or you may open a new issue here on GitHub.


# Getting Started

## Prerequisites:

- Python 3.13 installed
- [uv package manager](https://docs.astral.sh/

## Setup Development environment:
1. clone the repository and navigate to the project directory.
2. run the following command to setup the environment and install dependencies:
```bash
uv sync
```

## Run Varda:
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
original bands from the first N (or keeps just those N component bands).

## Saving results
Every Processing result joins the project's image list. Tick **Save result to
file** in the analysis dialog to also write it to disk (ENVI `.img`/`.hdr` or
GeoTIFF), or export any image later with **File → Export Image…** / right-click
an image → **Export Image…**.

## Optional: Band Parameters (HyPyRameter)
**Processing → Spectral Parameters → Band Parameters (HyPyRameter)** computes
CRISM-style spectral parameters with
[HyPyRameter](https://github.com/Michael-S-Phillips/HyPyRameter); the dialog
lists every parameter the image's wavelength range supports and lets you pick
which to compute. It is optional: without it Varda runs normally and lists that
analysis as unavailable. HyPyRameter is not on PyPI; the `hypyrameter` extra pins it to a
commit of its GitHub repository:
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
