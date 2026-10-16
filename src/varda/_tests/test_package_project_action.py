"""File → Package Project: asks before a large package, writes in the
background and says where it went."""

import numpy as np
import pytest
from app_model import Application
from PyQt6.QtWidgets import QMessageBox

from varda._actions import _file_actions
from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.maingui import MainGUI

APP_NAME = "varda-test-package-project"


@pytest.fixture
def gui(qtbot):
    app = Application(APP_NAME)
    app.images = ProjectImages()
    gui = MainGUI(app)
    qtbot.addWidget(gui)
    yield gui
    Application.destroy(APP_NAME)


def _result():
    return VardaRaster(ArrayDataSource(np.ones((4, 5, 2), np.float32)), name="slope")


def test_packaging_writes_the_zip_and_reports_it(gui, qtbot, tmp_path, monkeypatch):
    target = tmp_path / "shared"
    monkeypatch.setattr(
        _file_actions.QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), "")
    )
    told = []
    monkeypatch.setattr(
        _file_actions.QMessageBox, "information", lambda *a, **k: told.append(a[2])
    )
    _file_actions.packageProject(ProjectImages([_result()]), gui)
    qtbot.waitUntil(lambda: bool(told), timeout=20000)
    assert (tmp_path / "shared.varda.zip").is_file()
    assert "shared.varda.zip" in told[0]


def test_a_large_package_asks_first(gui, monkeypatch):
    monkeypatch.setattr(_file_actions, "planPackage", _largePlan)
    asked = []

    def warning(parent, title, text, buttons):
        asked.append(text)
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(_file_actions.QMessageBox, "warning", warning)
    monkeypatch.setattr(
        _file_actions.QFileDialog,
        "getSaveFileName",
        lambda *a, **k: pytest.fail("canceled before choosing a file"),
    )
    _file_actions.packageProject(ProjectImages([_result()]), gui)
    assert "about 3.0 GB" in asked[0]


class _largePlan:
    totalBytes = 3 * 1024**3
    isLarge = True
    missing = ()

    def __init__(self, *_):
        pass
