"""Tests for ROITableModel denominator badge/state."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from shapely.geometry import box

from varda.common.entities import Color, ROIMode
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_table_model import ROITableModel

RED = Color(1.0, 0.0, 0.0, 0.5)


def _collection_with_two() -> ROICollection:
    c = ROICollection()
    c.addROI(box(0, 0, 5, 5), "alpha", RED, ROIMode.RECTANGLE)
    c.addROI(box(0, 0, 5, 5), "beta", RED, ROIMode.RECTANGLE)
    return c


def test_default_no_denominator(qtbot):
    model = ROITableModel(_collection_with_two())
    assert model.denominatorFid is None


def test_set_denominator_marks_row(qtbot):
    model = ROITableModel(_collection_with_two())
    fid = model.fidForRow(0)
    model.setDenominatorFid(fid)
    assert model.denominatorFid == fid
    name_index = model.index(0, 1)
    display = model.data(name_index, Qt.ItemDataRole.DisplayRole)
    assert "÷" in display  # the ÷ marker
    font = model.data(name_index, Qt.ItemDataRole.FontRole)
    assert isinstance(font, QFont) and font.bold()


def test_non_denominator_row_unmarked(qtbot):
    model = ROITableModel(_collection_with_two())
    model.setDenominatorFid(model.fidForRow(0))
    other = model.index(1, 1)
    assert "÷" not in model.data(other, Qt.ItemDataRole.DisplayRole)


def test_set_denominator_emits_data_changed(qtbot):
    model = ROITableModel(_collection_with_two())
    with qtbot.waitSignal(model.dataChanged, timeout=500):
        model.setDenominatorFid(model.fidForRow(0))


def test_set_template_marks_row(qtbot):
    model = ROITableModel(_collection_with_two())
    fid = model.fidForRow(1)
    model.setTemplateFid(fid)
    assert model.templateFid == fid
    display = model.data(model.index(1, 1), Qt.ItemDataRole.DisplayRole)
    assert "⊞" in display


def test_template_and_denominator_independent(qtbot):
    model = ROITableModel(_collection_with_two())
    model.setDenominatorFid(model.fidForRow(0))
    model.setTemplateFid(model.fidForRow(1))
    assert model.denominatorFid == model.fidForRow(0)
    assert model.templateFid == model.fidForRow(1)
    assert "÷" in model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole)
    assert "⊞" in model.data(model.index(1, 1), Qt.ItemDataRole.DisplayRole)


BLUE = Color(0.0, 0.0, 1.0, 0.5)


def test_the_name_column_is_the_class(qtbot):
    model = ROITableModel(_collection_with_two())
    header = model.headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
    assert header == "Class"


def test_recolouring_an_roi_recolours_its_whole_class(qtbot):
    from PyQt6.QtGui import QColor

    c = _collection_with_two()
    third = c.addROI(box(6, 6, 8, 8), "alpha", RED, ROIMode.RECTANGLE)
    model = ROITableModel(c)
    model.setData(model.index(0, 2), QColor(0, 0, 255, 128))
    assert c.getROI(third).color.toQColor().name() == "#0000ff"
    assert c.getROI(model.fidForRow(1)).color == RED  # "beta" untouched


def test_moving_an_roi_into_a_class_takes_on_its_colour(qtbot):
    c = ROICollection()
    c.addROI(box(0, 0, 5, 5), "alpha", RED, ROIMode.RECTANGLE)
    moved = c.addROI(box(6, 6, 8, 8), "Class 2", BLUE, ROIMode.RECTANGLE)
    model = ROITableModel(c)
    model.setData(model.index(1, 1), "alpha")
    assert c.getROI(moved).name == "alpha" and c.getROI(moved).color == RED
