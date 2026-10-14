"""New-workspace dialogs stay open until the user answers them. They used to
have no parent and no reference, so garbage collection closed them a moment
after they appeared."""

import gc

import numpy as np
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from varda._actions._workspace_actions import (
    newDualImageWorkspace,
    newGeneralAnalysisWorkspace,
)
from varda.all_images_view_list.image_list_actions import (
    ImageListClickContext,
    _openInDualImage,
)
from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


class _MainGui(QWidget):
    def addTab(self, widget, title=None) -> None:
        pass


def _images() -> ProjectImages:
    data = np.random.default_rng(0).random((10, 10, 3)).astype(np.float32)
    return ProjectImages([VardaRaster(ArrayDataSource(data), name=n) for n in "ab"])


def _openDialogs() -> list[QDialog]:
    gc.collect()
    QApplication.processEvents()
    return [
        w for w in QApplication.allWidgets() if isinstance(w, QDialog) and w.isVisible()
    ]


def _closeAll() -> None:
    for dialog in _openDialogs():
        dialog.close()


def test_the_image_list_dual_image_dialog_stays_open(qtbot):
    mainGui = _MainGui()
    qtbot.addWidget(mainGui)
    images = _images()
    _openInDualImage(ImageListClickContext([images[0]]), images, mainGui)  # ty: ignore[invalid-argument-type]
    assert len(_openDialogs()) == 1
    _closeAll()


def test_the_workspace_menu_dialogs_stay_open(qtbot):
    mainGui = _MainGui()
    qtbot.addWidget(mainGui)
    images = _images()
    for open_ in (newDualImageWorkspace, newGeneralAnalysisWorkspace):
        open_(images, mainGui)  # ty: ignore[invalid-argument-type]
        assert len(_openDialogs()) == 1, open_.__name__
        _closeAll()
