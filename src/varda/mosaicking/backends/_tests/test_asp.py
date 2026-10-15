"""Ames Stereo Pipeline: finding it, downloading it, and reading what
image_align matched."""

import hashlib
import stat
import struct
import sys
import tarfile
import threading
from pathlib import Path

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS
from scipy import ndimage

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking.matching import MatchMethod, MatchSettings, autoAlign
from varda.mosaicking.model import MosaicProject

from varda.mosaicking.backends.asp import (
    RELEASES,
    AspError,
    AspInstall,
    AspRelease,
    downloadAsp,
    findAsp,
    imageAlign,
    parseVersion,
    readMatches,
    releaseFor,
)


def _fakeTool(folder: Path, version: str = "3.6.0", matches: str = "") -> Path:
    """A stand-in image_align: prints a version; when run, writes a text
    match file shifting each point by (5, -3)."""
    folder.mkdir(parents=True, exist_ok=True)
    tool = folder / "image_align"
    tool.write_text(
        f"""#!{sys.executable}
import sys, pathlib
args = sys.argv[1:]
if "--version" in args:
    print("NASA Ames Stereo Pipeline {version}")
    sys.exit(0)
prefix = args[args.index("--output-prefix") + 1]
ref, src = (pathlib.Path(a).stem for a in args[:2])
path = pathlib.Path(prefix + f"-{{ref}}__{{src}}-clean.txt")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("".join(f"{{x}} {{y}} 1 {{x + 5}} {{y - 3}} 1\\n" for x, y in [(10, 20), (40, 50), (70, 15)]))
"""
    )
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    return folder


def test_versions_are_read_from_the_banner():
    assert parseVersion("NASA Ames Stereo Pipeline 3.3.0\n  Build ID: x") == "3.3.0"
    assert parseVersion("nonsense") is None


def test_each_platform_has_a_release_and_windows_has_none():
    assert releaseFor("Darwin", "arm64").url.endswith("arm64-OSX.tar.bz2")
    assert releaseFor("Linux", "x86_64").url.endswith("x86_64-Linux.tar.bz2")
    assert releaseFor("Windows", "AMD64") is None
    assert all(len(r.sha256) == 64 for r in RELEASES.values())


def test_detection_order(tmp_path, monkeypatch):
    home = tmp_path / "home"
    conda = _fakeTool(home / "miniforge3" / "envs" / "asp" / "bin", "3.4.0")
    manual = _fakeTool(
        home / "StereoPipeline-3.5.0-2025-01-01-x86_64-Linux" / "bin", "3.5.0"
    )
    onPath = _fakeTool(tmp_path / "path-bin", "3.6.0")
    chosen = _fakeTool(tmp_path / "chosen" / "bin", "3.7.0")
    env = {"PATH": str(onPath)}
    assert (
        findAsp(str(chosen.parent), env=env, home=home).version == "3.7.0"
    )  # a folder above bin works too
    found = findAsp(None, env=env, home=home)
    assert (found.version, found.source) == ("3.6.0", "PATH")
    found = findAsp(None, env={"PATH": ""}, home=home)
    assert found.bin == conda and "conda" in found.source
    (conda / "image_align").unlink()
    assert findAsp(None, env={"PATH": ""}, home=home).bin == manual
    assert findAsp(None, env={"PATH": ""}, home=tmp_path / "nobody") is None


def test_a_varda_download_is_found_last(tmp_path):
    root = tmp_path / "asp"
    _fakeTool(root / "StereoPipeline-3.7.0-2026-06-08-arm64-OSX" / "bin", "3.7.0")
    found = findAsp(None, downloads=root, env={"PATH": ""}, home=tmp_path / "nobody")
    assert found is not None and found.source == "Varda download"


def _binaryMatch(path: Path, first, second) -> None:
    """ASP's binary match file: two counts, then each image's interest points."""

    def record(x, y):
        return (
            struct.pack("<ffiifff", x, y, int(x), int(y), 0, 1, 1)
            + b"\x00"
            + struct.pack("<IIQ", 0, 0, 2)
            + struct.pack("<2f", 0, 0)
        )

    with open(path, "wb") as f:
        f.write(struct.pack("<QQ", len(first), len(second)))
        for x, y in [*first, *second]:
            f.write(record(x, y))


def test_binary_and_text_matches_are_read_in_varda_pixels(tmp_path):
    _binaryMatch(
        tmp_path / "a.match",
        [(72.0, 120.0), (53.0, 164.0)],
        [(77.0, 117.0), (58.0, 161.0)],
    )
    (tmp_path / "a.txt").write_text("72 120 1 77 117 1\n53 164 1 58 161 1\n")
    for name in ("a.match", "a.txt"):
        first, second = readMatches(tmp_path / name)
        # ASP counts from pixel centers, Varda from corners
        assert np.allclose(first, [[72.5, 120.5], [53.5, 164.5]])
        assert np.allclose(second - first, [[5, -3], [5, -3]])


def test_image_align_runs_on_two_bands_and_returns_matches(tmp_path):
    install = AspInstall(_fakeTool(tmp_path / "bin"), "3.6.0", "test")
    reference = np.random.default_rng(0).random((60, 80)).astype(np.float32)
    first, second = imageAlign(
        install, reference, reference, "affine", tmp_path / "work"
    )
    assert np.allclose(second - first, [5, -3])


def test_a_failing_tool_reports_its_output(tmp_path):
    folder = tmp_path / "bin"
    folder.mkdir()
    tool = folder / "image_align"
    tool.write_text(
        f"#!{sys.executable}\nimport sys\nprint('bad things'); sys.exit(2)\n"
    )
    tool.chmod(0o755)
    with pytest.raises(AspError, match="bad things"):
        imageAlign(
            AspInstall(folder, "3.6.0", "test"),
            np.ones((5, 5)),
            np.ones((5, 5)),
            "translation",
            tmp_path / "w",
        )


def _tarball(tmp_path) -> tuple[Path, str]:
    """A small release: StereoPipeline-x/bin/image_align."""
    tool = _fakeTool(
        tmp_path / "staging" / "StereoPipeline-9.9.9-test" / "bin", "9.9.9"
    )
    archive = tmp_path / "release.tar.bz2"
    with tarfile.open(archive, "w:bz2") as tar:
        tar.add(tool.parent, arcname=tool.parent.name)
    return archive, hashlib.sha256(archive.read_bytes()).hexdigest()


def test_a_download_is_verified_and_unpacked(tmp_path):
    archive, digest = _tarball(tmp_path)
    release = AspRelease("test", archive.as_uri(), digest, 1)
    seen = []
    install = downloadAsp(
        release, tmp_path / "asp", lambda f, m: seen.append(f), threading.Event()
    )
    assert install.version == "9.9.9" and install.source == "Varda download"
    assert seen and seen[-1] == 1.0
    assert not list((tmp_path / "asp").glob("*.tar.bz2"))  # the archive is cleaned up


def test_a_corrupt_download_is_refused(tmp_path):
    archive, _ = _tarball(tmp_path)
    release = AspRelease("test", archive.as_uri(), "0" * 64, 1)
    with pytest.raises(AspError, match="checksum"):
        downloadAsp(release, tmp_path / "asp", lambda f, m: None, threading.Event())
    assert not any((tmp_path / "asp").glob("StereoPipeline-*"))


def test_a_cancelled_download_stops(tmp_path):
    archive, digest = _tarball(tmp_path)
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(AspError, match="anceled"):
        downloadAsp(
            AspRelease("test", archive.as_uri(), digest, 1),
            tmp_path / "asp",
            lambda f, m: None,
            cancelled,
        )


REAL = findAsp(None)


@pytest.mark.skipif(REAL is None, reason="Ames Stereo Pipeline isn't installed")
def test_the_real_image_align_finds_a_planted_shift(tmp_path):
    rng = np.random.default_rng(0)
    texture = ndimage.gaussian_filter(rng.normal(size=(300, 300)), 2.0).astype(
        np.float32
    )
    reference, source = texture[20:220, 20:220], texture[23:223, 15:215]
    first, second = imageAlign(REAL, reference, source, "translation", tmp_path)
    assert len(first) > 20
    assert np.allclose(np.median(second - first, axis=0), [5, -3], atol=0.5)


# --- in Auto Align ---------------------------------------------------------------


def _stripsProject(shift=(0.0, 0.0)):
    rng = np.random.default_rng(0)
    texture = ndimage.gaussian_filter(rng.normal(size=(200, 300)), 2.0)
    scene = np.stack([texture, 0.7 * texture], axis=2)
    moved = np.real(
        np.fft.ifft2(
            ndimage.fourier_shift(
                np.fft.fft2(scene, axes=(0, 1)), (shift[1], shift[0], 0)
            ),
            axes=(0, 1),
        )
    )

    def strip(cube, firstCol, name):
        source = ArrayDataSource(
            cube.astype(np.float32),
            wavelengths=np.array([500.0, 600.0]),
            wavelengthUnits="nm",
            transform=Affine(10.0, 0, firstCol * 10.0, 0, -10.0, 2000.0),
            crs=CRS.from_epsg(32612),
        )
        return VardaRaster(source, name=name)

    return MosaicProject(
        [strip(scene[:, :180], 0, "left"), strip(moved[:, 100:], 100, "right")]
    )


def test_auto_align_with_asp_pools_every_bands_matches(tmp_path):
    project = _stripsProject()
    install = AspInstall(_fakeTool(tmp_path / "bin"), "3.6.0", "test")
    result = autoAlign(
        project, 1, [0], MatchSettings(method=MatchMethod.ASP, asp=install)
    )
    assert result.method is MatchMethod.ASP
    assert result.added == 3 * len(result.bands)  # the fake matches 3 points per band
    assert {p.band for p in project.tiePoints} == set(result.bands)


def test_asp_without_an_install_is_an_error():
    with pytest.raises(AspError, match="Optional Features"):
        autoAlign(_stripsProject(), 1, [0], MatchSettings(method=MatchMethod.ASP))


@pytest.mark.skipif(REAL is None, reason="Ames Stereo Pipeline isn't installed")
def test_auto_align_with_the_real_asp_recovers_a_shift():
    project = _stripsProject(shift=(3.0, -2.0))
    result = autoAlign(project, 1, [0], MatchSettings(method=MatchMethod.ASP, asp=REAL))
    assert result.added > 20
    project.fit(1, threshold=1.0)
    # the right strip's content is 3 px east and 2 px south: the correction undoes it
    assert np.allclose(project.input(1).correction[:2, 2], (-30.0, -20.0), atol=5.0)
