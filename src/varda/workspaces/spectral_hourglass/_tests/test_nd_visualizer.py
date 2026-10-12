"""The n-D visualizer: projections, lasso selection and collapsing classes."""

import numpy as np
import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtWidgets import QToolButton

from varda.workspaces.spectral_hourglass.nd_visualizer import NdVisualizer


@pytest.fixture
def viz(qtbot):
    widget = NdVisualizer()
    qtbot.addWidget(widget)
    rng = np.random.default_rng(0)
    points = rng.normal(size=(300, 4))
    points[:10] += np.array([8.0, 0, 0, 0])  # a corner
    widget.setData(points, np.arange(1000, 1300), background=rng.normal(size=(500, 4)))
    return widget


def test_projection_is_two_dimensional_and_uses_every_dimension_by_default(viz):
    assert viz.projected().shape == (300, 2)
    assert viz.activeDims() == [0, 1, 2, 3]
    plane = viz.plane()
    np.testing.assert_allclose(plane.T @ plane, np.eye(2), atol=1e-9)


def test_stepping_the_tour_moves_the_points_smoothly(viz):
    before = viz.projected().copy()
    viz.step()
    after = viz.projected()
    assert not np.allclose(before, after)
    assert np.abs(after - before).max() < 1.0  # a small rotation, not a jump


def test_new_projection_jumps(viz):
    before = viz.plane().copy()
    viz.newProjection()
    assert not np.allclose(before, viz.plane())


def test_switching_off_dimensions_removes_them_from_the_projection(viz):
    viz.setActiveDims([0, 2])
    plane = viz.plane()
    np.testing.assert_allclose(plane[[1, 3]], 0.0, atol=1e-12)
    viz.step()
    np.testing.assert_allclose(viz.plane()[[1, 3]], 0.0, atol=1e-12)


def test_lasso_emits_the_pixel_ids_inside_the_polygon(viz, qtbot):
    projected = viz.projected()
    inside = (projected[:, 0] > 0) & (projected[:, 1] > 0)
    big = 100.0
    polygon = [(0, 0), (big, 0), (big, big), (0, big)]
    with qtbot.waitSignal(viz.sigLassoSelected) as blocker:
        viz.selectPolygon(polygon, add=True)
    ids, add = blocker.args
    assert add is True
    assert sorted(ids) == sorted((np.arange(1000, 1300))[inside])


def test_point_colours_follow_class_membership(viz):
    viz.setPointColors({1000: "#ff0000", 1001: "#00ff00"})
    colors = viz.pointColors()
    assert colors[0] == "#ff0000" and colors[1] == "#00ff00"
    assert colors[2] == viz.UNASSIGNED_COLOR


def test_collapsing_projects_class_means_to_one_point(viz):
    rng = np.random.default_rng(1)
    means = [rng.normal(size=4) * 5, rng.normal(size=4) * 5]
    viz.setCollapseMeans(means)
    projectedMeans = viz.projectPoints(np.array(means))
    np.testing.assert_allclose(projectedMeans[0], projectedMeans[1], atol=1e-9)
    viz.setCollapseMeans(None)
    projectedMeans = viz.projectPoints(np.array(means))
    assert not np.allclose(projectedMeans[0], projectedMeans[1])


def test_hovering_reports_the_nearest_point(viz, qtbot):
    target = viz.projected()[5]
    assert viz.pointNear(target[0], target[1]) == 1005
    assert viz.pointNear(1e6, 1e6) is None


def test_new_data_leaves_no_stray_dimension_buttons(viz):
    rng = np.random.default_rng(2)
    viz.setData(rng.normal(size=(50, 3)), np.arange(50))
    viz.setData(rng.normal(size=(50, 3)), np.arange(50))
    buttons = [
        b
        for b in viz.findChildren(QToolButton)
        if b.parent() is viz and b.isVisibleTo(viz) and b.text().isdigit()
    ]
    assert [b.text() for b in buttons] == ["1", "2", "3"]


def test_view_frames_the_projected_cloud_in_many_dimensions(qtbot):
    widget = NdVisualizer()
    qtbot.addWidget(widget)
    rng = np.random.default_rng(0)
    widget.setData(rng.normal(size=(2000, 18)), np.arange(2000))
    (x0, x1), _ = widget.viewBox.viewRange()
    typical = np.percentile(np.abs(widget.projected()), 99)
    assert (x1 - x0) / 2 < 3 * typical  # not sized by the 18-D radius (~4.2x)


def test_the_tour_never_jumps_between_segments(viz):
    """Crossing from one random target to the next must not snap the view."""
    viz.speedSlider.setValue(20)
    steps = []
    previous = viz.projected().copy()
    for _ in range(60):  # several segment boundaries at 0.08 per step
        viz.step()
        steps.append(np.abs(viz.projected() - previous).max())
        previous = viz.projected().copy()
    assert max(steps) < 4 * np.median(steps)


def test_holding_step_repeats_it(viz):
    assert viz.stepButton.autoRepeat()
    assert viz.stepButton.autoRepeatInterval() <= 50


def test_dragging_in_rotate_mode_turns_the_cloud(viz):
    viz.setMode(viz.ROTATE)
    before = viz.plane().copy()
    viz.rotateBy(30.0, 0.0)
    after = viz.plane()
    assert not np.allclose(before, after)
    np.testing.assert_allclose(after.T @ after, np.eye(2), atol=1e-9)
    viz.setActiveDims([0, 2])
    viz.rotateBy(10.0, -15.0)
    np.testing.assert_allclose(viz.plane()[[1, 3]], 0.0, atol=1e-12)


def test_lasso_and_rotate_modes_are_exclusive(viz):
    viz.setMode(viz.LASSO)
    assert viz.lassoButton.isChecked() and not viz.rotateButton.isChecked()
    viz.rotateButton.click()
    assert viz.mode() == viz.ROTATE and not viz.lassoButton.isChecked()


def test_axis_arrows_show_each_active_dimension_in_the_view(viz):
    viz.setActiveDims([0, 1, 3])
    arrows = viz.axisVectors()
    assert sorted(arrows) == [0, 1, 3]
    plane = viz.plane()
    np.testing.assert_allclose(arrows[3], plane[3])  # unit vector of MNF 4, projected


class _FakeDrag:
    def __init__(self, button, start, end, finish=False):
        self._button, self._start, self._end, self._finish = button, start, end, finish

    def button(self):
        return self._button

    def isStart(self):
        return False

    def isFinish(self):
        return self._finish

    def pos(self):
        return self._end

    def lastPos(self):
        return self._start

    def scenePos(self):
        return self._end

    def lastScenePos(self):
        return self._start

    def modifiers(self):
        return Qt.KeyboardModifier.NoModifier

    def accept(self):
        pass


def test_right_drag_pans_rather_than_zooms(viz, qtbot):
    viz.resize(500, 500)
    viz.show()
    qtbot.waitExposed(viz)
    (x0, x1), (y0, y1) = viz.viewBox.viewRange()
    viz.viewBox.mouseDragEvent(
        _FakeDrag(Qt.MouseButton.RightButton, QPointF(100, 100), QPointF(140, 100))
    )
    (a0, a1), (b0, b1) = viz.viewBox.viewRange()
    assert a1 - a0 == pytest.approx(x1 - x0, rel=1e-6)  # same zoom
    assert a0 != pytest.approx(x0)  # moved sideways


def test_trackball_drag_is_relative_to_the_press_and_reversible(viz):
    viz.setMode(viz.ROTATE)
    start = viz.plane().copy()
    viz.beginRotate()
    viz.dragRotate(40.0, 0.0)
    moved = viz.plane().copy()
    viz.dragRotate(80.0, 0.0)
    viz.dragRotate(0.0, 0.0)  # back to where the drag started
    np.testing.assert_allclose(viz.plane(), start, atol=1e-9)
    viz.dragRotate(40.0, 0.0)
    np.testing.assert_allclose(
        viz.plane(), moved, atol=1e-9
    )  # no drift from the path taken
    viz.endRotate()


def test_dragging_right_moves_the_hidden_depth_towards_the_cursor(viz):
    viz.beginRotate()
    depth = viz._rotateFrame[:, 2]  # the hidden direction frozen at the press
    viz.dragRotate(30.0, 0.0)
    assert (viz.projectPoints(depth[None, :])[0, 0]) > 0  # grab-the-ball convention
    viz.dragRotate(0.0, 30.0)  # drag down: depth goes down on screen (y up)
    assert (viz.projectPoints(depth[None, :])[0, 1]) < 0
    viz.endRotate()


def test_rotation_stays_within_the_tour_dimensions(viz):
    viz.setActiveDims([0, 2, 3])
    viz.beginRotate()
    viz.dragRotate(25.0, -60.0)
    viz.endRotate()
    np.testing.assert_allclose(viz.plane()[1], 0.0, atol=1e-12)
    np.testing.assert_allclose(viz.plane().T @ viz.plane(), np.eye(2), atol=1e-9)


def test_cursor_follows_the_mode(viz):
    viz.setMode(viz.ROTATE)
    assert viz.plotWidget.viewport().cursor().shape() == Qt.CursorShape.OpenHandCursor
    viz.setMode(viz.LASSO)
    assert viz.plotWidget.viewport().cursor().shape() == Qt.CursorShape.CrossCursor


def test_the_tour_pauses_while_dragging_and_resumes(viz):
    viz.playButton.setChecked(True)
    viz.beginRotate()
    assert not viz._timer.isActive()
    viz.endRotate()
    assert viz._timer.isActive()
    viz.playButton.setChecked(False)
