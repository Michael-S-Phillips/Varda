from varda.common.parameter import ParameterGroup, IntParameter


class _Inner(ParameterGroup):
    value = IntParameter("Value", 0, (0, 10))


class _Outer(ParameterGroup):
    inner = _Inner()
    top = IntParameter("Top", 0, (0, 10))


def test_clone_keeps_attribute_and_params_consistent(qtbot):
    inner = _Inner()
    cloned = inner.clone()
    # the attribute and the params-dict entry must be the SAME object
    assert cloned.value is cloned.params["value"]


def test_leaf_change_emits_group_instance(qtbot):
    outer = _Outer()
    received = []
    outer.sigParameterChanged.connect(lambda g: received.append(g))
    outer.top.set(3)
    assert received and received[-1] is outer


def test_nested_group_change_propagates(qtbot):
    outer = _Outer()
    received = []
    outer.sigParameterChanged.connect(lambda g: received.append(g))
    # set through the attribute (this is what render()/programmatic edits use)
    outer.inner.value.set(7)
    assert received and received[-1] is outer
    assert outer.inner.value.get() == 7
    assert outer.inner.params["value"].get() == 7
