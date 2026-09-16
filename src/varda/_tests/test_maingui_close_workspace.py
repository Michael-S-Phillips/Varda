"""Closing a workspace removes its tab, runs its close handler, and destroys it."""

import pytest
from app_model import Application
from PyQt6.QtWidgets import QWidget

from varda.common.di_types import ProjectImages
from varda.context_keys import WORKSPACE_COUNT
from varda.maingui import MainGUI

APP_NAME = "varda-test-maingui"


class _Workspace(QWidget):
    def __init__(self):
        super().__init__()
        self.closed = False

    def closeEvent(self, event):
        self.closed = True
        super().closeEvent(event)


@pytest.fixture
def gui(qtbot):
    app = Application(APP_NAME)
    app.images = ProjectImages()  # what VardaApplication provides
    gui = MainGUI(app)
    qtbot.addWidget(gui)
    yield gui
    Application.destroy(APP_NAME)


def test_close_workspace_removes_tab_and_runs_close_handler(gui):
    first, second = _Workspace(), _Workspace()
    gui.addTab(first, "first")
    gui.addTab(second, "second")

    gui.closeWorkspace(first)

    assert gui.centralTabs.count() == 1
    assert gui.childWindows == [second]
    assert first.closed


def test_workspace_count_context_tracks_open_workspaces(gui):
    assert gui.app.context.get(WORKSPACE_COUNT) == 0
    workspace = _Workspace()
    gui.addTab(workspace, "w")
    assert gui.app.context.get(WORKSPACE_COUNT) == 1
    gui.closeWorkspace(workspace)
    assert gui.app.context.get(WORKSPACE_COUNT) == 0


def test_tab_close_button_closes_that_workspace(gui):
    workspace = _Workspace()
    gui.addTab(workspace, "w")

    gui.centralTabs.tabCloseRequested.emit(0)

    assert gui.centralTabs.count() == 0
    assert workspace.closed


def test_current_workspace_is_the_selected_tab(gui):
    first, second = _Workspace(), _Workspace()
    gui.addTab(first, "first")
    gui.addTab(second, "second")
    gui.centralTabs.setCurrentWidget(first)
    assert gui.currentWorkspace() is first


def test_closing_with_no_workspace_is_a_no_op(gui):
    gui.closeWorkspace(None)
    assert gui.childWindows == []
