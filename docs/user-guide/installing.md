# Installing Varda

## Download a release (no Python needed)

Each release on the [Releases page](https://github.com/varda-pro/Varda/releases)
ships a zip per platform (`Varda-windows-x64.zip`, `Varda-macos-arm64.zip`,
`Varda-linux-x64.zip`). Unzip it and run the `Varda` executable inside.

- **macOS:** the build is not code-signed, so the first launch is blocked by
  Gatekeeper. Right-click the app → *Open* (once), or run
  `xattr -dr com.apple.quarantine <path to Varda>`.
- The packaged app includes HyPyRameter band parameters. The PyTorch CNN/ViT
  classifiers download PyTorch the first time you use them (see
  [Optional features](optional-features.md)).

## Run from source

You need Python 3.13 and the [uv package manager](https://docs.astral.sh/uv/).

1. Clone the repository and change into it.
2. Install the dependencies, adding the optional extras you want:
   ```bash
   uv sync
   # with the optional extras (see Optional features):
   uv sync --extra hypyrameter --extra ml
   ```
   `uv sync` on its own removes extras that were installed before, so repeat
   the `--extra` flags whenever you sync.
3. Run Varda:
   ```bash
   uv run varda
   ```

To check that an installation works, run `uv run varda --self-test` (or
`Varda --self-test` for a downloaded build). It opens, reads and writes test
images, renders one and runs two analyses, then reports each check.
