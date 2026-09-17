"""Restoring a session reloads its images and rebuilds workspaces with their ROIs."""

import numpy as np
from shapely.geometry import box

from varda.common.di_types import ProjectImages
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.rois.roi_collection import ROICollection
from varda.session import SessionState, WorkspaceState, roisToJson
from varda.session_restore import SessionRestorer
from varda.workspaces.dual_image_workspace.dual_image_workspace import (
    DualImageWorkspace,
)
from varda.workspaces.general_image_analysis import GeneralImageAnalysisWorkflow

RED = Color(1.0, 0.0, 0.0, 0.5)


def _image(name: str, path: str) -> VardaRaster:
    cube = np.random.default_rng(0).random((20, 20, 10))
    source = ArrayDataSource(cube, wavelengths=np.arange(10.0), filePath=path)
    return VardaRaster(source, name=name)


class FakeMainGui:
    def __init__(self) -> None:
        self.tabs = []

    def addTab(self, widget, title=None) -> None:
        self.tabs.append((widget, title))


def _fakeLoader(available: dict[str, VardaRaster]):
    def load(path, onSuccess, onFailure):
        if path in available:
            onSuccess(available[path])
        else:
            onFailure(f"no such file {path}")

    return load


def _roisWithOneBox() -> dict:
    rois = ROICollection()
    rois.addROI(box(1, 1, 4, 4), "r1", RED, ROIMode.RECTANGLE)
    return roisToJson(rois)


def test_restore_loads_images_in_order_and_rebuilds_workspaces(qtbot):
    a, b = _image("a", "/data/a.img"), _image("b", "/data/b.img")
    state = SessionState(
        images=("/data/a.img", "/data/b.img"),
        workspaces=(
            WorkspaceState("general", ("/data/b.img",), _roisWithOneBox()),
            WorkspaceState(
                "dual", ("/data/a.img", "/data/b.img"), roisToJson(ROICollection())
            ),
        ),
    )
    images = ProjectImages()
    mainGui = FakeMainGui()
    restorer = SessionRestorer(
        images, mainGui, loadImage=_fakeLoader({a.filePath: a, b.filePath: b})
    )

    with qtbot.waitSignal(restorer.sigFinished, timeout=10_000) as blocker:
        restorer.restore(state)

    assert list(images) == [a, b]
    (general, _), (dual, _) = mainGui.tabs
    for widget, _ in mainGui.tabs:
        qtbot.addWidget(widget)
    assert isinstance(general, GeneralImageAnalysisWorkflow)
    assert general.config.image.get() is b
    assert [roi.name for roi in general.roiCollection.getAllROIs()] == ["r1"]
    assert isinstance(dual, DualImageWorkspace)
    assert (dual.image1, dual.image2) == (a, b)
    (report,) = blocker.args
    assert report.failed == ()
    assert report.workspaces == 2


def test_already_open_images_are_not_loaded_again(qtbot):
    a = _image("a", "/data/a.img")
    images = ProjectImages([a])
    calls = []

    def load(path, onSuccess, onFailure):
        calls.append(path)
        onSuccess(_image("a again", path))

    restorer = SessionRestorer(images, FakeMainGui(), loadImage=load)
    state = SessionState(images=("/data/a.img",), workspaces=())

    with qtbot.waitSignal(restorer.sigFinished, timeout=10_000):
        restorer.restore(state)

    assert calls == []
    assert list(images) == [a]


def test_missing_images_are_reported_and_their_workspaces_skipped(qtbot):
    a = _image("a", "/data/a.img")
    state = SessionState(
        images=("/data/a.img", "/data/gone.img"),
        workspaces=(
            WorkspaceState("general", ("/data/gone.img",), _roisWithOneBox()),
            WorkspaceState("general", ("/data/a.img",), _roisWithOneBox()),
        ),
    )
    images = ProjectImages()
    mainGui = FakeMainGui()
    restorer = SessionRestorer(images, mainGui, loadImage=_fakeLoader({a.filePath: a}))

    with qtbot.waitSignal(restorer.sigFinished, timeout=10_000) as blocker:
        restorer.restore(state)

    for widget, _ in mainGui.tabs:
        qtbot.addWidget(widget)
    assert list(images) == [a]
    assert len(mainGui.tabs) == 1
    (report,) = blocker.args
    assert report.failed == ("/data/gone.img",)
    assert report.workspaces == 1
