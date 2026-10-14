# Installing Varda

## Download a release (no Python needed)

Get the latest release from the
[Releases page](https://github.com/varda-pro/Varda/releases/latest).

### macOS (Apple silicon)

1. Download `Varda-macos-arm64.dmg` and open it.
2. Drag **Varda** onto the **Applications** shortcut.
3. Open Varda from Applications. Varda isn't signed with an Apple developer
   certificate, so the first time, macOS says it can't verify the app:
   - **macOS 15 (Sequoia) and later:** click **Done**, open **System Settings →
     Privacy & Security**, scroll down to the message about Varda and click
     **Open Anyway**, then confirm.
   - **macOS 14 and earlier:** right-click Varda → **Open**, then **Open**.

   You only do this once.

Intel Macs aren't supported by the download; run Varda from source instead.

### Windows

Download `Varda-windows-x64.zip`, unzip it, and run `Varda.exe`. If Windows
shows "Windows protected your PC", choose **More info → Run anyway**.

### Linux

Download `Varda-linux-x64.zip`, unzip it, and run `Varda`.

The downloads include HyPyRameter band parameters. The PyTorch CNN/ViT
classifiers download PyTorch the first time you use them (see
[Optional features](optional-features.md)).

### Varda 0.5.0 and earlier on macOS

Those releases shipped as a zip with a plain folder, which macOS blocks
library by library ("library load disallowed by system policy"). To run one,
mark the unzipped folder as trusted in Terminal, then open `Varda` inside it:

```bash
xattr -dr com.apple.quarantine ~/Downloads/Varda-macos-arm64
```

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
