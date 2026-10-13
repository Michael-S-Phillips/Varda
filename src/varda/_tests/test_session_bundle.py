"""Self-contained sessions: results that exist only in memory travel with the
session in one zip; paths inside it are relative."""

import zipfile

import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_loading.image_loading_service import openDataSource
from varda.image_loading.raster_writer import writeRaster
from varda.session import (
    SessionState,
    WorkspaceState,
    openSessionBundle,
    readSession,
    saveSessionBundle,
    writeSession,
)


def _raster(name, value=1.0) -> VardaRaster:
    data = np.full((4, 5, 3), value, dtype=np.float32)
    return VardaRaster(
        ArrayDataSource(
            data, wavelengths=np.array([500.0, 600.0, 700.0]), wavelengthUnits="nm"
        ),
        name=name,
    )


def test_paths_inside_the_session_folder_are_stored_relative(tmp_path):
    inside = tmp_path / "data" / "a.img"
    state = SessionState(
        (str(inside), "/elsewhere/b.img"), (WorkspaceState("general", (str(inside),)),)
    )
    path = writeSession(state, tmp_path / "work", relativeTo=tmp_path)
    assert '"data/a.img"' in path.read_text()
    moved = tmp_path.parent / "moved"
    tmp_path.rename(moved)
    loaded = readSession(moved / "work.varda")
    assert loaded.images == (str(moved / "data" / "a.img"), "/elsewhere/b.img")
    assert loaded.workspaces[0].images == (str(moved / "data" / "a.img"),)


def test_a_bundle_carries_in_memory_results_and_restores_from_anywhere(tmp_path):
    original = writeRaster(_raster("scene"), tmp_path / "scene.img")
    onDisk = VardaRaster.fromDataSource(openDataSource(str(original)))
    result = _raster("scene slope", 2.0)  # only in memory
    bundle = saveSessionBundle([onDisk, result], [], tmp_path / "project")
    assert bundle.name == "project.varda.zip"
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
    assert "session.varda" in names
    assert any(n.startswith("data/") and n.endswith(".img") for n in names)

    sessionFile = openSessionBundle(bundle, tmp_path / "opened")
    state = readSession(sessionFile)
    assert state.images[0] == str(original)
    restored = state.images[1]
    assert restored.startswith(str(tmp_path / "opened"))
    np.testing.assert_allclose(openDataSource(restored).readAllBands(), 2.0)
