"""Image Properties: shows the metadata, turns what's changed into edits
(only what differs from the file), and can save them into an ENVI header."""

import numpy as np
import pytest
from PyQt6.QtCore import Qt

from varda.all_images_view_list.image_properties_dialog import (
    GOOD,
    NAME,
    WAVELENGTH,
    ImagePropertiesDialog,
    parseNoData,
)
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_loading.image_loading_service import openDataSource
from varda.image_loading.raster_writer import writeRaster


def _image():
    data = np.arange(24, dtype=np.float32).reshape(2, 3, 4)
    return VardaRaster(
        ArrayDataSource(data, wavelengths=np.array([1.0, 2.0, 3.0, 4.0])), name="cube"
    )


def test_no_data_values_read_as_typed():
    assert parseNoData("") is None and parseNoData(" none ") is None
    assert parseNoData("-999") == -999.0 and np.isnan(parseNoData("nan"))
    with pytest.raises(ValueError):
        parseNoData("lots")


def test_nothing_changed_is_no_edit(qtbot):
    dialog = ImagePropertiesDialog(_image())
    qtbot.addWidget(dialog)
    assert dialog.edits() == ({}, "cube")


def test_changes_become_edits_and_apply(qtbot):
    image = _image()
    dialog = ImagePropertiesDialog(image)
    qtbot.addWidget(dialog)
    dialog.nameEdit.setText("scene")
    dialog.noDataEdit.setText("0")
    dialog.unitsBox.setCurrentText("µm")
    dialog.table.item(2, GOOD).setCheckState(Qt.CheckState.Unchecked)
    dialog.table.item(0, NAME).setText("blue")
    dialog.fillStart.setValue(0.5)
    dialog.fillStep.setValue(0.1)
    dialog.fillWavelengths()
    overrides, name = dialog.edits()
    assert overrides["nodata"] == 0.0 and overrides["wavelengthUnits"] == "µm"
    assert overrides["bbl"] == [1, 1, 0, 1] and overrides["bandNames"][0] == "blue"
    np.testing.assert_allclose(overrides["wavelengths"], [0.5, 0.6, 0.7, 0.8])
    dialog.accept()
    assert image.name == "scene" and image.nodata == 0.0
    np.testing.assert_allclose(image.bandModel.centers, [500, 600, 700, 800])


def test_a_wavelength_that_does_not_read_is_refused(qtbot):
    dialog = ImagePropertiesDialog(_image())
    qtbot.addWidget(dialog)
    dialog.table.item(1, WAVELENGTH).setText("blue")
    with pytest.raises(ValueError, match="wavelength"):
        dialog.edits()


def test_edits_save_into_an_envi_header(qtbot, tmp_path):
    path = writeRaster(_image(), tmp_path / "cube.img")
    image = VardaRaster(openDataSource(str(path)))
    dialog = ImagePropertiesDialog(image)
    qtbot.addWidget(dialog)
    assert dialog.saveToFile.isEnabled()
    dialog.noDataEdit.setText("-1")
    dialog.saveToFile.setChecked(True)
    dialog.accept()
    reopened = VardaRaster(openDataSource(str(path)))
    assert reopened.nodata == -1.0
