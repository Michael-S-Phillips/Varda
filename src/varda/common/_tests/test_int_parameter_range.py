"""IntParameter ranges can change at runtime (e.g. once an image's band count is known)."""

from varda.common.parameter import IntParameter
from varda.common.parameter_widgets import parameterWidget


def test_set_range_clamps_the_value_and_notifies():
    param = IntParameter("N", 10, range=(1, 1000))
    seen = []
    param.sigRangeChanged.connect(seen.append)

    param.setRange((1, 8))

    assert param.range == (1, 8)
    assert param.get() == 8
    assert seen == [(1, 8)]


def test_set_range_can_pick_the_value_too():
    param = IntParameter("N", 10, range=(1, 1000))
    param.setRange((1, 285), value=285)
    assert param.get() == 285


def test_widget_follows_a_range_change(qtbot):
    param = IntParameter("N", 10, range=(1, 1000))
    widget = parameterWidget(param)
    qtbot.addWidget(widget)

    param.setRange((1, 12), value=12)

    assert (widget.spinBox.minimum(), widget.spinBox.maximum()) == (1, 12)
    assert widget.spinBox.value() == 12
    assert (widget.slider.minimum(), widget.slider.maximum()) == (1, 12)


def test_a_step_allows_only_values_on_it():
    param = IntParameter("Odd", 4, range=(1, 31), step=2)
    assert param.get() == 5  # the default too
    param.set(8)
    assert param.get() == 9
    param.set(40)
    assert param.get() == 31
    param.setRange((7, 31))
    assert param.get() == 31 and param.clone().step == 2


def test_widget_steps_by_the_parameters_step(qtbot):
    param = IntParameter("Odd", 3, range=(1, 31), step=2)
    widget = parameterWidget(param)
    qtbot.addWidget(widget)
    assert widget.spinBox.singleStep() == 2
    widget.spinBox.setValue(6)
    assert param.get() == 7 and widget.spinBox.value() == 7
