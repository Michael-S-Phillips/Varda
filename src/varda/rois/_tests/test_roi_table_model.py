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
