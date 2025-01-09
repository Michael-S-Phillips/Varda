import pytest
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication

from core.data import ProjectContext
from core.entities import Stretch, Metadata
from features.image_view_stretch import getStretchView
from features.image_view_stretch.stretch_viewmodel import StretchViewModel
from features.image_view_stretch.stretch_view import StretchView


@pytest.fixture
def projectContext():
    proj = ProjectContext()
    proj.createImage(
        raster=np.zeros((100, 100, 100)),
        metadata=Metadata(),
        stretch=[Stretch("test_image", 0, 255, 0, 255, 0, 255)],
    )
    return proj


@pytest.fixture
def viewModel(projectContext):
    return StretchViewModel(projectContext, 0)


def test_select_stretch(viewModel, projectContext):
    projectContext.addStretch(0, Stretch("new_stretch", 1, 100, 1, 100, 1, 100))
    viewModel.selectStretch(1)
    assert viewModel.stretchIndex == 1


def test_get_selected_stretch(viewModel, projectContext):
    stretch = viewModel.getSelectedStretch()
    assert stretch.name == "test_image"


def test_update_stretch(viewModel, projectContext):

    oldStretch = viewModel.getSelectedStretch()
    print(
        f"Before Update: {oldStretch.minR}, {oldStretch.maxR}, {oldStretch.minG}, {oldStretch.maxG}"
    )

    viewModel.updateStretch(minR=10, maxR=100, minG=20, maxG=200, minB=30, maxB=250)
    QCoreApplication.processEvents()  # Ensures signals are processed
    newStretch = viewModel.getSelectedStretch()
    print(
        f"After Update: {newStretch.minR}, {newStretch.maxR}, {newStretch.minG}, {newStretch.maxG}"
    )
    assert round(newStretch.minR) == 10
    assert round(newStretch.maxR) == 100
    assert round(newStretch.minG) == 20
    assert round(newStretch.maxG) == 200
    assert round(newStretch.minB) == 30
    assert round(newStretch.maxB) == 250


def test_signal_emission(viewModel, projectContext, qapp):
    def signal_emitted():
        signal_emitted.called = True

    signal_emitted.called = False
    viewModel.sigStretchChanged.connect(signal_emitted)
    projectContext.updateStretch(0, 0, Stretch("test", 1, 2, 3, 4, 5, 6))
    assert signal_emitted.called
