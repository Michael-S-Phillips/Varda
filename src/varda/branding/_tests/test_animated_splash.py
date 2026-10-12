"""The splash never holds the main window back by more than a second."""

import pytest
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
