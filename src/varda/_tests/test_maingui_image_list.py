"""The image list can be closed and brought back (View > Image List), and the
menu item's check mark follows it."""

import pytest
from app_model import Application

from varda.common.di_types import ProjectImages
from varda.context_keys import IMAGE_LIST_VISIBLE
from varda.maingui import MainGUI

APP_NAME = "varda-test-image-list"


@pytest.fixture
def gui(qtbot):
    app = Application(APP_NAME)
    app.images = ProjectImages()  # what VardaApplication provides
    gui = MainGUI(app)
    qtbot.addWidget(gui)
    gui.show()
    yield gui
    Application.destroy(APP_NAME)


def test_the_image_list_starts_open(gui):
    assert gui.imageListDock.isVisible()
    assert gui.app.context[IMAGE_LIST_VISIBLE] is True


def test_closing_the_image_list_unchecks_the_menu_item(gui):
    gui.imageListDock.close()  # its title bar's close button
    assert gui.app.context[IMAGE_LIST_VISIBLE] is False


def test_view_image_list_brings_it_back(gui):
    gui.imageListDock.close()
    gui.toggleImageList()
    assert gui.imageListDock.isVisible()
    assert gui.app.context[IMAGE_LIST_VISIBLE] is True
    gui.toggleImageList()
    assert not gui.imageListDock.isVisible()
