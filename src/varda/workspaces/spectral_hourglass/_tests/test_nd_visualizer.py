"""The n-D visualizer: projections, lasso selection and collapsing classes."""

import numpy as np
import pytest
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
        if b.parent() is viz and b.isVisibleTo(viz)
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
