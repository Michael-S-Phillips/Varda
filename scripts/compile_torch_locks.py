"""Compile the pinned, hashed PyTorch lock files the Optional Features dialog installs.

One lock per platform and backend, in resources/optional_features/torch/.
Run when bumping PyTorch (and before a release that should ship the bump):

    uv run python scripts/compile_torch_locks.py [--torch "torch==2.15.*"]
"""

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK_DIR = PROJECT_ROOT / "resources" / "optional_features" / "torch"

TORCH = "torch==2.14.*"
MACOS_TARGET = "14.0"  # recent torch wheels need macOS 14; uv assumes 12 otherwise

# name: (uv --python-platform, uv --torch-backend or None for the PyPI default)
# CUDA 13.0 needs an NVIDIA driver >= 580 and a Turing-or-newer GPU; others use CPU.
TARGETS = {
    "macos-arm64": ("aarch64-apple-darwin", None),  # the PyPI wheel includes MPS
    "windows-x64-cpu": ("x86_64-pc-windows-msvc", "cpu"),
    "windows-x64-cu130": ("x86_64-pc-windows-msvc", "cu130"),
    "linux-x64-cpu": ("x86_64-unknown-linux-gnu", "cpu"),
    "linux-x64-cu130": ("x86_64-unknown-linux-gnu", "cu130"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--torch", default=TORCH, help="requirement for torch")
    args = parser.parse_args()
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        requirements = Path(tmp) / "torch.in"
        requirements.write_text(f"{args.torch}\nnumpy\n")
        for name, (platform, backend) in TARGETS.items():
            out = LOCK_DIR / f"{name}.txt"
            command = [
                "uv",
                "pip",
                "compile",
                str(requirements),
                "--python-version",
                "3.13",
                "--python-platform",
                platform,
                "--generate-hashes",
                "--no-header",
                "--quiet",
                "-o",
                str(out),
            ]
            if backend:
                command += ["--torch-backend", backend]
            env = {**os.environ, "MACOSX_DEPLOYMENT_TARGET": MACOS_TARGET}
            subprocess.run(command, check=True, env=env)
            torch = next(
                line
                for line in out.read_text().splitlines()
                if line.startswith("torch==")
            )
            print(f"{name}: {torch.split()[0]}")


if __name__ == "__main__":
    main()
