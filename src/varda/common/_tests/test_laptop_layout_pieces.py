"""The pieces that keep panels readable on small screens: FlowLayout,
ElidingComboBox, PanelScrollArea, VardaDockWidget, and the audit that finds
text that's cut off."""

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QTableView,
    QWidget,
)

from varda.common.layout_audit import clippedWidgets
from varda.common.ui import (
    ElidingComboBox,
    FlowLayout,
    PanelScrollArea,
    VardaDockWidget,
)

LONG = "Moon: Lunar Orbiter Laser Altimeter (LOLA) Shot Observations"


def _buttons(layout: QLayout) -> tuple[QWidget, list[QPushButton]]:
    widget = QWidget()
    widget.setLayout(layout)
    buttons = [QPushButton(f"Button number {i}") for i in range(5)]
    for button in buttons:
        layout.addWidget(button)
    return widget, buttons


def test_a_flow_layout_wraps_its_items_instead_of_widening(qtbot):
    layout = FlowLayout()
    widget, buttons = _buttons(layout)
    qtbot.addWidget(widget)
    widest = max(b.sizeHint().width() for b in buttons)
    assert layout.minimumSize().width() == widest
    assert layout.sizeHint().width() > 4 * widest  # preferred: one row
    oneRow = layout.heightForWidth(layout.sizeHint().width())
    assert layout.heightForWidth(widest) > 3 * oneRow  # narrow: one per row
    widget.resize(widest, layout.heightForWidth(widest))
    widget.show()
    qtbot.waitExposed(widget)
    assert clippedWidgets(widget) == []


def test_the_audit_finds_a_row_of_buttons_squeezed_too_narrow(qtbot):
    layout = QHBoxLayout()
    widget, buttons = _buttons(layout)
    qtbot.addWidget(widget)
    widget.setMinimumWidth(0)
    layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetNoConstraint)
    widget.resize(150, 40)
    widget.show()
    qtbot.waitExposed(widget)
    assert any("Button number" in problem for problem in clippedWidgets(widget))


def test_the_audit_finds_an_unwrapped_label_cut_off_by_its_panel(qtbot):
    panel = QWidget()
    label = QLabel(LONG, panel)
    label.resize(label.sizeHint())
    qtbot.addWidget(panel)
    panel.resize(100, 40)
    panel.show()
    qtbot.waitExposed(panel)
    assert clippedWidgets(panel) == [f"QLabel {LONG!r}: cut off by QWidget ''"]


def test_an_eliding_combo_box_shrinks_and_keeps_its_full_text_in_the_tooltip(
    qtbot,
):
    combo = ElidingComboBox()
    combo.setToolTip("Click to search")
    combo.addItems([LONG, "Mars"])
    qtbot.addWidget(combo)
    combo.resize(140, combo.sizeHint().height())
    combo.show()
    qtbot.waitExposed(combo)
    assert combo.minimumSizeHint().width() < 200
    assert combo.isElided()
    assert combo.toolTip() == f"{LONG}\n\nClick to search"
    assert clippedWidgets(combo.parentWidget() or combo) == []
    combo.setCurrentIndex(1)  # fits: just its own tooltip
    combo.repaint()
    assert combo.toolTip() == "Click to search"


def test_a_panel_scroll_area_is_as_narrow_as_its_panel_can_be(qtbot):
    panel = QWidget()
    flow = FlowLayout(panel)
    for i in range(6):
        flow.addWidget(QPushButton(f"Action {i}"))
    area = PanelScrollArea(panel)
    qtbot.addWidget(area)
    assert area.minimumSizeHint().width() >= panel.minimumSizeHint().width()
    assert area.minimumSizeHint().width() < panel.sizeHint().width()


def test_a_dock_scrolls_a_panel_down_never_sideways(qtbot):
    panel = QLabel(LONG)
    dock = VardaDockWidget("Panel").withWidget(panel)
    qtbot.addWidget(dock)
    assert dock.widget() is panel
    area = dock.findChild(PanelScrollArea)
    assert isinstance(area, PanelScrollArea) and area.panel is panel
    assert dock.minimumSizeHint().width() >= panel.minimumSizeHint().width()
    table = QTableView()
    assert VardaDockWidget("Table").withWidget(table).widget() is table
