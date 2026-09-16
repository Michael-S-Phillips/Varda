"""Tabs can be closed, whether docked in the tab bar or detached into a window."""

from PyQt6.QtWidgets import QLabel

from varda.common.ui import DetachableTabWidget


def _tabs(qtbot) -> DetachableTabWidget:
    tabs = DetachableTabWidget()
    qtbot.addWidget(tabs)
    return tabs


def test_tabs_show_close_buttons(qtbot):
    assert _tabs(qtbot).tabsClosable()


def test_discarding_a_docked_tab_removes_it(qtbot):
    tabs = _tabs(qtbot)
    first, second = QLabel("a"), QLabel("b")
    tabs.addTab(first, "a")
    tabs.addTab(second, "b")

    tabs.discardTab(first)

    assert tabs.count() == 1
    assert tabs.widget(0) is second


def test_discarding_a_detached_tab_closes_its_window_without_reattaching(qtbot):
    tabs = _tabs(qtbot)
    widget = QLabel("a")
    tabs.addTab(widget, "a")
    tabs.detachTab(0)
    window = tabs.detachedWindows[widget]
    assert tabs.count() == 0

    tabs.discardTab(widget)

    assert widget not in tabs.detachedWindows
    assert tabs.count() == 0  # not reattached
    assert not window.isVisible()
