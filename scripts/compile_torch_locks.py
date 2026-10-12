"""Compile the pinned, hashed PyTorch lock files the Optional Features dialog installs.

One lock per platform and backend, in resources/optional_features/torch/, plus
sizes.json: the exact download size of each lock's wheels, for the dialog.
Run when bumping PyTorch (and before a release that should ship the bump):

    uv run python scripts/compile_torch_locks.py [--torch "torch==2.15.*"]
"""

import argparse
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
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


# Wheel platform tags that install on each target
PLATFORM_TAGS = {
    "aarch64-apple-darwin": ("macosx", ("arm64", "universal2")),
    "x86_64-pc-windows-msvc": ("win", ("amd64",)),
    "x86_64-unknown-linux-gnu": ("linux", ("x86_64",)),
}


def parseLock(path: Path) -> dict[str, set[str]]:
    """Package name -> the sha256 hashes pinned for it."""
    packages: dict[str, set[str]] = {}
    name = ""
    for line in path.read_text().splitlines():
        if match := re.match(r"^([A-Za-z0-9_.\-]+)==", line):
            name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
            packages[name] = set()
        if name:
            packages[name].update(re.findall(r"--hash=sha256:([0-9a-f]{64})", line))
    return packages


USER_AGENT = {"User-Agent": "varda-compile-torch-locks"}  # the PyTorch CDN needs one


def _get(url: str, accept: str = "") -> str | None:
    headers = {**USER_AGENT, **({"Accept": accept} if accept else {})}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read().decode()
    except urllib.error.HTTPError:
        return None


def _headSize(url: str) -> int:
    request = urllib.request.Request(url, method="HEAD", headers=USER_AGENT)
    with urllib.request.urlopen(request, timeout=60) as response:
        return int(response.headers["Content-Length"])


def indexFiles(name: str, backend: str | None) -> dict[str, tuple[str, int | None]]:
    """sha256 -> (filename, size or None) from PyPI and the PyTorch index."""
    files: dict[str, tuple[str, int | None]] = {}
    pypi = _get(
        f"https://pypi.org/simple/{name}/", "application/vnd.pypi.simple.v1+json"
    )
    for entry in json.loads(pypi)["files"] if pypi else []:
        if "sha256" in entry["hashes"]:
            files[entry["hashes"]["sha256"]] = (entry["filename"], entry.get("size"))
    if backend:
        html = _get(f"https://download.pytorch.org/whl/{backend}/{name}/") or ""
        for url, sha in re.findall(r'href="([^"#]+)#sha256=([0-9a-f]{64})"', html):
            files.setdefault(sha, (url, None))
    return files


def _installs(filename: str, platform: str) -> bool:
    if not filename.endswith(".whl"):
        return False
    pythonTag, abiTag, platformTag = Path(filename).stem.split("-")[-3:]
    family, arches = PLATFORM_TAGS[platform]
    pythonOk = any(t in pythonTag for t in ("cp313", "py3")) or abiTag == "abi3"
    platformOk = platformTag == "any" or (
        family in platformTag and any(a in platformTag for a in arches)
    )
    return pythonOk and abiTag != "cp313t" and platformOk


def downloadSize(lock: Path, platform: str, backend: str | None) -> int:
    total = 0
    for name, hashes in parseLock(lock).items():
        files = indexFiles(name, backend)
        sizes = []
        for sha in hashes & files.keys():
            filename, size = files[sha]
            if _installs(filename.rsplit("/", 1)[-1].replace("%2B", "+"), platform):
                sizes.append(size if size is not None else _headSize(filename))
        if not sizes:
            raise SystemExit(f"No wheel of {name} found for {platform}")
        total += max(sizes)
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--torch", default=TORCH, help="requirement for torch")
    args = parser.parse_args()
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        requirements = Path(tmp) / "torch.in"
        requirements.write_text(f"{args.torch}\nnumpy\n")
        sizes: dict[str, int] = {}
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
                "--no-annotate",
                "--quiet",
                "-o",
                str(out),
            ]
            if backend:
                command += ["--torch-backend", backend]
            env = {**os.environ, "MACOSX_DEPLOYMENT_TARGET": MACOS_TARGET}
            subprocess.run(command, check=True, env=env)
            sizes[name] = downloadSize(out, platform, backend)
            torch = next(
                line
                for line in out.read_text().splitlines()
                if line.startswith("torch==")
            )
            print(f"{name}: {torch.split()[0]}, {sizes[name] / 1e6:.0f} MB")
    (LOCK_DIR / "sizes.json").write_text(json.dumps(sizes, indent=2) + "\n")


if __name__ == "__main__":
    main()
