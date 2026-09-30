"""Step size, decimals, and slider options on numeric parameters."""

from varda.common.parameter import FloatParameter, Vec2Parameter
from varda.common.vec2 import Vec2


def test_float_parameter_step_and_decimals_configure_spinbox(qapp):
    widget = FloatParameter("Scale", default=1.0, step=0.05, decimals=3).getWidget()
    assert widget.spinBox.singleStep() == 0.05
    assert widget.spinBox.decimals() == 3


def test_float_parameter_without_step_keeps_spinbox_defaults(qapp):
    widget = FloatParameter("Plain", default=1.0).getWidget()
    assert widget.spinBox.singleStep() == 1.0
    assert widget.spinBox.decimals() == 2


def test_float_parameter_can_hide_slider_while_keeping_range(qapp):
    param = FloatParameter(
        "Scale", default=1.0, range=(0.001, 1000.0), decimals=3, showSlider=False
    )
    widget = param.getWidget()
    assert widget.slider is None
    # range must survive the spin box's decimal rounding
    assert widget.spinBox.minimum() == 0.001


def test_float_parameter_clone_preserves_step_decimals_and_slider(qapp):
    clone = FloatParameter(
        "Scale", range=(0.001, 1000.0), step=0.05, decimals=3, showSlider=False
    ).clone()
    assert (clone.step, clone.decimals, clone.showSlider) == (0.05, 3, False)


def test_vec2_parameter_step_and_decimals_configure_both_spinboxes(qapp):
    param = Vec2Parameter("Y Range", default=Vec2(0.0, 1.0), step=0.01, decimals=4)
    widget = param.getWidget()
    assert (widget.xSpinBox.singleStep(), widget.ySpinBox.singleStep()) == (0.01, 0.01)
    assert (widget.xSpinBox.decimals(), widget.ySpinBox.decimals()) == (4, 4)
    clone = param.clone()
    assert (clone.step, clone.decimals) == (0.01, 4)
