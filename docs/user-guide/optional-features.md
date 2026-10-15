# Optional features

## Band parameters (HyPyRameter)
**Processing → Spectral Parameters → Band Parameters (HyPyRameter)** computes
CRISM-style spectral parameters with
[HyPyRameter](https://github.com/Michael-S-Phillips/HyPyRameter); the dialog
lists every parameter the image's wavelength range supports (hover a name for
its definition) and lets you pick which to compute. It is optional: without it
Varda runs normally and lists that analysis as unavailable. The downloadable
app includes it; from source, the `hypyrameter` extra installs it from PyPI:
```bash
uv sync --extra hypyrameter
# or, with pip:  pip install "varda[hypyrameter]"
```

## CNN and ViT classifiers, and learned matchers (PyTorch)

The same environment also runs the Mosaic workspace's LoFTR and SIFT
matchers (Auto Align): it includes kornia and OpenCV for them.

**Processing → Classification → Train CNN on ROIs / Train ViT on ROIs** train
small neural networks on spatial-spectral patches around your ROI pixels. They
need PyTorch, which is too large to ship in every download. (The MLP
classifier is pure numpy and always available.)

**In the app.** The first time you pick one of these classifiers, Varda offers
to install PyTorch. You can also open **Processing → Optional Features…** at
any time. Varda picks the build for your hardware: Apple GPU on Apple silicon,
CUDA 13 for a recent NVIDIA GPU and driver, otherwise CPU. You can override
that choice. The CPU and Apple builds are a few hundred MB; the CUDA build is
about 3 GB.

PyTorch goes into its own Python environment in Varda's data folder (shown in
the dialog), so nothing else on your computer changes. Varda installs exactly
the versions pinned for its release, checked against their hashes. The
classifiers then run in a separate process using that environment.
**Uninstall** deletes the folder. Intel Macs and ARM Linux are not supported.

**From source.** Install the `ml` extra to run PyTorch inside Varda's own
environment instead:
```bash
uv sync --extra ml
# or, with pip:  pip install "varda[ml]"
```
Training runs on CUDA or Apple MPS when available, otherwise on the CPU.
Maintainers: `scripts/compile_torch_locks.py` regenerates the pinned locks in
`resources/optional_features/torch/`.

## Ames Stereo Pipeline (mosaicking)

Auto Align in the [Mosaic workspace](mosaicking.md) can match images with the
Ames Stereo Pipeline's `image_align` instead of Varda's own matchers. It's
optional: Varda's tools cover everything Auto Align needs.

**Processing → Optional Features…** shows whether Varda found ASP and where.
It looks, in order, in a folder you choose (**Choose Folder…**), on your
PATH, in conda environments named `asp` (or holding ASP) under miniforge,
miniconda, anaconda and mambaforge, in `~/StereoPipeline-*`, and in its own
download. **Re-detect** looks again.

If you don't have ASP, **Download ASP 3.7.0** fetches the official release
for your computer (260–650 MB) from GitHub into Varda's data folder, checks
it against its published SHA-256 checksum and unpacks it. **Remove** deletes
that copy (Varda never removes an ASP it didn't download).

ASP has no Windows version (it runs in WSL), so the download isn't offered
there.

## ISIS (mosaicking)

If you have [ISIS](https://github.com/DOI-USGS/ISIS3) installed, Varda finds
it through `ISISROOT`, or as a conda environment named `isis` (or one holding
ISIS, as ASP's environment often does). Varda never downloads ISIS: its
mission data runs to tens of gigabytes. **Optional Features** shows what was
found, and whether `ISISDATA` is set.

With ISIS, Varda can:

- **Map-project raw camera cubes:** **Processing → Geometry → Map-Project with
  ISIS (cam2map)…** projects a spiceinit-ed level 1 cube (to ISIS's default
  sinusoidal projection, to match a map-projected cube, or with a map
  template) so it can be mosaicked. Varda uses nearest-neighbor
  interpolation by default so the projected spectra are measured ones; the
  result opens in Varda. cam2map needs `ISISDATA` and the mission's SPICE
  kernels.
- **Cross-check mosaic radiometry:** in the Mosaic workspace's Radiometry
  tab, **Compare with ISIS equalizer** solves the same balance with ISIS
  equalizer (same held images and fit) and shows its gains and offsets beside
  Varda's; **Use ISIS's Corrections** applies them.
