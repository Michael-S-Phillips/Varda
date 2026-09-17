"""The session is autosaved periodically and on quit, so a crash costs little."""

import numpy as np

from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.session import readSession, writeSession, SessionState
from varda.session_autosave import SessionAutosaver, defaultAutosavePath


def _image(name: str, path: str) -> VardaRaster:
    cube = np.random.default_rng(0).random((10, 10, 4))
    return VardaRaster(ArrayDataSource(cube, filePath=path), name=name)


class FakeMainGui:
    def __init__(self) -> None:
        self.childWindows = []


def test_saves_periodically_once_there_is_something_to_save(qtbot, tmp_path):
    target = tmp_path / "autosave.varda"
    images = ProjectImages([_image("a", "/data/a.img")])
    saver = SessionAutosaver(images, FakeMainGui(), path=target, intervalMs=50)

    qtbot.waitUntil(target.exists, timeout=3000)

    assert readSession(target).images == ("/data/a.img",)
    assert saver.path == target


def test_an_empty_project_does_not_overwrite_the_previous_autosave(tmp_path):
    target = tmp_path / "autosave.varda"
    writeSession(SessionState(images=("/data/old.img",), workspaces=()), target)
    saver = SessionAutosaver(ProjectImages(), FakeMainGui(), path=target)

    assert saver.saveNow() is None

    assert readSession(target).images == ("/data/old.img",)


def test_save_now_reports_what_was_saved(tmp_path):
    target = tmp_path / "autosave.varda"
    images = ProjectImages([_image("a", "/data/a.img"), _image("mem", None)])
    saver = SessionAutosaver(images, FakeMainGui(), path=target)

    capture = saver.saveNow()

    assert capture is not None
    assert capture.state.images == ("/data/a.img",)
    assert capture.unsavedImages == ("mem",)
    assert target.exists()


def test_quitting_the_application_saves(qapp, tmp_path):
    target = tmp_path / "autosave.varda"
    images = ProjectImages([_image("a", "/data/a.img")])
    saver = SessionAutosaver(images, FakeMainGui(), path=target)

    qapp.aboutToQuit.emit()

    assert readSession(target).images == ("/data/a.img",)
    del saver


def test_default_autosave_path_lives_in_the_app_data_folder(qapp):
    path = defaultAutosavePath()
    assert path.name == "autosave.varda"
    assert path.is_absolute()
