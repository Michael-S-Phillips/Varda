"""Packaged projects: one zip holding the session, every image with its
companion files, the files workspaces refer to, results held in memory and
a manifest of checksums, opening on another computer where none of the
original paths exist."""

import json
import shutil

import numpy as np

from varda.common.entities import VardaRaster
from varda.common.provenance import PROVENANCE_KEY, makeProvenance, setProvenance
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_loading.image_loading_service import openDataSource
from varda.image_loading.raster_writer import writeRaster
from varda.project_package import (
    LARGE_BYTES,
    capturePackage,
    companionFiles,
    formatBytes,
    planPackage,
    referencedPaths,
    relocatedPaths,
    verifyPackage,
    writePackage,
)
from varda.session import (
    SessionState,
    WorkspaceState,
    openSessionBundle,
    readSession,
    writeSession,
)
from varda.workspaces.general_image_analysis import (
    GeneralImageAnalysisConfig,
    GeneralImageAnalysisWorkflow,
)


def _raster(name, value=1.0) -> VardaRaster:
    data = np.full((4, 5, 3), value, dtype=np.float32)
    return VardaRaster(
        ArrayDataSource(
            data, wavelengths=np.array([500.0, 600.0, 700.0]), wavelengthUnits="nm"
        ),
        name=name,
    )


def test_an_image_brings_its_companion_files(tmp_path):
    names = [
        "scene.img",
        "scene.hdr",
        "scene.img.aux.xml",
        "scene.png",  # png: unrelated
        "MISE.IMG",
        "MISE.IMG.HDR",
        "obs.lbl",
        "obs.img",  # a PDS label and its data
        "other.img",
    ]
    for name in names:
        (tmp_path / name).write_text("x")
    names = lambda files: sorted(f.name for f in files)  # noqa: E731
    assert names(companionFiles(tmp_path / "scene.img")) == [
        "scene.hdr",
        "scene.img",
        "scene.img.aux.xml",
    ]
    assert names(companionFiles(tmp_path / "MISE.IMG")) == ["MISE.IMG", "MISE.IMG.HDR"]
    assert names(companionFiles(tmp_path / "obs.lbl")) == ["obs.img", "obs.lbl"]
    assert companionFiles(tmp_path / "gone.img") == []


def test_workspace_file_paths_are_found_and_moved():
    extra = {"lines": [{"path": "/a/traverse.gpkg", "color": "#f00"}], "band": 0}
    assert referencedPaths(extra) == ["/a/traverse.gpkg"]
    moved = relocatedPaths(extra, {"/a/traverse.gpkg": "data/files/01/traverse.gpkg"})
    assert moved["lines"][0] == {"path": "data/files/01/traverse.gpkg", "color": "#f00"}


def test_relative_workspace_files_resolve_from_the_session(tmp_path):
    state = SessionState(
        (), (WorkspaceState("terrain", (), {}, {"lines": [{"path": "data/l.gpkg"}]}),)
    )
    writeSession(state, tmp_path / "s.varda")
    (loaded,) = readSession(tmp_path / "s.varda").workspaces
    assert loaded.extra["lines"][0]["path"] == str(tmp_path / "data" / "l.gpkg")


def test_a_package_opens_where_none_of_the_original_files_are(qtbot, tmp_path):
    originals = tmp_path / "mine"
    originals.mkdir()
    onDisk = VardaRaster.fromDataSource(
        openDataSource(str(writeRaster(_raster("scene"), originals / "scene.img")))
    )
    result = _raster("scene slope", 2.0)  # only in memory
    setProvenance(result, makeProvenance("Slope", {"Units": "degrees"}, [onDisk]))
    workspace = GeneralImageAnalysisWorkflow(GeneralImageAnalysisConfig([onDisk]))
    qtbot.addWidget(workspace)
    workspace.lineCollection.addLine([[0, 0], [3, 3]], name="Rim")

    plan = planPackage([onDisk, result], [workspace])
    files = [f.name for f in plan.images[0][1]]
    assert files[0] == "scene.img" and "scene.hdr" in files  # and any .aux.xml
    assert plan.inMemory == (result,) and not plan.isLarge
    assert plan.totalBytes >= 4 * 5 * 3 * 4 * 2  # both images' data
    state = capturePackage(plan, [onDisk, result], [workspace])
    package = writePackage(plan, state, tmp_path / "project")
    assert package.name == "project.varda.zip"

    shutil.rmtree(originals)  # another computer: the original files aren't there
    opened = tmp_path / "theirs"
    state = readSession(openSessionBundle(package, opened))
    assert all(p.startswith(str(opened)) for p in state.images)
    reopened = [VardaRaster.fromDataSource(openDataSource(p)) for p in state.images]
    np.testing.assert_allclose(reopened[0].getData(), 1.0)
    np.testing.assert_allclose(reopened[1].getData(), 2.0)
    record = reopened[1].extraMetadata[PROVENANCE_KEY]  # kept in its .aux.xml
    assert record["process"] == "Slope" and record["parameters"] == {"Units": "degrees"}
    (saved,) = state.workspaces
    assert saved.kind == "general" and saved.images == (state.images[0],)
    assert saved.extra["lines"][0]["name"] == "Rim"

    manifest = json.loads((opened / "manifest.json").read_text())
    assert manifest["format"] == "varda-package" and manifest["varda"]
    assert [i["name"] for i in manifest["images"]] == [onDisk.name, "scene slope"]
    assert manifest["images"][0]["source"].endswith("scene.img")
    assert verifyPackage(opened) == []
    (opened / manifest["images"][0]["files"][0]).write_bytes(b"changed")
    assert verifyPackage(opened) == [manifest["images"][0]["files"][0]]


def test_sizes_read_well_and_big_packages_are_flagged():
    assert formatBytes(512) == "512 bytes"
    assert formatBytes(3 * 1024**3) == "3.0 GB"
    assert LARGE_BYTES == 1024**3
