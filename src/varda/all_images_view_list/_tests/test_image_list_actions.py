"""Tests for the image list context-menu actions and the controller that runs them."""

import pytest
from app_model import Application

from varda.all_images_view_list import image_list_actions as ila
from varda.all_images_view_list.image_list_menu_controller import (
    ImageListMenuController,
)
from varda.common.di_types import ProjectImages
from varda.maingui import MainGUI
from varda.utilities.debug import generate_random_image
from varda.workspaces.general_image_analysis import GeneralImageAnalysisWorkflow

APP_NAME = "varda-test-image-list"


class FakeMainGui:
    def __init__(self) -> None:
        self.tabs: list[tuple[object, str | None]] = []

    def addTab(self, widget, title=None) -> None:
        self.tabs.append((widget, title))


@pytest.fixture
def app():
    app = Application(APP_NAME)
    app.register_actions(ila.IMAGE_LIST_ACTIONS)
    app.injection_store.register_provider(
        ila.getCurrentClickContext, ila.ImageListClickContext
    )
    yield app
    Application.destroy(APP_NAME)


def test_actions_registered_for_image_list_menu():
    ids = {a.id for a in ila.IMAGE_LIST_ACTIONS}
    assert ids == {ila.OPEN_GENERAL_ANALYSIS_ID, ila.OPEN_DUAL_IMAGE_ID, ila.ANALYZE_ID}
    for a in ila.IMAGE_LIST_ACTIONS:
        assert any(rule.id == ila.IMAGE_LIST_CONTEXT_MENU_ID for rule in a.menus)


def test_activating_image_opens_general_analysis_tab_for_that_image(qapp, app):
    images = ProjectImages()
    first = generate_random_image((20, 20, 10))
    second = generate_random_image((20, 20, 10))
    images.append(first)
    images.append(second)
    mainGui = FakeMainGui()
    app.injection_store.register_provider(lambda: images, ProjectImages)
    app.injection_store.register_provider(lambda: mainGui, MainGUI)

    ImageListMenuController(app).onImagesActivated([second])

    assert len(mainGui.tabs) == 1
    workspace, _title = mainGui.tabs[0]
    assert isinstance(workspace, GeneralImageAnalysisWorkflow)
    assert workspace.config.image.get() is second


def test_click_context_is_cleared_after_command_runs(qapp, app):
    images = ProjectImages()
    image = generate_random_image((20, 20, 10))
    images.append(image)
    app.injection_store.register_provider(lambda: images, ProjectImages)
    app.injection_store.register_provider(FakeMainGui, MainGUI)

    ImageListMenuController(app).onImagesActivated([image])

    assert ila.getCurrentClickContext() is None
