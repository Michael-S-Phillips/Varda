"""ISIS (USGS Integrated Software for Imagers and Spectrometers), when it's
installed. Varda never downloads it (its mission data runs to tens of GB).

- ``cam2map`` map-projects a raw, spiceinit-ed camera cube, so it can join a
  mosaic (which needs map-projected images).
- ``equalizer`` solves the radiometric balance its own way, to cross-check
  Varda's global least-squares solve on the same inputs.

ISIS is found through ``ISISROOT``, or as a conda environment named ``isis``
or holding the ``isis`` package (as ASP's environment often does).
"""

from __future__ import annotations

import math
import os
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

import numpy as np
import rasterio
from attrs import frozen

from varda.mosaicking.backends.asp import CONDA_ROOTS
from varda.mosaicking.grid import defaultGrid, pixelSize
from varda.mosaicking.model import MosaicProject
from varda.mosaicking.recipe import Correction, LinearMode
from varda.mosaicking.render import Resampling, readCube, sampleOnGrid

ISIS_NULL4 = -3.4028226550889045e38  # ISIS's Null for 32-bit floats
CHECK_PIXELS = 1_000_000  # the cross-check works on a grid of about this size
EQUALIZER_ADJUST = {
    LinearMode.BOTH: "both",
    LinearMode.GAIN: "contrast",
    LinearMode.OFFSET: "brightness",
}
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class IsisError(RuntimeError):
    """An ISIS program failed; the message is for the user."""


@frozen
class IsisInstall:
    root: Path  # ISISROOT
    data: Path | None  # ISISDATA, which cam2map's camera models need
    version: str | None
    source: str


def _version(root: Path) -> str | None:
    meta = sorted((root / "conda-meta").glob("isis-*.json"))
    match = re.match(r"isis-(\d+(?:\.\d+)*)", meta[-1].name) if meta else None
    return match.group(1) if match else None


def _usable(root: Path) -> bool:
    return (root / "bin" / "cam2map").is_file() or (
        root / "bin" / "equalizer"
    ).is_file()


def findIsis(
    env: Mapping[str, str] | None = None, home: Path | None = None
) -> IsisInstall | None:
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    data = Path(env["ISISDATA"]) if env.get("ISISDATA") else None
    if env.get("ISISROOT") and _usable(Path(env["ISISROOT"])):
        root = Path(env["ISISROOT"])
        return IsisInstall(root, data, _version(root), "ISISROOT")
    for name in CONDA_ROOTS:
        envs = (
            home / name / "envs"
            if not name.startswith("opt")
            else Path("/") / name / "envs"
        )
        if not envs.is_dir():
            continue
        candidates = [envs / "isis"] if (envs / "isis").is_dir() else []
        candidates += sorted(
            e
            for e in envs.iterdir()
            if e.is_dir()
            and e not in candidates
            and any((e / "conda-meta").glob("isis-*.json"))
        )
        for root in candidates:
            if _usable(root):
                return IsisInstall(
                    root, data, _version(root), f"conda environment {root.name}"
                )
    return None


def toolEnv(install: IsisInstall) -> dict[str, str]:
    env = dict(os.environ)
    env["ISISROOT"] = str(install.root)
    if install.data is not None:
        env["ISISDATA"] = str(install.data)
    env["PATH"] = str(install.root / "bin") + os.pathsep + env.get("PATH", "")
    return env


def run(install: IsisInstall, command: list[str], cwd: Path | None = None) -> str:
    """Run an ISIS program; its output, or IsisError with the end of it."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=toolEnv(install),
            creationflags=_NO_WINDOW,
        )
    except OSError as error:
        raise IsisError(f"{Path(command[0]).name} couldn't start: {error}") from error
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        tail = "\n".join(output.splitlines()[-8:])
        raise IsisError(
            f"{Path(command[0]).name} failed (exit code {result.returncode}):\n{tail}"
        )
    return output


# --- cam2map -------------------------------------------------------------------------


def cam2mapCommand(
    install: IsisInstall,
    source: Path,
    target: Path,
    *,
    mapTemplate: Path | None = None,
    matchMap: bool = False,
    resolution: float | None = None,
    interpolation: str = "nearestneighbor",
) -> list[str]:
    """cam2map's arguments. Nearest neighbor by default, so the projected
    spectra are measured ones (ISIS's own default is cubic convolution)."""
    command = [str(install.root / "bin" / "cam2map"), f"from={source}", f"to={target}"]
    if mapTemplate is not None:
        command.append(f"map={mapTemplate}")
        if matchMap:
            command.append("matchmap=true")
    if resolution is not None and not matchMap:
        command += ["pixres=mpp", f"resolution={resolution}"]
    command.append(f"interp={interpolation}")
    return command


def cam2map(install: IsisInstall, source: Path, target: Path, **options) -> Path:
    """Map-project ``source`` (a spiceinit-ed level 1 cube) to ``target``."""
    run(install, cam2mapCommand(install, source, target, **options), cwd=target.parent)
    if not target.exists():
        raise IsisError(f"cam2map finished but wrote no {target.name}.")
    return target


# --- equalizer -------------------------------------------------------------------------


def parseEqualizerStats(text: str) -> dict[str, list[tuple[float, float, float]]]:
    """Each file's per-band (gain, offset, average) from equalizer's
    Normalization groups."""
    stats: dict[str, list[tuple[float, float, float]]] = {}
    text = re.sub(r"-[ \t]*\n[ \t]*", "", text)  # PVL continues long values after a "-"
    for group in re.findall(r"Group\s*=\s*Normalization(.*?)End_Group", text, re.S):
        name = re.search(r"FileName\s*=\s*(\S+)", group)
        bands = re.findall(r"Band(\d+)\s*=\s*\(([^)]*)\)", group)
        if name is None:
            continue
        values = [
            tuple(float(v) for v in raw.split(","))
            for _, raw in sorted(bands, key=lambda b: int(b[0]))
        ]
        stats[name.group(1)] = [(g, o, a) for g, o, a in values]
    return stats


def equalizerCorrections(
    stats: Mapping[str, list[tuple[float, float, float]]],
) -> dict[str, Correction]:
    """equalizer's newDN = (oldDN - average)·gain + average + offset, as
    Varda's gain·oldDN + offset."""
    corrections = {}
    for name, bands in stats.items():
        gain = np.array([g for g, _, _ in bands])
        offset = np.array([a * (1 - g) + o for g, o, a in bands])
        corrections[name] = Correction(gain, offset)
    return corrections


def crossCheckRadiometry(
    project: MosaicProject,
    mode: LinearMode,
    held: Iterable[int],
    install: IsisInstall,
    workdir: Path,
    progress: Callable[[float, str], None] = lambda fraction, message: None,
) -> dict[int, Correction]:
    """equalizer's corrections for the project's visible inputs, holding the
    same images. Each input is written as an ISIS cube on one reduced grid
    with its current alignment (nearest neighbor), so equalizer sees the
    overlaps Varda does."""
    inputs = [i for i in project.inputs if i.visible]
    full = defaultGrid(project)
    factor = max(1.0, math.sqrt(full.width * full.height / CHECK_PIXELS))
    grid = defaultGrid(project, pixelSize(project) * factor)
    workdir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for done, item in enumerate(inputs):
        progress(done / (len(inputs) + 1), f"writing {item.image.name} for ISIS")
        values = sampleOnGrid(item, readCube(item), grid, Resampling.NEAREST)
        path = workdir / f"input{item.key}.cub"
        with rasterio.open(
            path,
            "w",
            driver="ISIS3",
            width=grid.width,
            height=grid.height,
            count=values.shape[2],
            dtype="float32",
            crs=grid.crs,
            transform=grid.transform,
            nodata=ISIS_NULL4,
        ) as dataset:
            dataset.write(
                np.where(np.isfinite(values), values, ISIS_NULL4).transpose(2, 0, 1)
            )
        paths[item.key] = path.resolve()
    held = [k for k in held if k in paths] or [inputs[0].key]
    (workdir / "from.lis").write_text("".join(f"{p}\n" for p in paths.values()))
    (workdir / "hold.lis").write_text("".join(f"{paths[k]}\n" for k in held))
    stats = workdir / "stats.pvl"
    progress(len(inputs) / (len(inputs) + 1), "running equalizer")
    run(
        install,
        [
            str(install.root / "bin" / "equalizer"),
            f"fromlist={workdir / 'from.lis'}",
            f"holdlist={workdir / 'hold.lis'}",
            f"outstats={stats}",
            "process=calculate",
            f"adjust={EQUALIZER_ADJUST[mode]}",
            "mincount=100",
        ],
        cwd=workdir,
    )
    corrections = equalizerCorrections(parseEqualizerStats(stats.read_text()))
    byName = {Path(name).resolve(): c for name, c in corrections.items()}
    return {key: byName[path] for key, path in paths.items() if path in byName}
