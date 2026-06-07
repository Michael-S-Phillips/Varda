"""Tests for ROITableView row context menu actions."""

from PyQt6.QtWidgets import QMenu
from shapely.geometry import box

from varda.common.entities import Color, ROIMode
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_table_model import ROITableModel
from varda.rois.roi_table_view import ROITableView

RED = Color(1.0, 0.0, 0.0, 0.5)


def _view():
    c = ROICollection()
    c.addROI(box(0, 0, 5, 5), "alpha", RED, ROIMode.RECTANGLE)
    model = ROITableModel(c)
    return ROITableView(model), model


def _find_action(menu: QMenu, text: str):
    for a in menu.actions():
        if a.text() == text:
            return a
    raise AssertionError(f"action {text!r} not found")


def test_plot_spectrum_action_emits(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    menu = view._buildRowMenu(fid)
    with qtbot.waitSignal(view.sigPlotSpectrumRequested, timeout=500) as sig:
        _find_action(menu, "Plot Spectrum").trigger()
    assert sig.args == [fid]


def test_plot_ratio_action_emits(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    menu = view._buildRowMenu(fid)
    with qtbot.waitSignal(view.sigPlotRatioRequested, timeout=500) as sig:
        _find_action(menu, "Plot Ratio Spectrum").trigger()
    assert sig.args == [fid]


def test_set_denominator_action_emits(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    menu = view._buildRowMenu(fid)
    with qtbot.waitSignal(view.sigDenominatorSetRequested, timeout=500) as sig:
        _find_action(menu, "Set as Denominator").trigger()
    assert sig.args == [fid]


def test_set_denominator_disabled_when_already_denominator(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    model.setDenominatorFid(fid)
    menu = view._buildRowMenu(fid)
    assert not _find_action(menu, "Set as Denominator").isEnabled()


def test_clear_denominator_disabled_when_none(qtbot):
    view, model = _view()
    menu = view._buildRowMenu(model.fidForRow(0))
    assert not _find_action(menu, "Clear Denominator").isEnabled()


def test_clear_denominator_action_emits(qtbot):
    view, model = _view()
    fid = model.fidForRow(0)
    model.setDenominatorFid(fid)
    menu = view._buildRowMenu(fid)
    with qtbot.waitSignal(view.sigDenominatorClearRequested, timeout=500):
        _find_action(menu, "Clear Denominator").trigger()
