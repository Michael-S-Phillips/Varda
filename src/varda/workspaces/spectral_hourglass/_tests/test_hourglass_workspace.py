"""The spectral hourglass workspace, driven end to end."""

import numpy as np
import pytest
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor

from synthetic_scene import PATCHES, WAVELENGTHS, endmemberSpectra, syntheticScene
from varda.analysis.spectral_library import LibrarySpectrum
from varda.image_rendering.image_renderer import RenderMode
from varda.workspaces.spectral_hourglass.hourglass_model import (
    MapMethod,
    Step,
    StepState,
)
from varda.workspaces.spectral_hourglass.hourglass_workspace import (
    SpectralHourglassWorkspace,
)
from varda.image_rendering.raster_view.viewport_tools.roi_tools import ROIDrawTool
from varda.workspaces.spectral_hourglass import scene_view
from varda.workspaces.spectral_hourglass.scene_view import Overlay
from varda.common.entities import ROIMode
from shapely.geometry import Polygon


@pytest.fixture
def workspace(qtbot):
    image, _ = syntheticScene()
    library = [
        LibrarySpectrum(name, WAVELENGTHS, spectrum * 1.1)
        for name, spectrum in zip(["Flat", "Kaolinite", "Pyroxene"], endmemberSpectra())
    ]
    images = [image]
    ws = SpectralHourglassWorkspace(image, images, library=library)
    ws.runner.synchronous = True
    qtbot.addWidget(ws)
    return ws


def _runThroughPpi(ws):
    ws.pipeline.preparePage.runButton.click()
    ws.pipeline.reducePage.runButton.click()
    ws.pipeline.reducePage.components.set(3)
    page = ws.pipeline.purityPage
    page.iterations.setValue(3000)
    page.threshold.setValue(0.5)
    page.maxCandidates.setValue(300)
    page.runButton.click()


def test_steps_unlock_in_order(workspace):
    pipeline = workspace.pipeline
    assert not pipeline.reducePage.runButton.isEnabled()
    pipeline.preparePage.runButton.click()
    assert workspace.model.state(Step.PREPARE) is StepState.DONE
    assert pipeline.reducePage.runButton.isEnabled()
    assert pipeline.itemText(0).startswith("✓")


def test_mnf_offers_component_overlays(workspace):
    workspace.pipeline.preparePage.runButton.click()
    workspace.pipeline.reducePage.runButton.click()
    assert workspace.pipeline.reducePage.plot is not None
    workspace.scene.showOverlay(Overlay.MNF)
    assert workspace.scene.currentOverlay() == Overlay.MNF


def test_ppi_fills_the_nd_view_and_shows_the_ppi_overlay(workspace):
    _runThroughPpi(workspace)
    assert (
        workspace.nd.projected().shape[0] == workspace.model.candidatePixels().size > 0
    )
    assert workspace.scene.currentOverlay() == Overlay.PPI
    assert workspace.nd.activeDims() == [0, 1, 2]


def test_lasso_puts_pixels_in_a_new_endmember_and_plots_its_spectrum(workspace):
    _runThroughPpi(workspace)
    big = 1e6
    workspace.nd.selectPolygon(
        [(-big, -big), (big, -big), (big, big), (-big, big)], True
    )
    model = workspace.model
    assert len(model.endmembers) == 1
    assert model.endmembers[0].pixels.size == model.candidatePixels().size
    assert workspace.model.state(Step.ENDMEMBERS) is StepState.DONE
    assert len(workspace.spectraPlot.plots) == 1


def test_changing_components_marks_purity_stale_in_the_titles(workspace):
    _runThroughPpi(workspace)
    workspace.pipeline.reducePage.components.set(2)
    assert "needs re-running" in workspace.pipeline.itemText(2)


def test_suggest_identify_and_map_end_to_end(workspace):
    _runThroughPpi(workspace)
    model = workspace.model
    for name, (r0, c0) in PATCHES.items():
        endmember = model.addEndmember(name)
        model.assignPixels(
            endmember.id,
            [r * 36 + c for r in range(r0, r0 + 4) for c in range(c0, c0 + 4)],
        )
    workspace.identifyPanel.identifyAll()
    assert [e.identification.split(" (")[0] for e in model.endmembers] == [
        "Flat",
        "Kaolinite",
        "Pyroxene",
    ]

    page = workspace.pipeline.mapPage
    page.buttons[MapMethod.SAM].setChecked(True)
    page.runButton.click()
    result = workspace.projectImages[-1]
    assert result.name == "scene SAM"
    assert workspace.scene.currentOverlay() == "Map: SAM"
    assert model.state(Step.MAP) is StepState.DONE

    page.buttons[MapMethod.MTMF].setChecked(True)
    page.runButton.click()
    assert workspace.projectImages[-1].name == "scene MTMF"
    assert page.review.isVisibleTo(page)
    page.review.endmemberBox.setCurrentIndex(1)
    page.review.scoreLine.setValue(0.8)
    assert workspace.scene.currentOverlay() == Overlay.DETECTIONS
    page.review.sigAddToProject.emit(page.review.detectionsRaster())
    assert workspace.projectImages[-1].name.startswith("scene MTMF detections")


def test_hovering_a_point_marks_the_pixel_and_plots_it(workspace):
    _runThroughPpi(workspace)
    pixel = int(workspace.model.candidatePixels()[0])
    workspace.nd.sigPointHovered.emit(pixel)
    assert workspace.scene.hoverItem.data.size == 1
    assert any(c.plotDataItem.name() == "Pixel" for c in workspace.spectraPlot.plots)


def test_mnf_and_ppi_can_join_the_project(workspace):
    _runThroughPpi(workspace)
    workspace.pipeline.reducePage.addButton.click()
    workspace.pipeline.purityPage.addButton.click()
    names = [image.name for image in workspace.projectImages]
    assert names[-2:] == ["scene MNF", "scene PPI"]
    assert workspace.projectImages[-2].bandCount == 3


def test_library_preview_is_plotted_scaled(workspace):
    _runThroughPpi(workspace)
    model = workspace.model
    endmember = model.addEndmember("clay")
    model.assignPixels(
        endmember.id, [r * 36 + c for r in range(2, 6) for c in range(30, 34)]
    )
    workspace.endmemberTable.setActiveEndmember(endmember.id)
    workspace.identifyPanel.table.cellDoubleClicked.emit(0, 1)
    names = [c.plotDataItem.name() for c in workspace.spectraPlot.plots]
    assert any(name.endswith("(scaled)") for name in names)


def test_ctrl_z_undoes_a_lasso(workspace, qtbot):
    _runThroughPpi(workspace)
    big = 1e6
    workspace.nd.selectPolygon(
        [(-big, -big), (big, -big), (big, big), (-big, big)], True
    )
    assert workspace.model.endmembers[0].pixels.size > 0
    workspace.undoShortcut.activated.emit()
    assert all(e.pixels.size == 0 for e in workspace.model.endmembers)


def test_display_controls_drive_the_scene_image(workspace):
    settings = workspace.scene.renderer.settings
    assert workspace.displayPanel.settings is settings
    settings.mode.set(RenderMode.MONO)
    settings.mono.band.set(5)
    assert workspace.scene.renderer.settings.mono.band.get() == 5
    assert workspace.histogram is not None


def _withPatchEndmembers(workspace):
    _runThroughPpi(workspace)
    for name, (r0, c0) in PATCHES.items():
        endmember = workspace.model.addEndmember(name)
        workspace.model.assignPixels(
            endmember.id,
            [r * 36 + c for r in range(r0, r0 + 4) for c in range(c0, c0 + 4)],
        )


def test_every_map_result_keeps_its_own_overlay_entry(workspace):
    _withPatchEndmembers(workspace)
    page = workspace.pipeline.mapPage
    for method in (MapMethod.SAM, MapMethod.UNMIX, MapMethod.MTMF):
        page.buttons[method].setChecked(True)
        page.runButton.click()
    scene = workspace.scene
    overlays = [scene.overlayBox.itemText(i) for i in range(scene.overlayBox.count())]
    for label in ("Map: SAM", "Map: Unmixing", "Map: MTMF"):
        assert label in overlays
    assert (
        scene.currentOverlay() == "Map: MTMF"
    )  # the latest, not the review's detections
    scene.showOverlay("Map: Unmixing")
    bands = [scene.mapBandBox.itemText(i) for i in range(scene.mapBandBox.count())]
    assert bands[0] == "All endmembers" and bands[1:4] == ["flat", "clay", "mafic"]
    assert scene._overlayRenderer is not None
    scene._overlayRenderer.render()


def test_all_endmembers_composite_colours_each_by_its_endmember(workspace):
    _withPatchEndmembers(workspace)
    page = workspace.pipeline.mapPage
    page.buttons[MapMethod.UNMIX].setChecked(True)
    page.runButton.click()
    rgb = workspace.scene.compositeImage(workspace.projectImages[-1])
    assert rgb.shape == (40, 36, 3) and rgb.min() >= 0 and rgb.max() <= 1
    clay = workspace.model.endmembers[1].color  # pure clay patch at (3, 31)
    expected = QColor(clay)
    np.testing.assert_allclose(
        rgb[3, 31], [expected.redF(), expected.greenF(), expected.blueF()], atol=0.08
    )


def test_moving_the_mtmf_thresholds_shows_the_detections(workspace):
    _withPatchEndmembers(workspace)
    page = workspace.pipeline.mapPage
    page.buttons[MapMethod.MTMF].setChecked(True)
    page.runButton.click()
    assert workspace.scene.currentOverlay() == "Map: MTMF"
    page.review.scoreLine.setValue(0.7)
    assert workspace.scene.currentOverlay() == Overlay.DETECTIONS


def test_the_active_endmember_stands_out_in_the_spectra_plot(workspace):
    _withPatchEndmembers(workspace)
    clay = workspace.model.endmembers[1]
    workspace.endmemberTable.setActiveEndmember(clay.id)
    curves = {c.plotDataItem.name(): c for c in workspace.spectraPlot.plots}
    active, other = curves["clay"], curves["flat"]
    assert workspace.spectraPlot.plots[-1] is active  # drawn on top
    assert active.config.width.value > other.config.width.value
    assert other.config.color.value.a < 0.5 <= active.config.color.value.a
    assert active.plotDataItem.opts["shadowPen"] is not None


def test_starting_over_from_purity_clears_the_candidates_and_overlay(workspace):
    _runThroughPpi(workspace)
    assert workspace.nd.projected().shape[0] > 0
    workspace.pipeline.startOverButtons[Step.PURITY].click()
    assert workspace.model.ppi is None
    assert workspace.nd.projected().shape[0] == 0
    overlays = [
        workspace.scene.overlayBox.itemText(i)
        for i in range(workspace.scene.overlayBox.count())
    ]
    assert Overlay.PPI not in overlays and Overlay.MNF in overlays
    assert workspace.pipeline.currentIndex() == list(Step).index(Step.PURITY)


def test_save_and_open_a_workflow_resumes_where_it_left_off(workspace, qtbot, tmp_path):
    _withPatchEndmembers(workspace)
    workspace.identifyPanel.excludeMatch("Pyroxene")
    path = workspace.saveWorkflow(tmp_path / "run.hourglass.json")
    assert workspace.model.ppi is not None
    counts = workspace.model.ppi.counts.copy()

    image = workspace.model.image
    fresh = SpectralHourglassWorkspace(
        image, [image], library=workspace.identifyPanel.library()
    )
    fresh.runner.synchronous = True
    qtbot.addWidget(fresh)
    fresh.openWorkflow(path)

    model = fresh.model
    assert [e.name for e in model.endmembers] == ["flat", "clay", "mafic"]
    assert model.state(Step.PURITY) is StepState.DONE and model.ppi is not None
    np.testing.assert_array_equal(model.ppi.counts, counts)
    assert model.components == 3
    assert fresh.nd.projected().shape[0] == model.candidatePixels().size > 0
    assert fresh.identifyPanel.excludedNames() == ["Pyroxene"]


def test_a_workflow_for_another_image_is_refused(workspace, qtbot, tmp_path):
    _runThroughPpi(workspace)
    path = workspace.saveWorkflow(tmp_path / "run.hourglass.json")
    other, _ = syntheticScene(rows=30, cols=30)
    fresh = SpectralHourglassWorkspace(other, [other])
    qtbot.addWidget(fresh)
    with pytest.raises(ValueError, match="different image"):
        fresh.openWorkflow(path)


def _drawAction(workspace):
    actions = workspace.scene.toolManager.getToolbar().actions()
    return next(a for a in actions if a.data() is ROIDrawTool)


def _draw(workspace, corners, *, remove=False, monkeypatch=None):
    """Draw a shape on the scene with the Draw on Image tool, in pixel
    coordinates (the synthetic scene isn't georeferenced)."""
    if monkeypatch is not None:
        monkeypatch.setattr(scene_view, "_removing", lambda: remove)
    if not isinstance(workspace.scene.toolManager.activeTool, ROIDrawTool):
        _drawAction(workspace).trigger()  # the tool stays on between shapes
    tool = workspace.scene.toolManager.activeTool
    assert isinstance(tool, ROIDrawTool)
    tool.sigROIDrawingComplete.emit(
        {"geometry": Polygon(corners), "roiType": ROIMode.RECTANGLE}
    )


def test_the_scene_toolbar_offers_drawing_endmember_pixels(workspace):
    action = _drawAction(workspace)
    assert action.text() == "Draw on Image"
    assert "endmember" in action.toolTip()


def test_drawing_adds_the_valid_pixels_inside_to_the_active_endmember(workspace):
    workspace.pipeline.preparePage.runButton.click()
    _draw(workspace, [(0, 0), (3, 0), (3, 3), (0, 3)])
    model = workspace.model
    assert len(model.endmembers) == 1  # a new endmember, as none was active
    width = workspace.scene.image.width
    expected = {r * width + c for r in range(3) for c in range(3)} - {
        0
    }  # (0, 0) is nodata
    assert set(model.endmembers[0].pixels.tolist()) == expected
    assert len(workspace.spectraPlot.plots) == 1


def test_drawing_with_shift_removes_pixels(workspace, monkeypatch):
    workspace.pipeline.preparePage.runButton.click()
    _draw(workspace, [(0, 0), (3, 0), (3, 3), (0, 3)], monkeypatch=monkeypatch)
    _draw(
        workspace,
        [(0, 0), (3, 0), (3, 1), (0, 1)],
        remove=True,
        monkeypatch=monkeypatch,
    )
    width = workspace.scene.image.width
    assert set(workspace.model.endmembers[0].pixels.tolist()) == {
        r * width + c for r in (1, 2) for c in range(3)
    }


def test_drawing_before_prepare_changes_nothing(workspace):
    _draw(workspace, [(0, 0), (3, 0), (3, 3), (0, 3)])
    assert workspace.model.endmembers == []


def test_the_shape_picker_shows_with_the_draw_tool(workspace):
    scene = workspace.scene
    assert scene.shapeBox.isHidden()
    _drawAction(workspace).trigger()
    assert not scene.shapeBox.isHidden()
    scene.shapeBox.setCurrentIndex(scene.shapeBox.findData(ROIMode.POLYGON))
    assert scene.toolManager.activeTool.shape is ROIMode.POLYGON
    _drawAction(workspace).trigger()  # off again
    assert scene.shapeBox.isHidden()


def test_a_crop_box_on_the_scene_adds_a_crop_to_the_project(workspace):
    workspace.scene.sigCropRequested.emit(QRect(0, 0, 10, 12))
    cropped = workspace.projectImages[-1]
    assert (cropped.width, cropped.height) == (10, 12)
    assert "Spectral Hourglass" in workspace.status.currentMessage()


def test_ppi_uses_the_pages_seed_and_describes_it_in_the_project_image(workspace):
    page = workspace.pipeline.purityPage
    assert page.seed.value() == 0
    page.seed.setValue(42)
    _runThroughPpi(workspace)
    assert workspace.model.ppi is not None and workspace.model.ppi.seed == 42
    page.addButton.click()
    description = workspace.projectImages[-1].dataSource.description
    assert "3,000 iterations" in description and "seed 42" in description


def test_run_more_is_disabled_once_the_ppi_settings_change(workspace):
    _runThroughPpi(workspace)
    page = workspace.pipeline.purityPage
    assert page.moreButton.isEnabled()
    page.threshold.setValue(0.75)
    assert not page.moreButton.isEnabled()
    page.threshold.setValue(0.5)
    assert page.moreButton.isEnabled()
    page.seed.setValue(9)
    assert not page.moreButton.isEnabled()
    page.seed.setValue(0)
    workspace.pipeline.reducePage.components.set(2)
    assert not page.moreButton.isEnabled()


def test_run_more_adds_to_the_total_iterations(workspace):
    _runThroughPpi(workspace)
    page = workspace.pipeline.purityPage
    page.iterations.setValue(1000)
    page.moreButton.click()
    assert workspace.model.ppiIterations == 4000
    assert "4,000 iterations" in page.summary.text() and "seed 0" in page.summary.text()


def test_the_saved_workflow_records_the_seed_and_both_iteration_counts(workspace):
    _runThroughPpi(workspace)
    page = workspace.pipeline.purityPage
    page.iterations.setValue(1000)
    page.moreButton.click()
    state = workspace.sessionState()
    assert state["ppi"]["seed"] == 0
    assert state["ppi"]["iterationsPerRun"] == 1000
    assert state["ppiCounts"]["totalIterations"] == 4000
    assert state["ppiCounts"]["seed"] == 0

    page.seed.setValue(5)
    page.iterations.setValue(2000)
    workspace.restoreSessionState(state)
    assert (page.seed.value(), page.iterations.value()) == (0, 1000)
