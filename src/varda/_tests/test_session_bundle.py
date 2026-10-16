"""Session paths inside the session's folder are stored relative, so a
packaged project (see test_project_package) opens from anywhere."""

import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.session import (
    SessionState,
    WorkspaceState,
    readSession,
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
