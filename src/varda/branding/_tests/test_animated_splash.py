"""The splash never holds the main window back by more than a second."""

import time

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import QWidget

from varda.branding import splash as splashModule
from varda.branding.splash import (
    SPLASH_SPEC_PATH,
    AnimatedSplash,
    StaticSplash,
    createSplash,
    loadSplashSpec,
)


class FakeClock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def window(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


def _splash(qtbot, clock):
    widget = AnimatedSplash(loadSplashSpec(SPLASH_SPEC_PATH), clock=clock)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_window_ready_early_skips_to_the_last_frame_and_closes(qtbot, window):
    clock = FakeClock(0.3)  # 2.0 s of animation left
    splash = _splash(qtbot, clock)
    splash.finishWhenDone(window)
    assert splash.isDone() and splash.currentTime() == splash.end
    qtbot.waitUntil(lambda: not splash.isVisible(), timeout=2000)


def test_window_ready_near_the_end_waits_for_the_animation(qtbot, window):
    clock = FakeClock(1.8)  # 0.5 s left: worth waiting for
    splash = _splash(qtbot, clock)
    splash.finishWhenDone(window)
    qtbot.wait(100)
    assert splash.isVisible()
    clock.now = 2.4
    qtbot.waitUntil(lambda: not splash.isVisible(), timeout=2000)


def test_static_splash_on_request_or_without_a_motion_spec(
    qtbot, monkeypatch, tmp_path
):
    monkeypatch.setenv("VARDA_STATIC_SPLASH", "1")
    first = createSplash()
    qtbot.addWidget(first)
    assert isinstance(first, StaticSplash)

    monkeypatch.delenv("VARDA_STATIC_SPLASH")
    monkeypatch.setattr(splashModule, "SPLASH_SPEC_PATH", tmp_path / "missing.json")
    second = createSplash()
    qtbot.addWidget(second)
    assert isinstance(second, StaticSplash)

    monkeypatch.setattr(splashModule, "SPLASH_SPEC_PATH", SPLASH_SPEC_PATH)
    third = createSplash()
    qtbot.addWidget(third)
    assert isinstance(third, AnimatedSplash)


def test_static_splash_pixmap_is_hidpi_sized(qtbot):
    widget = StaticSplash()
    qtbot.addWidget(widget)
    pixmap = widget.pixmap()
    ratio = pixmap.devicePixelRatio()
    assert pixmap.width() == round(640 * ratio) and pixmap.height() == round(
        360 * ratio
    )


def test_the_splash_appears_at_once(qtbot):
    """QSplashScreen.show() waited up to a second for the window system;
    the splash is the first thing on screen, so it must not."""
    splash = createSplash()
    qtbot.addWidget(splash)
    started = time.perf_counter()
    splash.show()
    assert time.perf_counter() - started < 0.3
    assert splash.isVisible()


def test_the_splash_opens_on_the_screen_under_the_mouse(qtbot, monkeypatch):
    """With several displays, the one being looked at is the one with the
    mouse (QSplashScreen did the same), not necessarily the primary."""
    screen = QGuiApplication.primaryScreen()
    picked = []
    monkeypatch.setattr(
        splashModule.QGuiApplication,
        "screenAt",
        staticmethod(lambda point: picked.append(point) or screen),
    )
    splash = createSplash()
    qtbot.addWidget(splash)
    assert picked and all(point == QCursor.pos() for point in picked)
    assert screen.availableGeometry().contains(splash.frameGeometry().center())


def test_the_splash_stays_visible_while_the_app_is_in_the_background(qtbot):
    """macOS hides splash windows of an inactive app, and Varda launched from
    a terminal is inactive until its main window opens."""
    splash = createSplash()
    qtbot.addWidget(splash)
    assert splash.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
