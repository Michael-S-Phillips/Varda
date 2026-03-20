# Varda

Varda is a GUI based app to visualize and analyze image data, with an emphasis on supporting hyperspectral and multispectral data workflows.
It currently offers basic visualization and spectra exploration (viewing individual pixel spectra, and mean spectra of ROIs). There are many features we still plan to add, including richer ROI features and image processing/analysis pipelines. As well as continuing to improve the modularity and exposing plugin APIs for users to inject their own features.

This project is still very much a WIP! As such, things will be changing rapidly, and may feel a bit unpolished. If you encounter any issues, or are missing any features that you would like to see, feel free to contact me at jesseoved@arizona.edu, or you may open a new issue here on GitHub.


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
