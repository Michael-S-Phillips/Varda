"""MultiChoiceParameter: pick any subset of a list of named choices."""

from PyQt6.QtCore import Qt

from varda.common.parameter import MultiChoiceParameter


def test_defaults_to_every_choice_selected():
    param = MultiChoiceParameter("Things", ["a", "b", "c"])
    assert param.choices == ["a", "b", "c"]
    assert param.get() == ["a", "b", "c"]


def test_explicit_default_selects_only_those():
    param = MultiChoiceParameter("Things", ["a", "b", "c"], default=["c"])
    assert param.get() == ["c"]


def test_set_keeps_choice_order_and_drops_unknown_names():
    param = MultiChoiceParameter("Things", ["a", "b", "c"])
    param.set(["c", "zzz", "a"])
    assert param.get() == ["a", "c"]


def test_set_choices_selects_all_new_choices_by_default_and_notifies():
    param = MultiChoiceParameter("Things", ["a", "b"], default=["a"])
    seen = []
    param.sigChoicesChanged.connect(seen.append)

    param.setChoices(["x", "y", "z"])

    assert param.choices == ["x", "y", "z"]
    assert param.get() == ["x", "y", "z"]
    assert seen == [["x", "y", "z"]]


def test_set_choices_can_keep_an_explicit_selection():
    param = MultiChoiceParameter("Things", ["a", "b"])
    param.setChoices(["a", "b", "c"], selected=["c", "a"])
    assert param.get() == ["a", "c"]


def test_widget_shows_checked_items_and_toggling_updates_the_value(qtbot):
    param = MultiChoiceParameter("Things", ["a", "b", "c"], default=["b"])
    widget = param.getWidget()
    qtbot.addWidget(widget)

    states = [
        widget.listWidget.item(i).checkState() for i in range(widget.listWidget.count())
    ]
    assert states == [
        Qt.CheckState.Unchecked,
        Qt.CheckState.Checked,
        Qt.CheckState.Unchecked,
    ]

    widget.listWidget.item(2).setCheckState(Qt.CheckState.Checked)
    assert param.get() == ["b", "c"]


def test_widget_all_and_none_buttons(qtbot):
    param = MultiChoiceParameter("Things", ["a", "b", "c"], default=["b"])
    widget = param.getWidget()
    qtbot.addWidget(widget)

    widget.allButton.click()
    assert param.get() == ["a", "b", "c"]
    widget.noneButton.click()
    assert param.get() == []


def test_widget_follows_new_choices(qtbot):
    param = MultiChoiceParameter("Things", ["a", "b"])
    widget = param.getWidget()
    qtbot.addWidget(widget)

    param.setChoices(["p", "q", "r"], selected=["q"])

    labels = [
        widget.listWidget.item(i).text() for i in range(widget.listWidget.count())
    ]
    assert labels == ["p", "q", "r"]
    assert widget.listWidget.item(1).checkState() == Qt.CheckState.Checked
    assert widget.listWidget.item(0).checkState() == Qt.CheckState.Unchecked


def test_widget_range_entry_selects_choices_by_position(qtbot):
    param = MultiChoiceParameter("Things", [f"c{i}" for i in range(1, 9)])
    widget = param.getWidget()
    qtbot.addWidget(widget)

    widget.rangeEdit.setText("2-4, 7")
    widget.rangeButton.click()

    assert param.get() == ["c2", "c3", "c4", "c7"]


def test_widget_range_entry_ignores_junk_and_out_of_range_positions(qtbot):
    param = MultiChoiceParameter("Things", ["a", "b", "c"])
    widget = param.getWidget()
    qtbot.addWidget(widget)

    widget.rangeEdit.setText("0, 2-9, x")
    widget.rangeButton.click()

    assert param.get() == ["b", "c"]


def test_clone_copies_choices_and_default():
    param = MultiChoiceParameter("Things", ["a", "b"], default=["b"], description="d")
    clone = param.clone()
    assert clone.choices == ["a", "b"]
    assert clone.get() == ["b"]
    assert clone.description == "d"
