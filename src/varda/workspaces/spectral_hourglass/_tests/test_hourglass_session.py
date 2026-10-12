"""Spectral hourglass workspaces are saved in sessions and restored."""

from synthetic_scene import PATCHES, syntheticScene
from varda.common.di_types import ProjectImages
from varda.session import captureSession, readSession, writeSession
from varda.session_restore import SessionRestorer
from varda.workspaces.spectral_hourglass.hourglass_workspace import (
    SpectralHourglassWorkspace,
)

PATH = "/data/scene.img"


def _workspace(qtbot):
    image, _ = syntheticScene(filePath=PATH)
    ws = SpectralHourglassWorkspace(image, [image])
    ws.runner.synchronous = True
    qtbot.addWidget(ws)
    prepare = ws.pipeline.preparePage
    prepare.limitBox.setChecked(True)
    prepare.low.setValue(1100.0)
    prepare.high.setValue(2500.0)
    prepare.runButton.click()
    ws.pipeline.reducePage.runButton.click()
    ws.pipeline.reducePage.components.set(3)
    ws.pipeline.purityPage.maxCandidates.setValue(500)
    for name, (r0, c0) in PATCHES.items():
        endmember = ws.model.addEndmember(name)
        ws.model.assignPixels(
            endmember.id,
            [r * 36 + c for r in range(r0, r0 + 4) for c in range(c0, c0 + 4)],
        )
    return image, ws


def test_capture_and_file_round_trip_keep_the_hourglass_state(qtbot, tmp_path):
    image, ws = _workspace(qtbot)
    capture = captureSession([image], [ws])
    (state,) = capture.state.workspaces
    assert (state.kind, state.images) == ("hourglass", (PATH,))
    assert state.extra["settings"]["wavelengthRange"] == [1100.0, 2500.0]
    assert state.extra["components"] == 3
    assert [e["name"] for e in state.extra["endmembers"]["endmembers"]] == list(PATCHES)

    path = writeSession(capture.state, tmp_path / "s")
    assert readSession(path).workspaces[0].extra == state.extra


def test_restore_reopens_the_hourglass_with_its_settings_and_endmembers(qtbot):
    image, ws = _workspace(qtbot)
    state = captureSession([image], [ws]).state

    class FakeMainGui:
        tabs: list = []

        def addTab(self, widget, title=None):
            self.tabs.append(widget)

    gui = FakeMainGui()
    restorer = SessionRestorer(
        ProjectImages(), gui, loadImage=lambda path, ok, fail: ok(image)
    )
    with qtbot.waitSignal(restorer.sigFinished, timeout=10_000):
        restorer.restore(state)

    (restored,) = gui.tabs
    qtbot.addWidget(restored)
    assert isinstance(restored, SpectralHourglassWorkspace)
    assert [e.name for e in restored.model.endmembers] == list(PATCHES)
    prepare = restored.pipeline.preparePage
    assert prepare.limitBox.isChecked() and prepare.low.value() == 1100.0
    assert restored.pipeline.purityPage.maxCandidates.value() == 500

    restored.runner.synchronous = True
    prepare.runButton.click()
    restored.pipeline.reducePage.runButton.click()
    assert restored.model.components == 3  # the saved count wins over the suggestion
