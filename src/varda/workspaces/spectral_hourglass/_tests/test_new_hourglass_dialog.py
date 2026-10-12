"""The menu actions open a dialog that stays open (and makes a workspace)."""

import gc

from PyQt6.QtWidgets import QMainWindow

from synthetic_scene import syntheticScene
from varda._actions._processing_actions import openSpectralHourglass
from varda._actions._workspace_actions import newSpectralHourglassWorkspace
from varda.workspaces.spectral_hourglass.hourglass_workspace import (
    SpectralHourglassWorkspace,
)
from varda.workspaces.spectral_hourglass.new_hourglass_dialog import (
    NewSpectralHourglassDialog,
)


class FakeMainGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tabs = []

    def addTab(self, widget, title=None):
        self.tabs.append(widget)


def _openedDialog(qtbot, action):
    image, _ = syntheticScene()
    gui = FakeMainGui()
    qtbot.addWidget(gui)
    action([image], gui)
    gc.collect()
    dialogs = [w for w in gui.findChildren(NewSpectralHourglassDialog) if w.isVisible()]
    return gui, dialogs


def test_workspace_menu_dialog_survives_and_opens_the_workspace(qtbot):
    gui, dialogs = _openedDialog(qtbot, newSpectralHourglassWorkspace)
    assert len(dialogs) == 1
    dialogs[0].accept()
    assert len(gui.tabs) == 1 and isinstance(gui.tabs[0], SpectralHourglassWorkspace)
    qtbot.addWidget(gui.tabs[0])


def test_processing_menu_dialog_survives(qtbot):
    _, dialogs = _openedDialog(qtbot, openSpectralHourglass)
    assert len(dialogs) == 1
