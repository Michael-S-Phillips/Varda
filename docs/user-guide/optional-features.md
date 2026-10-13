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

## CNN and ViT classifiers (PyTorch)
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
