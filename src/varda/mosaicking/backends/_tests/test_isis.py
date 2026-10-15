"""ISIS: finding it, map-projecting with cam2map, and cross-checking the
radiometry with equalizer."""

import sys
from pathlib import Path

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS
from scipy import ndimage

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking.backends.isis import (
    IsisError,
    IsisInstall,
    cam2map,
    cam2mapCommand,
    crossCheckRadiometry,
    equalizerCorrections,
    findIsis,
    parseEqualizerStats,
)
from varda.mosaicking.model import MosaicProject
from varda.mosaicking.radiometry import LinearMode, RadiometryMethod, balance

STATS = """
Object = EqualizationInformation
  # Formula: newDN = (oldDN - AVERAGE) * GAIN + AVERAGE + OFFSET
  # BandN = (GAIN, OFFSET, AVERAGE)
  Group = Normalization
    FileName = /work/input0.cub
    Band1    = (1.0, 4.9985325407903e-34, 0.99862358213961)
    Band2    = (1.0, 0.0, 2.0)
  End_Group

  Group = Normalization
    FileName = /work/inp-
               ut1.cub
    Band1    = (0.76943243750016, -0.4998532540791, 1.5124425037205)
    Band2    = (0.5, 0.25, 4.0)
  End_Group
End_Object
"""


def _fakeRoot(folder: Path, tools=("cam2map", "equalizer")) -> Path:
    (folder / "bin").mkdir(parents=True)
    for tool in tools:
        path = folder / "bin" / tool
        path.write_text(f"#!{sys.executable}\n")
        path.chmod(0o755)
    return folder


def test_isisroot_is_found_first(tmp_path):
    root = _fakeRoot(tmp_path / "isis")
    found = findIsis(
        {"ISISROOT": str(root), "ISISDATA": str(tmp_path)}, home=tmp_path / "home"
    )
    assert found.root == root and found.data == tmp_path and found.source == "ISISROOT"


def test_conda_environments_with_isis_are_found(tmp_path):
    home = tmp_path / "home"
    env = _fakeRoot(home / "anaconda3" / "envs" / "asp")  # ASP's env, holding ISIS
    (env / "conda-meta").mkdir()
    (env / "conda-meta" / "isis-8.0.0-np125_0.json").write_text("{}")
    found = findIsis({}, home=home)
    assert found.root == env and found.version == "8.0.0" and found.data is None
    assert "asp" in found.source


def test_nothing_found(tmp_path):
    assert findIsis({}, home=tmp_path) is None


def test_equalizer_statistics_become_corrections():
    stats = parseEqualizerStats(STATS)
    assert list(stats) == ["/work/input0.cub", "/work/input1.cub"]
    corrections = equalizerCorrections(stats)
    second = corrections["/work/input1.cub"]
    # newDN = (oldDN - average) * gain + average + offset
    assert np.allclose(second.gain, [0.76943243750016, 0.5])
    assert np.allclose(
        second.offset,
        [1.5124425037205 * (1 - 0.76943243750016) - 0.4998532540791, 4.0 * 0.5 + 0.25],
    )


def test_cam2map_arguments(tmp_path):
    install = IsisInstall(tmp_path, None, "8.0.0", "test")
    plain = cam2mapCommand(install, Path("in.cub"), Path("out.cub"))
    assert (
        plain[0].endswith("cam2map")
        and "from=in.cub" in plain
        and "to=out.cub" in plain
    )
    assert "interp=nearestneighbor" in plain
    matched = cam2mapCommand(
        install,
        Path("in.cub"),
        Path("out.cub"),
        mapTemplate=Path("ref.cub"),
        matchMap=True,
    )
    assert "map=ref.cub" in matched and "matchmap=true" in matched
    sized = cam2mapCommand(
        install,
        Path("in.cub"),
        Path("out.cub"),
        resolution=6.0,
        interpolation="bilinear",
    )
    assert (
        "pixres=mpp" in sized
        and "resolution=6.0" in sized
        and "interp=bilinear" in sized
    )


def test_cam2map_runs_and_reports_failures(tmp_path):
    root = tmp_path / "isis"
    (root / "bin").mkdir(parents=True)
    tool = root / "bin" / "cam2map"
    tool.write_text(
        f"""#!{sys.executable}
import os, sys, pathlib
args = dict(a.split("=", 1) for a in sys.argv[1:])
assert os.environ["ISISROOT"]
if "fail" in args["from"]:
    print("**USER ERROR** Unable to initialize camera model"); sys.exit(1)
pathlib.Path(args["to"]).write_text("cube")
"""
    )
    tool.chmod(0o755)
    install = IsisInstall(root, None, "8.0.0", "test")
    out = cam2map(install, tmp_path / "raw.cub", tmp_path / "map.cub")
    assert out.read_text() == "cube"
    with pytest.raises(IsisError, match="camera model"):
        cam2map(install, tmp_path / "fail.cub", tmp_path / "map2.cub")


REAL = findIsis()


def _project() -> MosaicProject:
    rng = np.random.default_rng(0)
    texture = ndimage.gaussian_filter(rng.normal(size=(100, 200)), 3.0)
    scene = np.stack([1.0 + texture, 2.0 + 2 * texture], axis=2)

    def strip(cube, firstCol, name):
        source = ArrayDataSource(
            cube.astype(np.float32),
            wavelengths=np.array([500.0, 600.0]),
            wavelengthUnits="nm",
            transform=Affine(100.0, 0, firstCol * 100.0, 0, -100.0, 10000.0),
            crs=CRS.from_proj4(
                "+proj=eqc +lat_ts=0 +lon_0=0 +R=3396190 +units=m +no_defs"
            ),
        )
        return VardaRaster(source, name=name)

    return MosaicProject(
        [
            strip(scene[:, :120], 0, "A"),
            strip(scene[:, 80:] * np.array([1.3, 0.8]) + 0.2, 80, "B"),
        ]
    )


@pytest.mark.skipif(REAL is None, reason="ISIS isn't installed")
def test_equalizer_agrees_with_the_global_solve(tmp_path):
    project = _project()
    isis = crossCheckRadiometry(project, LinearMode.BOTH, {0}, REAL, tmp_path)
    varda = balance(
        project, RadiometryMethod.GLOBAL, LinearMode.BOTH, held={0}
    ).corrections
    assert np.allclose(isis[1].gain, [1 / 1.3, 1 / 0.8], atol=0.01)
    assert np.allclose(isis[1].gain, varda[1].gain, atol=0.01)
    assert np.allclose(isis[1].offset, varda[1].offset, atol=0.02)
    assert np.allclose(isis[0].gain, 1.0)
