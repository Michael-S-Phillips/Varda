"""ISIS in the GUI: cam2map's dialog, and comparing the radiometry with
equalizer."""

import sys
from pathlib import Path

import numpy as np
import pytest

from varda.mosaicking.backends.isis import IsisInstall
from varda.mosaicking.recipe import Correction, RadiometryMethod
from varda.workspaces.mosaic import mosaic_workspace
from varda.workspaces.mosaic.cam2map_dialog import Cam2mapDialog
from varda.workspaces.mosaic.mosaic_workspace import MosaicWorkspace
from varda.workspaces.mosaic.panels import RADIOMETRY_COLUMNS
from varda.workspaces.mosaic._tests.test_radiometry_panel import _strip


def _fakeIsis(tmp_path: Path) -> IsisInstall:
    (tmp_path / "isis" / "bin").mkdir(parents=True)
    tool = tmp_path / "isis" / "bin" / "cam2map"
    tool.write_text(
        f"""#!{sys.executable}
import sys, pathlib
args = dict(a.split("=", 1) for a in sys.argv[1:])
pathlib.Path(args["to"]).write_text(" ".join(sorted(args)))
"""
    )
    tool.chmod(0o755)
    return IsisInstall(tmp_path / "isis", None, "8.0.0", "test")


def test_cam2map_projects_and_reports_the_output(qtbot, tmp_path):
    dialog = Cam2mapDialog(_fakeIsis(tmp_path))
    qtbot.addWidget(dialog)
    dialog.source.setText(str(tmp_path / "raw.cub"))
    assert dialog.target.text() == str(tmp_path / "raw_map.cub")
    dialog.resolution.setValue(6.0)
    with qtbot.waitSignal(dialog.sigProjected, timeout=10000) as blocker:
        dialog.runButton.click()
    written = Path(blocker.args[0])
    assert written == tmp_path / "raw_map.cub"
    assert "resolution" in written.read_text() and "interp" in written.read_text()


def test_matching_a_cube_needs_one(qtbot, tmp_path):
    dialog = Cam2mapDialog(_fakeIsis(tmp_path))
    qtbot.addWidget(dialog)
    dialog.source.setText(str(tmp_path / "raw.cub"))
    dialog.mapMatch.setChecked(True)
    assert not dialog.resolution.isEnabled()
    dialog.runButton.click()
    assert "Choose the cube" in dialog.status.text()
    dialog.mapPath.setText(str(tmp_path / "ref.cub"))
    options = dialog.options()
    assert options["matchMap"] and options["mapTemplate"] == tmp_path / "ref.cub"


def test_without_isis_nothing_runs(qtbot, monkeypatch):
    monkeypatch.setattr(
        "varda.workspaces.mosaic.cam2map_dialog.currentIsis", lambda: None
    )
    dialog = Cam2mapDialog()
    qtbot.addWidget(dialog)
    assert not dialog.runButton.isEnabled()
    assert "Not found" in dialog.status.text()


@pytest.fixture
def workspace(qtbot, monkeypatch):
    monkeypatch.setattr(
        mosaic_workspace,
        "currentIsis",
        lambda: IsisInstall(Path("/isis"), None, "8.0.0", "test"),
    )
    monkeypatch.setattr(
        mosaic_workspace,
        "crossCheckRadiometry",
        lambda project, mode, held, install, folder: {
            0: Correction(np.ones(2), np.zeros(2)),
            1: Correction(np.array([0.8, 1.25]), np.array([-0.04, -0.06])),
        },
    )
    rng = np.random.default_rng(0)
    scene = np.stack([rng.random((40, 100)), rng.random((40, 100))], axis=2)
    widget = MosaicWorkspace(
        [_strip(scene[:, :60], 0, "left"), _strip(scene[:, 40:], 40, "right")], []
    )
    qtbot.addWidget(widget)
    return widget


def test_the_comparison_shows_isis_beside_varda_and_can_be_used(workspace, qtbot):
    panel = workspace.radiometryPanel
    assert panel.compareIsis.isVisibleTo(panel)
    panel.compareIsis.click()
    qtbot.waitUntil(lambda: panel.compareIsis.isEnabled(), timeout=10000)
    column = RADIOMETRY_COLUMNS.index("ISIS gain")
    assert panel.table.item(1, column).text() == "1.0250"  # mean of 0.8 and 1.25
    assert "ISIS equalizer solved 2 images" in panel.status.text()
    panel.useIsis.click()
    assert np.allclose(workspace.project.input(1).radiometry.gain, [0.8, 1.25])
    assert workspace.project.radiometryMethod is RadiometryMethod.GLOBAL
