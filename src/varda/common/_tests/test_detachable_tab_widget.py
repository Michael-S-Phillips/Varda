"""Workspace tabs work like a browser's: dragged into order, dragged out into
a window of their own, closed by a button or a middle click, whether docked
in the tab bar or detached into a window."""

from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QLabel

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


def _mouse(bar, kind, pos, button, buttons):
    event = QMouseEvent(
        kind,
        QPointF(pos),
        QPointF(bar.mapToGlobal(pos)),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(bar, event)


def test_tabs_can_be_dragged_into_a_new_order(qtbot):
    assert _tabs(qtbot).tabBar().isMovable()


def test_a_middle_click_closes_a_tab_as_in_a_browser(qtbot):
    tabs = _tabs(qtbot)
    tabs.addTab(QLabel("a"), "a")
    tabs.addTab(QLabel("b"), "b")
    tabs.show()
    closed = []
    tabs.tabCloseRequested.connect(closed.append)
    bar = tabs.tabBar()
    middle = Qt.MouseButton.MiddleButton
    _mouse(bar, QEvent.Type.MouseButtonPress, bar.tabRect(1).center(), middle, middle)
    assert closed == [1]


def test_dragging_a_tab_out_of_the_bar_opens_it_in_its_own_window(qtbot):
    tabs = _tabs(qtbot)
    first, second = QLabel("a"), QLabel("b")
    tabs.addTab(first, "a")
    tabs.addTab(second, "b")
    tabs.show()
    bar = tabs.tabBar()
    left, none = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    start = bar.tabRect(1).center()
    _mouse(bar, QEvent.Type.MouseButtonPress, start, left, left)
    _mouse(bar, QEvent.Type.MouseMove, start + QPoint(0, 10), none, left)
    assert tabs.count() == 2  # a small move stays in the bar
    _mouse(bar, QEvent.Type.MouseMove, start + QPoint(0, 200), none, left)
    assert second in tabs.detachedWindows and tabs.count() == 1
    tabs.detachedWindows[second].close()  # closing it puts the tab back
    assert tabs.count() == 2
