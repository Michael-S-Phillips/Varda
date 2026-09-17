"""Sessions: capture the open images, workspaces and ROIs; save and read them back."""

import json

import numpy as np
import pytest
from shapely.geometry import box

from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.rois.roi_collection import ROICollection
from varda.session import (
    SessionState,
    WorkspaceState,
    captureSession,
    readSession,
    roisFromJson,
    roisToJson,
    writeSession,
)
from varda.workspaces.dual_image_workspace.dual_image_workspace import (
    DualImageWorkspace,
    DualImageWorkspaceConfig,
)
from varda.workspaces.general_image_analysis import (
    GeneralImageAnalysisConfig,
    GeneralImageAnalysisWorkflow,
)

RED = Color(1.0, 0.0, 0.0, 0.5)


def _image(name: str, path: str | None) -> VardaRaster:
    cube = np.random.default_rng(0).random((20, 20, 10))
    source = ArrayDataSource(cube, wavelengths=np.arange(10.0), filePath=path)
    return VardaRaster(source, name=name)


def test_roi_json_round_trip():
    source = ROICollection()
    source.addColumn("note")
    source.addROI(box(2, 2, 6, 6), "square", RED, ROIMode.RECTANGLE, note="hi")

    data = roisToJson(source)
    restored = ROICollection()
    roisFromJson(data, restored)

    (roi,) = restored.getAllROIs()
    assert roi.name == "square"
    assert roi.roiType == ROIMode.RECTANGLE
    assert roi.color.toHexString() == RED.toHexString()
    assert roi.geometry.equals(box(2, 2, 6, 6))
    assert roi.properties["note"] == "hi"
    json.dumps(data)  # must be plain JSON


def test_capture_records_images_workspaces_and_rois(qtbot):
    a, b = _image("a", "/data/a.img"), _image("b", "/data/b.img")
    general = GeneralImageAnalysisConfig([a, b])
    general.image.set(b)
    generalWorkspace = GeneralImageAnalysisWorkflow(general)
    qtbot.addWidget(generalWorkspace)
    generalWorkspace.roiCollection.addROI(box(1, 1, 4, 4), "r1", RED, ROIMode.RECTANGLE)
    dual = DualImageWorkspaceConfig([a, b])
    dual.image1Param.set(a)
    dual.image2Param.set(b)
    dualWorkspace = DualImageWorkspace(dual)
    qtbot.addWidget(dualWorkspace)

    capture = captureSession([a, b], [generalWorkspace, dualWorkspace])

    assert capture.state.images == ("/data/a.img", "/data/b.img")
    assert capture.unsavedImages == ()
    first, second = capture.state.workspaces
    assert (first.kind, first.images) == ("general", ("/data/b.img",))
    assert len(first.rois["features"]) == 1
    assert (second.kind, second.images) == ("dual", ("/data/a.img", "/data/b.img"))
    assert second.rois["features"] == []


def test_images_without_a_file_are_reported_and_their_workspaces_skipped(qtbot):
    saved, unsaved = _image("saved", "/data/saved.img"), _image("result", None)
    config = GeneralImageAnalysisConfig([saved, unsaved])
    config.image.set(unsaved)
    workspace = GeneralImageAnalysisWorkflow(config)
    qtbot.addWidget(workspace)

    capture = captureSession([saved, unsaved], [workspace])

    assert capture.state.images == ("/data/saved.img",)
    assert capture.unsavedImages == ("result",)
    assert capture.state.workspaces == ()


def test_write_and_read_round_trip(tmp_path):
    state = SessionState(
        images=("/data/a.img", "/data/b.img"),
        workspaces=(
            WorkspaceState(
                "dual", ("/data/a.img", "/data/b.img"), roisToJson(ROICollection())
            ),
        ),
    )

    path = writeSession(state, tmp_path / "work")

    assert path == tmp_path / "work.varda"
    assert readSession(path) == state


def test_reading_a_non_session_file_is_a_clear_error(tmp_path):
    bogus = tmp_path / "x.varda"
    bogus.write_text('{"hello": 1}')
    with pytest.raises(ValueError, match="not a Varda session"):
        readSession(bogus)
