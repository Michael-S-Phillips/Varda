"""The endmember table: add, rename, recolour, merge, delete, active row."""

import pytest
from PyQt6.QtGui import QColor

from synthetic_scene import modelThroughPpi, modelWithEndmembers
from varda.workspaces.spectral_hourglass.endmember_table import EndmemberTable


@pytest.fixture
def table(qtbot):
    widget = EndmemberTable(modelWithEndmembers())
    qtbot.addWidget(widget)
    return widget


def test_rows_follow_the_model(table):
    assert table.table.rowCount() == 3
    assert [table.table.item(r, 1).text() for r in range(3)] == [
        "flat",
        "clay",
        "mafic",
    ]
    assert table.table.item(0, 2).text() == "16"


def test_adding_makes_the_new_endmember_active(table, qtbot):
    with qtbot.waitSignal(table.sigActiveChanged) as blocker:
        table.addButton.click()
    assert table.table.rowCount() == 4
    assert blocker.args[0] == table.model.endmembers[-1].id
    assert table.activeEndmemberId() == table.model.endmembers[-1].id


def test_editing_a_name_renames_the_endmember(table):
    table.table.item(1, 1).setText("Kaolinite")
    assert table.model.endmembers[1].name == "Kaolinite"


def test_colour_cell_shows_the_endmember_colour(table):
    table.model.recolorEndmember(table.model.endmembers[0].id, "#123456")
    assert table.table.item(0, 0).background().color() == QColor("#123456")


def test_merge_and_delete_selected_rows(table):
    table.selectRows([0, 2])
    table.mergeButton.click()
    assert [e.name for e in table.model.endmembers] == ["flat", "clay"]
    assert table.model.endmembers[0].pixels.size == 32
    table.selectRows([1])
    table.deleteButton.click()
    assert [e.name for e in table.model.endmembers] == ["flat"]


def test_suggest_creates_groups_from_the_candidates(qtbot):
    widget = EndmemberTable(modelThroughPpi())
    qtbot.addWidget(widget)
    widget.suggestCount.setValue(3)
    widget.suggestButton.click()
    assert widget.table.rowCount() == 3


def test_identification_column(table):
    table.model.setIdentification(table.model.endmembers[1].id, "Kaolinite (0.91)")
    assert table.table.item(1, 3).text() == "Kaolinite (0.91)"


def test_undo_button_reverts_the_last_edit(table):
    assert table.undoButton.isEnabled() == table.model.canUndo()
    table.addButton.click()
    assert table.table.rowCount() == 4 and table.undoButton.isEnabled()
    table.undoButton.click()
    assert table.table.rowCount() == 3
