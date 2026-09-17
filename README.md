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

## Optional: Band Parameters (HyPyRameter)
**Processing → Spectral Parameters → Band Parameters (HyPyRameter)** computes
CRISM-style spectral parameters with
[HyPyRameter](https://github.com/Michael-S-Phillips/HyPyRameter).
It is optional: without it Varda runs normally and lists that analysis as
unavailable. HyPyRameter is not on PyPI; the `hypyrameter` extra pins it to a
commit of its GitHub repository:
```bash
uv sync --extra hypyrameter
# or, with pip:  pip install "varda[hypyrameter]"
```
