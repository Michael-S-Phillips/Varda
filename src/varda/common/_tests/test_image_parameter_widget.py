"""The image dropdown must show the parameter's value and follow later changes."""

import pytest

from varda.common.parameter import ImageParameter
from varda.utilities.debug import generate_random_image


@pytest.fixture
def images():
    return [generate_random_image((10, 10, 10)) for _ in range(3)]


@pytest.fixture
def param(images):
    param = ImageParameter("Image")
    param.setProvider(lambda: images)
    return param


def test_widget_shows_the_parameters_current_value(qapp, param, images):
    param.set(images[1])
    widget = param.getWidget()
    assert widget.comboBox.currentIndex() == 1


def test_widget_follows_a_value_set_after_creation(qapp, param, images):
    widget = param.getWidget()
    param.set(images[2])
    assert widget.comboBox.currentIndex() == 2


def test_choosing_in_the_widget_sets_the_parameter(qapp, param, images):
    widget = param.getWidget()
    widget.comboBox.setCurrentIndex(2)
    assert param.get() is images[2]


def test_syncing_the_widget_does_not_re_emit_the_parameter(qapp, param, images):
    widget = param.getWidget()
    changes = []
    param.sigParameterChanged.connect(lambda value: changes.append(value))
    param.set(images[1])
    assert changes == [images[1]]  # once from set(), not again from the combo
    assert widget.comboBox.currentIndex() == 1
