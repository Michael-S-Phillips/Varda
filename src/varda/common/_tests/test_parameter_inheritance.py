"""Parameter groups inherit their bases' parameters; LabeledEnum values are
the labels the UI shows."""

from enum import Enum

from varda.common.parameter import (
    EnumParameter,
    IntParameter,
    LabeledEnum,
    ParameterGroup,
)


class _Base(ParameterGroup):
    shared = IntParameter("Shared", 1)


class _Child(_Base):
    own = IntParameter("Own", 2)


def test_a_subclass_has_its_own_parameters_first_then_its_bases():
    child = _Child()
    assert list(child.params) == ["own", "shared"]
    assert child.shared.value == 1


def test_instances_get_their_own_copies_of_inherited_parameters():
    first, second = _Child(), _Child()
    first.shared.set(5)
    assert second.shared.value == 1


def test_a_subclass_can_override_a_base_parameter():
    class Override(_Base):
        shared = IntParameter("Shared", 9)

    assert Override().shared.value == 9


class _Plain(Enum):
    RGB_TO_HSV = 1


class _Labeled(LabeledEnum):
    RGB_TO_HSV = "RGB to HSV"


def test_enum_labels_come_from_names_unless_the_enum_is_labeled():
    assert EnumParameter("x", _Plain).enumNames == ["Rgb To Hsv"]
    assert EnumParameter("x", _Labeled).enumNames == ["RGB to HSV"]
