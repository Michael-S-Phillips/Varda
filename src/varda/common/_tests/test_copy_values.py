"""copyValues gives one parameter group another's values."""

from enum import Enum

from varda.common.parameter import (
    EnumParameter,
    FloatParameter,
    IntParameter,
    ParameterGroup,
    Vec2Parameter,
    copyValues,
)
from varda.common.vec2 import Vec2


class Mode(Enum):
    A = 1
    B = 2


class Inner(ParameterGroup):
    size = IntParameter("Size", 3, range=(0, 10))
    span = Vec2Parameter("Span", Vec2(0.0, 1.0))


class Outer(ParameterGroup):
    mode = EnumParameter("Mode", Mode)
    scale = FloatParameter("Scale", 1.0)
    inner = Inner()


def test_values_are_copied_including_nested_groups():
    source, target = Outer(), Outer()
    source.mode.set(Mode.B)
    source.scale.set(2.5)
    source.inner.size.set(7)
    source.inner.span.set(Vec2(0.2, 0.8))
    copyValues(source, target)
    assert target.mode.get() is Mode.B and target.scale.get() == 2.5
    assert target.inner.size.get() == 7
    assert target.inner.span.get() == Vec2(0.2, 0.8)


def test_copies_are_independent():
    source, target = Outer(), Outer()
    copyValues(source, target)
    target.inner.span.get().x = 0.9  # the widget edits a Vec2 in place
    assert source.inner.span.get().x == 0.0


def test_the_target_announces_the_change_once():
    source, target = Outer(), Outer()
    source.scale.set(4.0)
    source.inner.size.set(5)
    seen = []
    target.sigParameterChanged.connect(seen.append)
    copyValues(source, target)
    assert seen == [target]
